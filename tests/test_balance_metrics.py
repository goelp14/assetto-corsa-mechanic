from balance_metrics import BalanceMetrics
from dynamics_math import DynamicsMath
from telemetry_ingest import TelemetryIngest


def test_understeer_detection(thresholds):
    dm = DynamicsMath({"wheelbase_m": 3.65, "understeer_gradient_K": 0.005})
    bm = BalanceMetrics({"wheelbase_m": 3.65}, thresholds)
    frame = TelemetryIngest.frame_from_dict({
        "velocity": (60.0, 0.0, 0.0),
        "heading": 0.0,
        "steer": 0.15,
        "yaw_rate": 0.1,
        "acc_g": (0.0, 2.0, 0.0),
        "slip": (0.2, 0.2, 0.05, 0.05),
    })
    dyn = dm.update(frame)
    bal = bm.update(frame, dyn)
    assert bal.valid
    assert bm.delta_us_deg() != 0
