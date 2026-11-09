# ac_app/lib/dynamics_math.py
# Python 3.3 compatible — stdlib only

import math

RING_SIZE = 5


class DynamicsState(object):
    __slots__ = (
        "vx", "vy", "beta", "alpha_f", "alpha_r",
        "yaw_rate_ref", "yaw_rate_err", "yaw_accel_filt",
    )

    def __init__(self):
        self.vx = 0.0
        self.vy = 0.0
        self.beta = 0.0
        self.alpha_f = 0.0
        self.alpha_r = 0.0
        self.yaw_rate_ref = 0.0
        self.yaw_rate_err = 0.0
        self.yaw_accel_filt = 0.0


class DynamicsMath(object):
    """Yaw kinematics, body slip, and bicycle-model reference yaw rate."""

    def __init__(self, car_config=None, ring_size=RING_SIZE):
        self.l_f = 1.65
        self.l_r = 2.0
        self.wheelbase = 3.65
        self.K = 0.005
        self.ring_size = ring_size
        self._yaw_accel_ring = [0.0] * ring_size
        self._ring_idx = 0
        self._state = DynamicsState()
        if car_config:
            self.load_car_config(car_config)

    def load_car_config(self, car_config):
        self.l_f = car_config.get("cg_to_front_axle_m", self.l_f)
        self.l_r = car_config.get("cg_to_rear_axle_m", self.l_r)
        self.wheelbase = car_config.get("wheelbase_m", self.l_f + self.l_r)
        self.K = car_config.get("understeer_gradient_K", self.K)

    def _body_velocity(self, velocity, heading):
        """World velocity (x, y up, z) -> (forward, rightward) in m/s.

        AC heading points the car along world (-sin h, cos h) in the x/z plane
        and increases when turning right.
        """
        vx_w = velocity[0]
        vz_w = velocity[2] if len(velocity) > 2 else 0.0
        s = math.sin(heading)
        c = math.cos(heading)
        forward = -vx_w * s + vz_w * c
        right = -vx_w * c - vz_w * s
        return forward, right

    def _push_ring(self, value):
        self._yaw_accel_ring[self._ring_idx] = value
        self._ring_idx = (self._ring_idx + 1) % self.ring_size

    def _median_yaw_accel(self):
        vals = sorted(self._yaw_accel_ring)
        return vals[self.ring_size // 2]

    def update(self, frame):
        st = self._state
        st.vx, st.vy = self._body_velocity(frame.velocity, frame.heading)
        speed = math.sqrt(st.vx * st.vx + st.vy * st.vy)
        if speed > 0.5:
            st.beta = math.atan2(st.vy, st.vx)
        else:
            st.beta = 0.0

        # Lateral axis, steer and yaw rate are all + to the right, so the
        # textbook (left-positive) bicycle relations hold unchanged.
        steer = getattr(frame, "steer_road", 0.0)
        if abs(st.vx) > 1.0:
            st.alpha_f = (st.vy + self.l_f * frame.yaw_rate) / st.vx - steer
            st.alpha_r = (st.vy - self.l_r * frame.yaw_rate) / st.vx
        else:
            st.alpha_f = 0.0
            st.alpha_r = 0.0

        ay = abs(frame.acc_g[1]) * 9.81
        denom = 1.0 + self.K * ay
        if abs(denom) < 1e-6:
            denom = 1e-6
        if abs(st.vx) > 1.0:
            st.yaw_rate_ref = (st.vx / self.wheelbase) * math.tan(steer / denom)
        else:
            st.yaw_rate_ref = 0.0

        st.yaw_rate_err = frame.yaw_rate - st.yaw_rate_ref
        self._push_ring(frame.yaw_accel)
        st.yaw_accel_filt = self._median_yaw_accel()
        return st

    @property
    def state(self):
        return self._state

    def beta_deg(self):
        return math.degrees(self._state.beta)

    def derivative(self, values, dt):
        """Simple central difference over a short list."""
        if len(values) < 2 or dt <= 0:
            return 0.0
        return (values[-1] - values[0]) / (dt * float(len(values) - 1))
