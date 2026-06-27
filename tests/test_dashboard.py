import json
import os

from dashboard import EngineerDashboard
from telemetry_ingest import TelemetryIngest


def _monaco_indexer():
    from spline_indexer import SplineIndexer
    path = os.path.join(
        os.path.dirname(__file__), "..", "ac_app", "config", "tracks", "monaco_2020.json",
    )
    with open(path) as fh:
        return SplineIndexer(json.load(fh))


def test_track_position_bar_moves_with_spline():
    from dashboard import track_position_bar
    a = track_position_bar(0.0)
    b = track_position_bar(0.5)
    assert a != b
    assert "O" in a
    assert "[" in a


def test_dashboard_learning_shows_landmark_hint():
    idx = _monaco_indexer()
    dash = EngineerDashboard()
    frame = TelemetryIngest.frame_from_dict({
        "spline": 0.70, "speed_kmh": 180, "brake": 0.5, "throttle": 0.0,
        "steer": 0.2, "acc_g": (0, 1.2, 0), "yaw_rate": 0.0, "lap": 2,
        "track": "monaco_2020",
        "tyre_temp": (90, 92, 88, 87),
    })
    lines = dash.build(
        frame=frame,
        phase="LEARNING",
        clean_laps=2,
        target_laps=3,
        total_laps=5,
        spline_indexer=idx,
        corner_name="Rascasse",
        corner_display="Rascasse",
        phase_name="entry",
        landmarks=idx.corner_landmarks("Rascasse"),
        upcoming_corner=None,
        sector="S3",
        lap_delta_s=0.0,
        worst_corners=[],
        reference_lap_ms=None,
        theoretical_best_ms=None,
        last_lap_ms=None,
        tyre_temps=frame.tyre_temp,
        tyre_ideal_lo=75,
        tyre_ideal_hi=95,
        tyre_hot_c=102,
        tyre_cold_c=68,
        driving_style={"aggression": 0.5},
        balance=None,
        bootstrap_active=False,
        track_display="Monaco",
        coach_text="",
        bucket_consistent=42,
        coaching_active=True,
        stint_ready=False,
    )
    assert "LEARNING" in lines["header"]
    assert "Rascasse" in lines["location"]
    assert "pool" in lines["hint"].lower()
    assert "Coaching active" in lines["pace"]
    assert "LF" in lines["tyres"]


def test_dashboard_tweaking_shows_worst_corner():
    idx = _monaco_indexer()
    dash = EngineerDashboard()
    frame = TelemetryIngest.frame_from_dict({
        "spline": 0.3, "speed_kmh": 200, "brake": 0.0, "throttle": 1.0,
        "steer": 0.0, "acc_g": (0, 0.5, 0), "yaw_rate": 0.0, "lap": 10,
        "track": "monaco_2020",
        "tyre_temp": (95, 96, 94, 93),
    })
    lines = dash.build(
        frame=frame,
        phase="TWEAKING",
        clean_laps=7,
        target_laps=7,
        total_laps=10,
        spline_indexer=idx,
        corner_name="",
        corner_display="",
        phase_name="straight",
        landmarks={},
        upcoming_corner=idx.upcoming_corner(0.3),
        sector="S2",
        lap_delta_s=0.15,
        worst_corners=[("Rascasse", 0.12)],
        reference_lap_ms=82000,
        theoretical_best_ms=81500,
        last_lap_ms=82150,
        tyre_temps=frame.tyre_temp,
        tyre_ideal_lo=75,
        tyre_ideal_hi=95,
        tyre_hot_c=102,
        tyre_cold_c=68,
        driving_style={"aggression": 0.6},
        balance=None,
        bootstrap_active=False,
        track_display="Monaco",
        coach_text="Rascasse — too fast on entry",
        bucket_consistent=80,
    )
    assert "Costliest: Rascasse" in lines["pace"]
    assert "too fast" in lines["coach"]
    assert "Next:" in lines["hint"] or "consistent" in lines["hint"].lower()
