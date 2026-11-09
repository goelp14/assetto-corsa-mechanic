import math

from balance_metrics import BalanceMetrics
from dynamics_math import DynamicsMath
from telemetry_ingest import TelemetryIngest


def _corner_frame(direction, steer_road_deg, speed=30.0, lat_g=1.2):
    return TelemetryIngest.frame_from_dict({
        "velocity": (0.0, 0.0, speed),
        "heading": 0.0,
        "steer_road": direction * math.radians(steer_road_deg),
        "yaw_rate": direction * lat_g * 9.81 / speed,
        "acc_g": (0.0, direction * lat_g, 0.0),
        "slip": (0.2, 0.2, 0.05, 0.05),
    })


def test_understeer_detection(thresholds):
    dm = DynamicsMath({"wheelbase_m": 3.65, "understeer_gradient_K": 0.005})
    bm = BalanceMetrics({"wheelbase_m": 3.65}, thresholds)
    frame = _corner_frame(1, 8.0, speed=60.0, lat_g=2.0)
    bal = bm.update(frame, dm.update(frame))
    assert bal.valid
    assert bm.delta_us_deg() > 0


def test_understeer_sign_matches_in_both_directions(thresholds):
    car = {"wheelbase_m": 2.4, "lat_g_base": 1.5, "lat_g_per_ms": 0.0}
    results = []
    for direction in (1, -1):
        dm = DynamicsMath(car)
        bm = BalanceMetrics(car, thresholds)
        frame = _corner_frame(direction, 6.0)
        bm.update(frame, dm.update(frame))
        results.append(bm.delta_us_deg())
    ack = math.degrees(2.4 * 1.2 * 9.81 / 30.0 ** 2)
    assert abs(results[0] - (6.0 - ack)) < 1e-6
    assert abs(results[0] - results[1]) < 1e-9


def test_non_aero_car_lateral_cap_ignores_speed(thresholds):
    bm = BalanceMetrics({"lat_g_base": 1.5, "lat_g_per_ms": 0.0}, thresholds)
    assert abs(bm._ay_max(60.0) - 1.5 * 9.81) < 1e-9
    aero = BalanceMetrics({}, thresholds)
    assert aero._ay_max(60.0) > 3.0 * 9.81
