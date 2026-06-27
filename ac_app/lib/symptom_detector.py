# ac_app/lib/symptom_detector.py
# Map phase aggregates to setup/coaching symptoms (Python 3.3).

try:
    from surface_event_detector import primary_surface_symptom
except ImportError:
    from .surface_event_detector import primary_surface_symptom


class SymptomHit(object):
    __slots__ = ("symptom", "phase", "confidence", "evidence")

    def __init__(self, symptom, phase="any", confidence=0.5, evidence=None):
        self.symptom = symptom
        self.phase = phase
        self.confidence = confidence
        self.evidence = evidence or {}


class SymptomDetector(object):
    """Rule-based symptom detection from corner phase summaries."""

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {}

    def _t(self, key, default):
        return float(self.thresholds.get(key, default))

    def detect_corner(self, summary, speed_class="medium"):
        if not summary or not summary.get("phases"):
            return []
        hits = []
        phases = summary["phases"]
        entry = phases.get("entry", {})
        mid = phases.get("mid", {})
        exit_p = phases.get("exit", {})

        if entry.get("samples", 0) >= 3:
            d_us = entry.get("mean_delta_us_deg", 0.0)
            if d_us > self._t("ENTRY_US_DEG", 2.0) and entry.get("mean_brake", 0) > 0.15:
                hits.append(SymptomHit(
                    "entry_understeer", "entry", 0.7, dict(entry),
                ))
            rear_slip = entry.get("max_rear_slip", 0.0)
            front_slip = entry.get("max_front_slip", 0.0)
            if rear_slip > front_slip + self._t("ENTRY_SLIP_DELTA", 0.06):
                if entry.get("peak_beta_deg", 0) > self._t("ENTRY_OS_BETA_DEG", 8.0):
                    hits.append(SymptomHit(
                        "entry_oversteer", "entry", 0.75, dict(entry),
                    ))
            if entry.get("mean_brake", 0) > 0.35 and rear_slip > self._t("BRAKE_REAR_SLIP", 0.12):
                hits.append(SymptomHit(
                    "rear_unstable_braking", "entry", 0.7, dict(entry),
                ))

        if mid.get("samples", 0) >= 3:
            d_us = mid.get("mean_delta_us_deg", 0.0)
            if d_us > self._t("MID_US_DEG", 2.0):
                hits.append(SymptomHit("mid_understeer", "mid", 0.8, dict(mid)))
            elif d_us < -self._t("MID_OS_DEG", 2.0):
                hits.append(SymptomHit("mid_oversteer", "mid", 0.8, dict(mid)))
            imb = mid.get("mean_load_imbalance", 0.0)
            if imb > self._t("MID_LOAD_F_BIAS", 0.08) and d_us > 1.0:
                hits.append(SymptomHit("mid_understeer", "mid", 0.65, dict(mid)))

        if exit_p.get("samples", 0) >= 3:
            if (
                exit_p.get("max_throttle", 0) > 0.45
                and exit_p.get("max_rear_slip", 0) > self._t("EXIT_WHEELSPIN_SLIP", 0.14)
            ):
                hits.append(SymptomHit(
                    "exit_wheelspin", "exit", 0.85, dict(exit_p),
                ))
            d_us = exit_p.get("mean_delta_us_deg", 0.0)
            if d_us < -self._t("EXIT_OS_DEG", 2.0):
                hits.append(SymptomHit("exit_oversteer", "exit", 0.75, dict(exit_p)))

        for phase_name, pdata in phases.items():
            if pdata.get("max_susp_pct", 0) > self._t("KERB_SUSP_PCT", 0.85):
                ev = dict(pdata)
                ev["phase"] = phase_name
                hits.append(SymptomHit(
                    "kerb_instability", "any", 0.6,
                    ev,
                ))
                break

        surface = summary.get("surface", {})
        if not surface:
            for pdata in phases.values():
                surface = pdata.get("surface", {})
                if surface:
                    break
        surf_hit = primary_surface_symptom(surface, self.thresholds)
        if surf_hit is not None:
            symptom, conf, detail = surf_hit
            hits.append(SymptomHit(
                symptom, "mid", conf,
                {"surface_detail": detail, "surface": surface},
            ))

        if speed_class == "high" and mid.get("peak_ay_g", 0) > 2.0:
            if mid.get("mean_yaw_err", 0) > self._t("HIGH_SPEED_YAW_ERR", 0.12):
                hits.append(SymptomHit(
                    "high_speed_instability", "straight", 0.7, dict(mid),
                ))

        hits.sort(key=lambda h: h.confidence, reverse=True)
        return hits

    def detect_straight(self, straight_summary):
        if not straight_summary:
            return []
        hits = []
        if straight_summary.get("max_speed_kmh", 0) >= self._t("HIGH_SPEED_KMH", 200.0):
            if straight_summary.get("mean_yaw_err", 0) > self._t("HIGH_SPEED_YAW_ERR", 0.12):
                hits.append(SymptomHit(
                    "high_speed_instability", "straight", 0.8, dict(straight_summary),
                ))
            if straight_summary.get("peak_beta_deg", 0) > self._t("HIGH_SPEED_BETA_DEG", 6.0):
                hits.append(SymptomHit(
                    "high_speed_instability", "straight", 0.7, dict(straight_summary),
                ))
        return hits

    def primary(self, summary, speed_class="medium", straight_summary=None):
        hits = self.detect_corner(summary, speed_class)
        if not hits and straight_summary:
            hits = self.detect_straight(straight_summary)
        if not hits:
            return None
        return hits[0]
