import math

from dynamics_math import DynamicsMath
from telemetry_ingest import TelemetryIngest


def test_body_slip_and_yaw_ref():
    dm = DynamicsMath({
        "wheelbase_m": 3.65,
        "cg_to_front_axle_m": 1.65,
        "cg_to_rear_axle_m": 2.0,
        "understeer_gradient_K": 0.005,
    })
    frame = TelemetryIngest.frame_from_dict({
        "velocity": (50.0, 5.0, 0.0),
        "heading": 0.1,
        "steer": 0.05,
        "yaw_rate": 0.2,
        "yaw_accel": 0.0,
        "acc_g": (0.0, 1.0, 0.0),
    })
    st = dm.update(frame)
    assert st.vx > 0
    assert abs(st.beta) < math.pi / 2
    assert st.yaw_rate_ref != 0.0
