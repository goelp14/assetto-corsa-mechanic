from telemetry_ingest import TelemetryIngest
from shift_analyzer import ShiftAnalyzer, DIRECTION_DOWN, DIRECTION_UP


def _frame(gear=3, rpm=8000, brake=0.0, throttle=0.5, steer=0.0, lat_g=0.0, lap=1):
    return TelemetryIngest.frame_from_dict({
        "spline": 0.2,
        "speed_kmh": 180.0,
        "brake": brake,
        "throttle": throttle,
        "steer": steer,
        "acc_g": (0.0, lat_g, 0.0),
        "yaw_rate": 0.0,
        "slip_ratio": (0.02, 0.02, 0.03, 0.03),
        "lap": lap,
        "gear": gear,
        "rpm": rpm,
    })


def test_good_downshift_in_brake_zone(thresholds):
    sa = ShiftAnalyzer(thresholds=thresholds)
    sa.observe(_frame(gear=4), "Turn 1", "entry")
    finalized = None
    for _ in range(int(thresholds.get("SHIFT_FOLLOWUP_FRAMES", 5)) + 1):
        finalized = sa.observe(_frame(gear=3, brake=0.6, lat_g=0.1), "Turn 1", "entry")
    assert finalized is not None
    assert finalized.quality == "good"
    assert finalized.direction == DIRECTION_DOWN


def test_unsettling_downshift_mid_corner(thresholds):
    sa = ShiftAnalyzer(thresholds=thresholds)
    sa.observe(_frame(gear=4, steer=0.25, lat_g=0.8), "Turn 4", "mid")
    finalized = None
    for i in range(int(thresholds.get("SHIFT_FOLLOWUP_FRAMES", 5)) + 1):
        slip = 0.03 + i * 0.02
        f = _frame(gear=3, steer=0.25, lat_g=0.8, throttle=0.2)
        f.slip_ratio = (0.02, 0.02, slip, slip)
        f.yaw_rate = i * 0.15
        finalized = sa.observe(f, "Turn 4", "mid")
    assert finalized is not None
    assert finalized.quality == "bad"
    assert finalized.template_key in (
        "shift_unsettling_downshift", "shift_harsh_downshift", "shift_late_downshift",
    )


def test_upshift_on_straight_is_good(thresholds):
    sa = ShiftAnalyzer(thresholds=thresholds)
    sa.observe(_frame(gear=5, throttle=0.9), "", "straight")
    finalized = None
    for _ in range(int(thresholds.get("SHIFT_FOLLOWUP_FRAMES", 5)) + 1):
        finalized = sa.observe(_frame(gear=6, throttle=0.95), "", "straight")
    assert finalized is not None
    assert finalized.quality == "good"
    assert finalized.direction == DIRECTION_UP


def test_lap_summary_counts(thresholds):
    sa = ShiftAnalyzer(thresholds=thresholds)
    sa.observe(_frame(gear=5), "", "straight")
    for _ in range(int(thresholds.get("SHIFT_FOLLOWUP_FRAMES", 5)) + 1):
        sa.observe(_frame(gear=6, throttle=0.9), "", "straight")
    summary = sa.lap_summary()
    assert summary["total_shifts"] == 1
    assert summary["settling_shifts"] == 1
    assert sa.hud_line().startswith("G6")
