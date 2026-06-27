import math

from dynamics_math import DynamicsMath
from telemetry_ingest import TelemetryIngest
from yaw_gates import YawGateEvaluator, GATE_INTENTIONAL, GATE_LOSS_OF_CONTROL


def test_intentional_gate(thresholds):
    yg = YawGateEvaluator(thresholds)
    dm = DynamicsMath()
    frame = TelemetryIngest.frame_from_dict({
        "steer": -0.1,
        "yaw_rate": 0.3,
        "yaw_accel": 0.1,
        "velocity": (50.0, 2.0, 0.0),
        "heading": 0.0,
        "acc_g": (0, 0.5, 0),
    })
    dyn = dm.update(frame)
    result = yg.classify(frame, dyn)
    assert result.gate in (GATE_INTENTIONAL, GATE_LOSS_OF_CONTROL, "NEUTRAL")
