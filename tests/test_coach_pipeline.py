import json
import os
import sys
import tempfile

import pytest

COACH = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools", "coach")
QT = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
LIB = os.path.join(os.path.dirname(__file__), "..", "ac_app", "lib")

for p in (COACH, QT, LIB):
    if p not in sys.path:
        sys.path.insert(0, p)


def _thresholds():
    path = os.path.join(os.path.dirname(__file__), "..", "ac_app", "config", "thresholds.json")
    with open(path) as fh:
        return json.load(fh)


def _spin_samples():
    samples = []
    for i in range(20):
        sp = 0.40 + i * 0.002
        beta = 5.0 if i < 15 else 10.0 + (i - 15) * 8.0
        samples.append({
            "spline": sp,
            "corner": "t7",
            "phase": "exit",
            "speed_kmh": 120 - i,
            "throttle": 0.9 if i >= 14 else 0.3,
            "steer_deg": 45.0,
            "acc_g_lat": 1.4 if i >= 14 else 0.8,
            "beta_deg": beta,
            "susp_ratio": [0.3, 0.3, 0.3, 0.3],
        })
    samples[-1]["beta_deg"] = 42.0
    return samples


def test_detect_incidents_high_beta():
    from incident_analyzer import detect_incidents_in_samples

    thresholds = _thresholds()
    incidents = detect_incidents_in_samples(_spin_samples(), 3, thresholds)
    assert len(incidents) >= 1
    inc = incidents[0]
    assert inc["peak_beta_deg"] >= 35
    assert len(inc["pre_window"]) >= 1
    assert "hypothesis_ids" in inc
    assert inc["template_key"] == "root_loss_of_control"


def test_evidence_pack_citations():
    from evidence_pack import build_evidence_pack

    tmp = tempfile.mkdtemp()
    analysis = os.path.join(tmp, "analysis")
    os.makedirs(analysis)
    os.makedirs(os.path.join(tmp, "laps"))

    incidents = [{
        "incident_id": "lap3_s0.412",
        "lap": 3,
        "spline": 0.412,
        "corner": "t7",
        "peak_beta_deg": 41.2,
        "confidence": 0.82,
    }]
    with open(os.path.join(analysis, "incidents.json"), "w") as fh:
        json.dump(incidents, fh)
    for name in ("stint_summary", "time_loss", "corner_reports", "pace_opportunities",
                 "setup_timeline", "annotations", "session_plan", "sector_bests", "gg_envelope"):
        with open(os.path.join(analysis, "%s.json" % name), "w") as fh:
            json.dump({} if name in ("stint_summary", "time_loss", "session_plan", "sector_bests", "gg_envelope") else [], fh)
    with open(os.path.join(tmp, "manifest.json"), "w") as fh:
        json.dump({"session_id": "test", "track_id": "monaco_2020", "geometry": "geometry.json"}, fh)

    pack = build_evidence_pack(tmp, corner="t7", lap=3)
    assert pack["incidents"]
    assert pack["incidents"][0]["evidence_id"] == "incident_0"
    assert "incident_0" in pack["citation_ids"]


def test_citation_guard_rejects_unknown():
    from citation_guard import validate_citations

    pack = {"citation_ids": ["incident_0"], "incidents": [{"evidence_id": "incident_0", "peak_beta_deg": 41}]}
    ok, issues = validate_citations({
        "summary": "Beta peaked at 41 degrees.",
        "citations": ["incident_0"],
    }, pack)
    assert ok

    ok2, issues2 = validate_citations({
        "summary": "Beta peaked at 99 degrees.",
        "citations": ["incident_0"],
    }, pack)
    assert not ok2
    assert any("99" in i for i in issues2)


def test_ask_coach_deterministic():
    from coach_service import ask_coach

    tmp = tempfile.mkdtemp()
    analysis = os.path.join(tmp, "analysis")
    os.makedirs(analysis)
    incidents = [{
        "incident_id": "lap3_s0.412",
        "lap": 3,
        "spline": 0.412,
        "corner": "t7",
        "phase": "exit",
        "peak_beta_deg": 41.2,
        "hypotheses": [{"id": "loss_of_control", "label": "Inputs exceeded grip", "confidence": 0.6}],
        "confidence": 0.82,
    }]
    with open(os.path.join(analysis, "incidents.json"), "w") as fh:
        json.dump(incidents, fh)
    for name, val in (
        ("stint_summary", {}), ("time_loss", {}), ("corner_reports", []),
        ("pace_opportunities", []), ("setup_timeline", []), ("annotations", []),
        ("session_plan", {}), ("sector_bests", {}), ("gg_envelope", {}),
    ):
        with open(os.path.join(analysis, "%s.json" % name), "w") as fh:
            json.dump(val, fh)
    with open(os.path.join(tmp, "manifest.json"), "w") as fh:
        json.dump({"session_id": "test"}, fh)

    resp = ask_coach(tmp, "Why did I spin?", corner="t7", lap=3)
    assert resp.get("what") or resp.get("summary")
    assert resp.get("question_type") == "incident"


def test_offline_yaw_gate():
    from incident_analyzer import offline_yaw_gate_for_corner

    thresholds = _thresholds()
    gate = offline_yaw_gate_for_corner(_spin_samples(), "t7", thresholds)
    assert gate is not None
    assert gate.gate == "LOSS_OF_CONTROL"


def test_analyze_session_incidents():
    from incident_analyzer import analyze_session_incidents

    tmp = tempfile.mkdtemp()
    lap1 = os.path.join(tmp, "lap_01.json")
    lap2 = os.path.join(tmp, "lap_02.json")
    clean = [{"spline": 0.4 + i * 0.01, "beta_deg": 2, "corner": "t7", "throttle": 0.2,
              "steer_deg": 10, "acc_g_lat": 0.5, "speed_kmh": 150, "susp_ratio": [0.2]*4}
             for i in range(10)]
    with open(lap1, "w") as fh:
        json.dump({"lap": 1, "lap_time_ms": 80000, "samples": clean}, fh)
    with open(lap2, "w") as fh:
        json.dump({"lap": 2, "lap_time_ms": 85000, "samples": _spin_samples()}, fh)

    incidents = analyze_session_incidents([lap1, lap2], _thresholds())
    assert len(incidents) >= 1
