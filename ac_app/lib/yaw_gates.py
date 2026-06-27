# ac_app/lib/yaw_gates.py
# Python 3.3 compatible — stdlib only

import math

GATE_INTENTIONAL = "INTENTIONAL"
GATE_LOSS_OF_CONTROL = "LOSS_OF_CONTROL"
GATE_NEUTRAL = "NEUTRAL"


class YawGateResult(object):
    __slots__ = ("gate", "confidence")

    def __init__(self, gate, confidence):
        self.gate = gate
        self.confidence = confidence


class YawGateEvaluator(object):
    """Classify yaw behaviour: intentional rotation vs loss of control."""

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {}
        self._prev_yaw_err = 0.0

    def _thresh(self, key, default):
        return self.thresholds.get(key, default)

    @staticmethod
    def _counter_steer_active(steer, yaw_rate):
        return (steer > 0.02 and yaw_rate < -0.05) or (steer < -0.02 and yaw_rate > 0.05)

    def classify(self, frame, dynamics_state):
        yaw_err = abs(dynamics_state.yaw_rate_err)
        yaw_accel = abs(dynamics_state.yaw_accel_filt)
        beta_deg = abs(math.degrees(dynamics_state.beta))

        err_thresh = self._thresh("YAW_ERR_THRESH", 0.15)
        accel_stable = self._thresh("YAW_ACCEL_STABLE", 0.5)
        accel_critical = self._thresh("YAW_ACCEL_CRITICAL", 2.0)
        beta_intent = self._thresh("BETA_INTENTIONAL_MAX_DEG", 25.0)
        beta_terminal = self._thresh("BETA_TERMINAL_DEG", 35.0)

        growing_err = abs(dynamics_state.yaw_rate_err) > abs(self._prev_yaw_err)
        self._prev_yaw_err = dynamics_state.yaw_rate_err

        if yaw_accel > accel_critical or beta_deg > beta_terminal:
            conf = min(1.0, yaw_accel / accel_critical)
            return YawGateResult(GATE_LOSS_OF_CONTROL, conf)

        opp_lock = self._counter_steer_active(frame.steer, frame.yaw_rate)
        if opp_lock and growing_err and yaw_err > err_thresh:
            return YawGateResult(GATE_LOSS_OF_CONTROL, 0.75)

        if (
            yaw_err > err_thresh
            and self._counter_steer_active(frame.steer, frame.yaw_rate)
            and yaw_accel < accel_stable
            and beta_deg < beta_intent
        ):
            conf = min(1.0, yaw_err / (err_thresh * 2.0))
            return YawGateResult(GATE_INTENTIONAL, conf)

        return YawGateResult(GATE_NEUTRAL, 0.5)
