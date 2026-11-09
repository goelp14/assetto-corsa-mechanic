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


def test_tyres_out_peak_survives_subsampling():
    tmp = tempfile.mkdtemp()
    arch = TelemetryArchive(sessions_dir=tmp, subsample_every=4, async_writes=False)
    arch.start_session("rt_sonoma", "test_car")
    for i, out in enumerate([0, 3, 0, 0, 0, 0, 0, 0]):
        frame = TelemetryIngest.frame_from_dict({"spline": i * 0.01, "speed_kmh": 90})
        frame.tyres_out = out
        arch.observe_frame(frame)
    arch.flush_lap(1, 95000)
    with open(os.path.join(arch.session_dir, "laps", "lap_01.json"), "r") as fh:
        samples = json.load(fh)["samples"]
    assert [s.get("tyres_out") for s in samples] == [3, None]


def test_ffb_clipping_and_live_brake_bias_recorded():
    tmp = tempfile.mkdtemp()
    arch = TelemetryArchive(sessions_dir=tmp, subsample_every=2, async_writes=False)
    arch.start_session("rt_sonoma", "test_car")
    for i, ff in enumerate([0.5, 1.0, -0.3, -1.0]):
        frame = TelemetryIngest.frame_from_dict({"spline": i * 0.01, "speed_kmh": 90})
        frame.ffb = ff
        frame.brake_bias = 0.58
        arch.observe_frame(frame)
    arch.flush_lap(1, 95000, setup_snapshot={"FRONT_BIAS": 60}, setup_source="Auto_Tweak.ini")
    with open(os.path.join(arch.session_dir, "laps", "lap_01.json"), "r") as fh:
        payload = json.load(fh)
    assert payload["ffb_clip_pct"] == 50.0
    assert payload["brake_bias_live"] == 58.0
    assert [s["ffb"] for s in payload["samples"]] == [1.0, 1.0]
    with open(os.path.join(arch.session_dir, "session.jsonl"), "r") as fh:
        lap = [json.loads(l) for l in fh if '"lap_summary"' in l][0]
    assert lap["setup_snapshot_source"] == "Auto_Tweak.ini"
    assert lap["brake_bias_live"] == 58.0


def test_tyre_brake_and_ride_height_channels_recorded():
    tmp = tempfile.mkdtemp()
    arch = TelemetryArchive(sessions_dir=tmp, subsample_every=1, async_writes=False)
    arch.start_session("rt_sonoma", "test_car")
    for i, lat in enumerate([0.2, 1.2, -1.4]):
        frame = TelemetryIngest.frame_from_dict({
            "spline": i * 0.01, "speed_kmh": 120 + i, "acc_g": (0.0, lat, 0.0), "rpm": 9000 + i, "gear": 4,
            "slip": (0.01, 0.02, 0.05, 0.06), "wheel_speed": (100.0, 101.0, 98.0, 99.0),
            "tyre_radius": (0.3, 0.3, 0.33, 0.33), "tyre_temp": (70.0, 71.0, 80.0, 81.0 + i),
            "tyre_pressure": (25.0, 25.5, 26.0, 26.0 + i), "camber": (-0.02, -0.02, -0.01, -0.01),
            "tyre_temp_imo": ((80.0, 75.0, 70.0),) * 4, "brake_temp": (300.0 + i, 300.0, 200.0, 200.0),
            "ride_height": (0.05 - 0.01 * i, 0.07), "susp_ratio": (0.5, 0.99, 0.5, 0.5),
        })
        arch.observe_frame(frame)
    arch.flush_lap(1, 95000)
    with open(os.path.join(arch.session_dir, "laps", "lap_01.json"), "r") as fh:
        payload = json.load(fh)
    s = payload["samples"][0]
    assert s["wheel_slip"] == [0.01, 0.02, 0.05, 0.06]
    assert s["wheel_rads"] == [100.0, 101.0, 98.0, 99.0]
    assert s["tyre_imo"][0] == [80.0, 75.0, 70.0]
    assert s["camber_deg"][0] == -1.15
    assert s["ride_height_mm"] == [50.0, 70.0]
    assert payload["tyre_radius_m"] == [0.3, 0.3, 0.33, 0.33]
    cs = payload["car_state"]
    assert cs["psi_max"][3] == 28.0
    assert cs["core_mean"][3] == 82.0
    assert cs["imo_cornering"][0] == [80.0, 75.0, 70.0]
    assert cs["brake_temp_max"][0] == 302.0
    assert cs["ride_height_min_mm"] == [30.0, 70.0]
    assert cs["bump_stop_pct"] == [0.0, 100.0, 0.0, 0.0]
    assert cs["top_speed_kmh"] == 122 and cs["max_rpm"] == 9002


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
