import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QT = os.path.join(ROOT, "external", "query_tools")
if QT not in sys.path:
    sys.path.insert(0, QT)

from setup_episodes import build_setup_episodes, build_setup_timeline


def test_build_setup_episodes_merges_queue_and_apply():
    records = [
        {"record_type": "lap_summary", "lap": 4, "lap_time_ms": 81000},
        {"record_type": "lap_summary", "lap": 5, "lap_time_ms": 80500},
        {"record_type": "setup_queued", "lap": 5, "section": "WING_0", "delta": 1,
         "corner": "turn_6", "phase": "mid", "spline": 0.42,
         "detection_what": "Turn 6 (mid) — mid understeer",
         "detection_why": "balance output score 0.62"},
        {"record_type": "pit_transition", "kind": "entry", "lap": 6, "spline": 0.01},
        {"record_type": "lap_summary", "lap": 6, "lap_time_ms": 80100},
        {"record_type": "setup_change", "tweak_id": "monaco_001", "parameter": "WING_0",
         "old_value": 29, "new_value": 30, "lap": 6, "queued_lap": 5, "pit_entry": True,
         "corner": "turn_6", "phase": "mid", "spline": 0.42,
         "detection_what": "Turn 6 (mid) — mid understeer",
         "detection_why": "balance output score 0.62"},
        {"record_type": "setup_evaluation", "tweak_id": "monaco_001", "status": "confirmed",
         "effectiveness": 0.4, "lap": 8, "lap_time_delta_ms": -120},
        {"record_type": "lap_summary", "lap": 7, "lap_time_ms": 79900},
        {"record_type": "lap_summary", "lap": 8, "lap_time_ms": 79800},
    ]
    episodes = build_setup_episodes(records, lap_count=8)
    assert len(episodes) == 1
    ep = episodes[0]
    assert ep["parameter"] == "WING_0"
    assert ep["detected_lap"] == 5
    assert ep["applied_lap"] == 6
    assert ep["detection_what"] == "Turn 6 (mid) — mid understeer"
    assert ep["status"] == "confirmed"
    assert ep["active_from_lap"] == 6
    timeline = build_setup_timeline(episodes)
    assert timeline[0]["detected_spline"] == 0.42
