import math

from dynamics_math import DynamicsMath
from telemetry_ingest import TelemetryIngest


def _forward(heading, speed, slip_deg=0.0):
    """World velocity (x, y, z) for a car with this heading, travelling slip_deg right of its nose."""
    travel = heading + math.pi / 2.0 + math.radians(slip_deg)
    return (speed * math.cos(travel), 0.0, speed * math.sin(travel))


def test_body_slip_and_yaw_ref():
    dm = DynamicsMath({
        "wheelbase_m": 3.65,
        "cg_to_front_axle_m": 1.65,
        "cg_to_rear_axle_m": 2.0,
        "understeer_gradient_K": 0.005,
    })
    frame = TelemetryIngest.frame_from_dict({
        "velocity": _forward(0.1, 50.0, slip_deg=4.0),
        "heading": 0.1,
        "steer_road": 0.05,
        "yaw_rate": 0.2,
        "yaw_accel": 0.0,
        "acc_g": (0.0, 1.0, 0.0),
    })
    st = dm.update(frame)
    assert abs(st.vx - 50.0 * math.cos(math.radians(4.0))) < 1e-6
    assert abs(math.degrees(st.beta) - 4.0) < 1e-6
    assert st.yaw_rate_ref > 0.0


def test_vertical_velocity_does_not_create_slip():
    dm = DynamicsMath({"wheelbase_m": 2.4})
    frame = TelemetryIngest.frame_from_dict({
        "velocity": (0.0, 3.0, 40.0),
        "heading": 0.0,
        "acc_g": (0.0, 0.0, 0.0),
    })
    st = dm.update(frame)
    assert abs(st.beta) < 1e-9
    assert abs(st.vx - 40.0) < 1e-9
