import json
import os
import tempfile

from telemetry_archive import TelemetryArchive
from telemetry_ingest import TelemetryIngest


def test_session_round_trip():
    tmp = tempfile.mkdtemp()
    arch = TelemetryArchive(sessions_dir=tmp, subsample_every=1, async_writes=False)
    arch.start_session("monza", "rss_formula_hybrid_x_2026")
    frame = TelemetryIngest.frame_from_dict({
        "spline": 0.12, "speed_kmh": 250, "brake": 0.5, "throttle": 0.0,
        "steer": 0.1, "acc_g": (0, 1.5, 0), "yaw_rate": 0.1,
    })
    arch.observe_frame(frame, corner="Turn 4", phase="entry")
    arch.flush_lap(1, 95000)
    arch.end_session(1, 95000)
    jsonl = os.path.join(arch.session_dir, "session.jsonl")
    assert os.path.isfile(jsonl)
    with open(jsonl, "r") as fh:
        lines = [json.loads(l) for l in fh if l.strip()]
    types = [r["record_type"] for r in lines]
    assert "session_start" in types
    assert "lap_summary" in types


def test_phase_change_and_lap_type():
    tmp = tempfile.mkdtemp()
    arch = TelemetryArchive(sessions_dir=tmp, async_writes=False)
    arch.start_session("monaco", "test_car", phase="LEARNING")
    arch.record_phase_change("LEARNING", "TWEAKING", 4, clean_laps=3, total_laps=8)
    arch.record_pit_transition("entry", 5, 0.82)
    arch.flush_lap(5, 81000, lap_type="in_lap", phase="TWEAKING", counted=False)
    arch.note_setup_tweak(1)
    arch.record_setup_change("t1", "WING_0", 29, 31, symptom="bootstrap")
    arch.end_session(12, 80163, phase="TWEAKING")
    with open(os.path.join(arch.session_dir, "session.jsonl"), "r") as fh:
        rows = [json.loads(l) for l in fh if l.strip()]
    types = [r["record_type"] for r in rows]
    assert "phase_change" in types
    assert "pit_transition" in types
    lap = [r for r in rows if r["record_type"] == "lap_summary"][0]
    assert lap["lap_type"] == "in_lap"
    assert lap["counted"] is False
    end = [r for r in rows if r["record_type"] == "session_end"][0]
    assert end["total_laps"] == 12
    assert end["best_lap_ms"] == 80163
    assert end["phase"] == "TWEAKING"
    assert end["setup_tweaks_applied"] == 1


def test_decimate_samples_caps_lap_file():
    from telemetry_archive import _decimate_samples, TelemetryArchive
    samples = [{"spline": i * 0.001} for i in range(5000)]
    trimmed = _decimate_samples(samples, 1200)
    assert len(trimmed) == 1200

    tmp = tempfile.mkdtemp()
    arch = TelemetryArchive(
        sessions_dir=tmp, subsample_every=1, max_lap_samples=100, async_writes=False,
    )
    arch.start_session("monza", "test_car")
    frame = TelemetryIngest.frame_from_dict({
        "spline": 0.1, "speed_kmh": 200, "brake": 0.0, "throttle": 1.0,
        "steer": 0.0, "acc_g": (0, 0.5, 0), "yaw_rate": 0.0,
    })
    for _ in range(400):
        arch.observe_frame(frame)
    arch.flush_lap(1, 90000)
    lap_path = os.path.join(arch.session_dir, "laps", "lap_01.json")
    with open(lap_path, "r") as fh:
        payload = json.load(fh)
    assert len(payload["samples"]) == 100
    assert payload["sample_count_raw"] == 400
