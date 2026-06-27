# ac_app/lib/corner_phase_metrics.py
# Per-corner phase aggregates for symptom detection (Python 3.3).

import math

try:
    from surface_event_detector import SurfacePhaseStats
except ImportError:
    from .surface_event_detector import SurfacePhaseStats

PHASES = ("entry", "mid", "exit")


class _PhaseStats(object):
    __slots__ = (
        "n", "delta_us_sum", "peak_ay", "min_speed", "max_throttle",
        "brake_sum", "load_f_sum", "load_r_sum", "max_rear_slip",
        "max_front_slip", "max_susp_pct", "yaw_err_sum", "peak_beta_deg",
        "load_imbalance_sum", "steer_abs_sum", "steer_corrections",
        "_last_steer_sign", "_surface",
    )

    def __init__(self):
        self.n = 0
        self.delta_us_sum = 0.0
        self.peak_ay = 0.0
        self.min_speed = 9999.0
        self.max_throttle = 0.0
        self.brake_sum = 0.0
        self.load_f_sum = 0.0
        self.load_r_sum = 0.0
        self.max_rear_slip = 0.0
        self.max_front_slip = 0.0
        self.max_susp_pct = 0.0
        self.yaw_err_sum = 0.0
        self.peak_beta_deg = 0.0
        self.load_imbalance_sum = 0.0
        self.steer_abs_sum = 0.0
        self.steer_corrections = 0
        self._last_steer_sign = 0
        self._surface = SurfacePhaseStats()

    def observe(self, frame, dynamics, balance, thresholds=None):
        self.n += 1
        ay = abs(frame.acc_g[1])
        if ay > self.peak_ay:
            self.peak_ay = ay
        if frame.speed_kmh < self.min_speed:
            self.min_speed = frame.speed_kmh
        if frame.throttle > self.max_throttle:
            self.max_throttle = frame.throttle
        self.brake_sum += frame.brake
        self.steer_abs_sum += abs(frame.steer)
        steer_sign = 1 if frame.steer > 0.02 else (-1 if frame.steer < -0.02 else 0)
        if (
            steer_sign != 0
            and self._last_steer_sign != 0
            and steer_sign != self._last_steer_sign
        ):
            self.steer_corrections += 1
        if steer_sign != 0:
            self._last_steer_sign = steer_sign
        if balance is not None and balance.valid:
            self.delta_us_sum += balance.delta_us
            self.load_imbalance_sum += getattr(balance, "load_balance", 0.0)
        if dynamics is not None:
            self.yaw_err_sum += abs(dynamics.yaw_rate_err)
            beta = abs(math.degrees(dynamics.beta))
            if beta > self.peak_beta_deg:
                self.peak_beta_deg = beta
        loads = getattr(frame, "wheel_load", None)
        if loads and len(loads) >= 4:
            lf, rf, lr, rr = loads[0], loads[1], loads[2], loads[3]
            self.load_f_sum += lf + rf
            self.load_r_sum += lr + rr
        slips = getattr(frame, "slip_ratio", frame.slip)
        if slips and len(slips) >= 4:
            front = (slips[0] + slips[1]) * 0.5
            rear = (slips[2] + slips[3]) * 0.5
            if front > self.max_front_slip:
                self.max_front_slip = front
            if rear > self.max_rear_slip:
                self.max_rear_slip = rear
        ratios = getattr(frame, "susp_ratio", None)
        if ratios:
            for r in ratios:
                if r > self.max_susp_pct:
                    self.max_susp_pct = r
        self._surface.observe(frame, dynamics, balance, thresholds or {})

    def mean_delta_us_deg(self):
        if self.n == 0:
            return 0.0
        return math.degrees(self.delta_us_sum / float(self.n))

    def mean_load_imbalance(self):
        if self.n == 0:
            return 0.0
        return self.load_imbalance_sum / float(self.n)

    def to_dict(self):
        data = {
            "samples": self.n,
            "mean_delta_us_deg": round(self.mean_delta_us_deg(), 2),
            "peak_ay_g": round(self.peak_ay, 3),
            "min_speed_kmh": round(self.min_speed, 1) if self.min_speed < 9999 else 0.0,
            "max_throttle": round(self.max_throttle, 3),
            "mean_brake": round(self.brake_sum / float(max(self.n, 1)), 3),
            "max_rear_slip": round(self.max_rear_slip, 3),
            "max_front_slip": round(self.max_front_slip, 3),
            "max_susp_pct": round(self.max_susp_pct, 3),
            "mean_yaw_err": round(self.yaw_err_sum / float(max(self.n, 1)), 4),
            "peak_beta_deg": round(self.peak_beta_deg, 1),
            "mean_load_imbalance": round(self.mean_load_imbalance(), 4),
            "mean_steer_abs": round(self.steer_abs_sum / float(max(self.n, 1)), 4),
            "steer_corrections": self.steer_corrections,
        }
        data["surface"] = self._surface.to_dict()
        return data


class StraightStats(object):
    __slots__ = ("n", "max_speed", "yaw_err_sum", "peak_beta_deg")

    def __init__(self):
        self.n = 0
        self.max_speed = 0.0
        self.yaw_err_sum = 0.0
        self.peak_beta_deg = 0.0

    def observe(self, frame, dynamics):
        self.n += 1
        if frame.speed_kmh > self.max_speed:
            self.max_speed = frame.speed_kmh
        if dynamics is not None:
            self.yaw_err_sum += abs(dynamics.yaw_rate_err)
            beta = abs(math.degrees(dynamics.beta))
            if beta > self.peak_beta_deg:
                self.peak_beta_deg = beta

    def to_dict(self):
        return {
            "samples": self.n,
            "max_speed_kmh": round(self.max_speed, 1),
            "mean_yaw_err": round(self.yaw_err_sum / float(max(self.n, 1)), 4),
            "peak_beta_deg": round(self.peak_beta_deg, 1),
        }


class CornerPhaseMetrics(object):
    """Accumulate per-phase stats while in a corner; finalize on exit."""

    def __init__(self, thresholds=None):
        self._corner = ""
        self._phases = {}
        self._straight = StraightStats()
        self._straight_window = 0
        self._thresholds = thresholds or {}

    def _phase_bucket(self, phase):
        key = phase if phase in PHASES else "mid"
        if key not in self._phases:
            self._phases[key] = _PhaseStats()
        return self._phases[key]

    def observe(self, corner, phase, frame, dynamics, balance):
        if corner:
            if corner != self._corner:
                self._corner = corner
                self._phases = {}
            self._phase_bucket(phase).observe(frame, dynamics, balance, self._thresholds)
            self._straight_window = 0
            return
        self._observe_straight(frame, dynamics)

    def _observe_straight(self, frame, dynamics):
        if frame.speed_kmh < 120.0:
            self._straight_window = 0
            return
        self._straight_window += 1
        if self._straight_window >= 3:
            self._straight.observe(frame, dynamics)

    def finalize(self, corner):
        if corner != self._corner:
            return None
        summary = {
            "corner": corner,
            "phases": {},
        }
        surface = {
            "kerb_contacts": 0, "kerb_grip_loss": 0, "bump_hits": 0,
            "platform_hops": 0, "painted_kerb_slip": 0,
            "max_vert_g": 0.0, "max_load_drop_pct": 0.0, "max_susp_pct": 0.0,
        }
        for phase in PHASES:
            if phase in self._phases and self._phases[phase].n > 0:
                pdata = self._phases[phase].to_dict()
                summary["phases"][phase] = pdata
                surf = pdata.get("surface", {})
                for key in surface:
                    if key.startswith("max_"):
                        surface[key] = max(surface[key], surf.get(key, 0.0))
                    else:
                        surface[key] += surf.get(key, 0)
        summary["surface"] = surface
        self._corner = ""
        self._phases = {}
        return summary if summary["phases"] else None

    def merged_surface(self, corner):
        """Combine surface stats across all phases for a corner."""
        if corner != self._corner:
            return {}
        merged = {
            "kerb_contacts": 0, "kerb_grip_loss": 0, "bump_hits": 0,
            "platform_hops": 0, "painted_kerb_slip": 0,
            "max_vert_g": 0.0, "max_load_drop_pct": 0.0, "max_susp_pct": 0.0,
        }
        for phase in self._phases.values():
            surf = phase.to_dict().get("surface", {})
            for key in merged:
                if key.startswith("max_"):
                    merged[key] = max(merged[key], surf.get(key, 0.0))
                else:
                    merged[key] += surf.get(key, 0)
        return merged

    def consume_straight(self):
        if self._straight.n < 5:
            return None
        data = self._straight.to_dict()
        self._straight = StraightStats()
        self._straight_window = 0
        return data

    def reset_lap(self):
        self._corner = ""
        self._phases = {}
        self._straight = StraightStats()
        self._straight_window = 0
