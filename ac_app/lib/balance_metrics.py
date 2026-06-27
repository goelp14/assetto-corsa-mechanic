# ac_app/lib/balance_metrics.py
# Python 3.3 compatible — stdlib only

import math

G = 9.81


class BalanceState(object):
    __slots__ = (
        "delta_ack", "delta_us", "slip_balance", "alpha_slip_balance",
        "load_balance", "ay_efficiency",
        "ay_actual", "k_est", "valid",
    )

    def __init__(self):
        self.delta_ack = 0.0
        self.delta_us = 0.0
        self.slip_balance = 0.0
        self.alpha_slip_balance = 0.0
        self.load_balance = 0.0
        self.ay_efficiency = 1.0
        self.ay_actual = 0.0
        self.k_est = 0.005
        self.valid = False


class BalanceMetrics(object):
    """Understeer angle, lateral-G efficiency, slip balance."""

    def __init__(self, car_config=None, thresholds=None):
        self.wheelbase = 3.65
        self.K = 0.005
        self.max_yaw_rate = 1.2
        self.thresholds = thresholds or {}
        self._k_history = []
        self._k_history_max = 30
        self._state = BalanceState()
        if car_config:
            self.wheelbase = car_config.get("wheelbase_m", self.wheelbase)
            self.K = car_config.get("understeer_gradient_K", self.K)
            self.max_yaw_rate = car_config.get("max_yaw_rate_rad_s", self.max_yaw_rate)

    def _thresh(self, key, default):
        return self.thresholds.get(key, default)

    def _ay_max(self, speed_ms):
        if speed_ms < 5.0:
            return G * 4.0
        lat_g_cap = min(6.0, 1.5 + speed_ms / 30.0)
        return lat_g_cap * G

    def update(self, frame, dynamics_state):
        st = self._state
        st.valid = False
        vx = dynamics_state.vx
        speed_ms = math.sqrt(vx * vx + dynamics_state.vy * dynamics_state.vy)
        min_speed = self._thresh("MIN_SPEED_FOR_BALANCE_MS", 15.0)
        min_ay = self._thresh("MIN_AY_FOR_BALANCE_G", 0.3)
        ay = frame.acc_g[1] * G
        st.ay_actual = ay

        if speed_ms < min_speed or abs(frame.acc_g[1]) < min_ay:
            return st

        st.valid = True
        if abs(vx) > 1.0:
            st.delta_ack = self.wheelbase * ay / (vx * vx)
        else:
            st.delta_ack = 0.0
        st.delta_us = frame.steer - st.delta_ack

        st.alpha_slip_balance = dynamics_state.alpha_f - dynamics_state.alpha_r
        slip = frame.slip
        front_slip = (slip[0] + slip[1]) * 0.5
        rear_slip = (slip[2] + slip[3]) * 0.5
        st.slip_balance = front_slip - rear_slip

        loads = getattr(frame, "wheel_load", None)
        if loads and len(loads) >= 4 and sum(loads) > 10.0:
            front = loads[0] + loads[1]
            rear = loads[2] + loads[3]
            total = front + rear
            if total > 1.0:
                st.load_balance = (front - rear) / total

        ay_max = self._ay_max(speed_ms)
        if ay_max > 0:
            st.ay_efficiency = min(1.5, abs(ay) / ay_max)
        else:
            st.ay_efficiency = 1.0

        if abs(ay) > 0.5:
            k_sample = st.delta_us / ay
            self._k_history.append(k_sample)
            if len(self._k_history) > self._k_history_max:
                self._k_history.pop(0)
            sorted_k = sorted(self._k_history)
            st.k_est = sorted_k[len(sorted_k) // 2]

        return st

    @property
    def state(self):
        return self._state

    def delta_us_deg(self):
        return math.degrees(self._state.delta_us)

    def symptom_from_balance(self):
        st = self._state
        if not st.valid:
            return None
        us_thresh = self._thresh("DELTA_US_UNDERSTEER_DEG", 2.0)
        os_thresh = self._thresh("DELTA_US_OVERSTEER_DEG", -2.0)
        delta_deg = math.degrees(st.delta_us)
        ay_min = self._thresh("AY_EFFICIENCY_MIN", 0.92)
        if delta_deg > us_thresh or st.ay_efficiency < ay_min:
            return "mid_understeer"
        if delta_deg < os_thresh:
            return "mid_oversteer"
        return None
