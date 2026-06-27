from telemetry_ingest import TelemetryIngest
from tyre_window import TyreWindowTracker


def _hot_lap_frame(temp_c, slip=0.15, speed=120.0, yaw_rate=0.0):
    return TelemetryIngest.frame_from_dict({
        "speed_kmh": speed,
        "throttle": 0.8,
        "brake": 0.0,
        "steer": 0.2,
        "acc_g": (0.0, 1.5, 0.0),
        "yaw_rate": yaw_rate,
        "tyre_temp": (temp_c, temp_c, temp_c - 5, temp_c - 5),
        "tyre_pressure": (24.0, 24.0, 23.0, 23.0),
        "slip": (slip, slip, slip * 0.8, slip * 0.8),
    })


def _drive_representative_lap(tracker, temp_c=108.0, slip=0.18):
    for _ in range(40):
        tracker.observe(_hot_lap_frame(temp_c, slip=slip))


def test_front_hot_aggressive_style_after_stint():
    tracker = TyreWindowTracker()
    tracker.set_compound("soft")
    _drive_representative_lap(tracker)
    assert tracker.finish_lap() == []

    _drive_representative_lap(tracker)
    diagnoses = tracker.finish_lap()
    assert len(diagnoses) >= 1
    assert diagnoses[0].symptom == "tyre_front_hot_aggressive"
    summary = tracker.last_summary()
    assert summary["tyres"]["LF"]["mean_temp_c"] > 100
    assert summary["stint_ready"] is True


def test_front_cold_conservative_style():
    tracker = TyreWindowTracker()
    diagnoses = []
    for _ in range(2):
        for _ in range(40):
            frame = _hot_lap_frame(60.0, slip=0.03, speed=90.0)
            frame.steer = 0.05
            tracker.observe(frame)
        diagnoses = tracker.finish_lap()
    assert any("cold" in d.symptom for d in diagnoses)
    style = tracker.last_summary()["style"]
    assert style["aggression"] < 0.4


def test_spin_lap_skips_tyre_diagnosis():
    tracker = TyreWindowTracker()
    _drive_representative_lap(tracker)
    tracker.finish_lap()

    for _ in range(20):
        tracker.observe(_hot_lap_frame(108.0, slip=0.35, yaw_rate=3.0))
    for _ in range(20):
        tracker.observe(_hot_lap_frame(108.0, slip=0.16))
    diagnoses = tracker.finish_lap()
    assert diagnoses == []
    assert tracker.last_summary()["lap_representative"] is False


def test_compound_overrides_window():
    tracker = TyreWindowTracker()
    tracker.set_compound("hard")
    lo, hi = tracker.ideal_temp_range()
    assert hi >= 95
