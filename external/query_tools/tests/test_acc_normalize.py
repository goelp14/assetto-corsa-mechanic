import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from external.query_tools.acc_ingest.normalize import (
    normalize_sample,
    write_lap,
    write_session_start,
)


def test_normalize_sample_maps_acc_fields():
    raw = {
        "gas": 0.5,
        "speedKmh": 120.3,
        "steerAngle": 0.25,
        "accG": [1.1, 0.0, -0.8],
        "tyreCoreTemperature": [80.0, 81.0, 79.0, 80.5],
        "wheelsPressure": [27.1, 27.2, 26.9, 27.0],
        "tc": 0.1,
        "abs": 0.0,
    }
    s = normalize_sample(raw, source="acc_shm")
    assert s["throttle"] == 0.5
    assert s["speed_kmh"] == 120.3
    assert s["steer_deg"] == 25.0
    assert s["acc_g_lat"] == 1.1
    assert s["acc_g_long"] == -0.8
    assert s["tyre_core"] == [80.0, 81.0, 79.0, 80.5]
    assert s["tyre_psi"] == [27.1, 27.2, 26.9, 27.0]
    assert s["ingest_source"] == "acc_shm"


def test_write_lap_roundtrip(tmp_path):
    session = tmp_path / "sess"
    session.mkdir()
    (session / "laps").mkdir()
    write_session_start(
        str(session),
        track="spa",
        car="ferrari_296_gt3",
        source="acc_motec",
    )
    samples = [
        {"spline": 0.1, "speed_kmh": 100.0, "throttle": 1.0, "brake": 0.0, "steer_deg": 5.0},
        {"spline": 0.2, "speed_kmh": 110.0, "throttle": 0.8, "brake": 0.0, "steer_deg": 3.0},
    ]
    lap_path = write_lap(str(session), 1, 120_000, samples, source="acc_motec")
    assert os.path.isfile(lap_path)

    with open(lap_path, encoding="utf-8") as fh:
        lap = json.load(fh)
    assert lap["lap"] == 1
    assert lap["lap_time_ms"] == 120_000
    assert len(lap["samples"]) == 2
    assert lap["samples"][0]["spline"] == 0.1
    assert lap["source"] == "acc_motec"

    with open(session / "session.jsonl", encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh]
    types = [r["record_type"] for r in lines]
    assert "session_start" in types
    assert "lap_summary" in types
    assert lines[0]["game"] == "acc"
    assert lines[0]["source"] == "acc_motec"