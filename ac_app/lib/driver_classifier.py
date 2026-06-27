# ac_app/lib/driver_classifier.py
# Python 3.3 compatible — stdlib only

try:
    from decision_engine import VERDICT_DRIVER_ERROR
except ImportError:
    from .decision_engine import VERDICT_DRIVER_ERROR


class DriverClassification(object):
    __slots__ = ("template_key", "evidence")

    def __init__(self, template_key, evidence):
        self.template_key = template_key
        self.evidence = evidence


class DriverClassifier(object):
    """Map DRIVER_ERROR verdicts to feedback template keys."""

    def __init__(self, thresholds=None, investigator=None):
        self.thresholds = thresholds or {}
        self._investigator = investigator

    def _thresh(self, key, default):
        return self.thresholds.get(key, default)

    def classify(self, decision, frame, baseline_bucket=None, corner="",
                 summary=None, reference=None, landmarks=None, line_cfg=None,
                 yaw_gate=None):
        if decision.verdict != VERDICT_DRIVER_ERROR:
            return None

        evidence = dict(decision.evidence)
        evidence["corner"] = corner or decision.corner

        if self._investigator is not None and summary:
            inv = self._investigator.investigate(
                summary, reference or {}, frame=frame, corner=corner or decision.corner,
                landmarks=landmarks, line_cfg=line_cfg, yaw_gate=yaw_gate,
            )
            if inv is not None:
                ev = dict(inv.evidence)
                ev.update(evidence)
                return DriverClassification(inv.template_key, ev)

        if baseline_bucket is not None and baseline_bucket.sample_count >= 3:
            speed_tol = self._thresh("INPUT_SPEED_TOL_KMH", 5.0)
            ref_speed = baseline_bucket.peak_speed
            if ref_speed < 25.0:
                ref_speed = baseline_bucket.mean_speed
            if ref_speed < 25.0:
                ref_speed = 0.0
            speed_delta = frame.speed_kmh - ref_speed
            evidence["speed_delta_kmh"] = int(round(speed_delta))
            evidence["ref_speed_kmh"] = int(round(ref_speed))

            if ref_speed > 0 and speed_delta > speed_tol:
                evidence["brake_later_m"] = 10
                return DriverClassification("overspeed", evidence)

            if frame.brake > baseline_bucket.mean_brake + 0.15:
                early_m = 15
                evidence["early_m"] = early_m
                evidence["wait_s"] = "0.2"
                evidence["gain_kmh"] = 4
                evidence["gain_s"] = "0.1"
                return DriverClassification("early_brake", evidence)

        if frame.throttle > 0.5 and abs(frame.acc_g[1]) > 1.5:
            return DriverClassification("early_throttle", evidence)

        if decision.phase == "entry" and frame.brake > 0.2:
            evidence["early_m"] = 10
            evidence["wait_s"] = "0.15"
            evidence["gain_kmh"] = 3
            evidence["gain_s"] = "0.08"
            return DriverClassification("early_brake", evidence)

        return None
