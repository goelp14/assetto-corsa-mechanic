# ac_app/lib/phase_pace.py
# Always assume there is time left — chase seconds and hundredths per phase.


class PhasePaceCoach(object):
    """Find the next micro-gain in entry, mid, or exit."""

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {}

    def _t(self, key, default):
        return float(self.thresholds.get(key, default))

    def next_gain(self, summary, reference, corner_display="", potential_gap_s=0.0,
                  line_cfg=None):
        if not summary or not summary.get("phases"):
            return None
        ref_phases = reference.get("phases", {}) if reference else {}
        best = None
        best_score = 0.0

        for phase_name in ("entry", "mid", "exit"):
            phase = summary["phases"].get(phase_name, {})
            ref = ref_phases.get(phase_name, {})
            if phase.get("samples", 0) < 3:
                continue

            score, kind, detail = self._phase_opportunity(phase, ref, phase_name)
            if score > best_score:
                best_score = score
                best = {
                    "phase": phase_name,
                    "kind": kind,
                    "detail": detail,
                    "corner_name": corner_display,
                    "gain_s": self._estimate_gain_s(score, potential_gap_s),
                }

        if best is None and potential_gap_s > 0.001:
            return {
                "phase": "any",
                "kind": "micro",
                "corner_name": corner_display,
                "gain_s": "%.3f" % min(potential_gap_s, 0.5),
                "detail": "Every phase can still improve — even hundredths add up.",
            }
        if best is None:
            return None
        best["gain_s"] = "%.3f" % float(best["gain_s"])
        return best

    def _phase_opportunity(self, phase, ref, phase_name):
        score = 0.0
        kind = "grip"
        detail = ""

        peak_ay = phase.get("peak_ay_g", 0.0)
        ref_ay = ref.get("peak_ay_g", peak_ay)
        if ref_ay > 0.5 and peak_ay < ref_ay - self._t("PHASE_AY_GAP", 0.15):
            score = max(score, (ref_ay - peak_ay) * 2.0)
            kind = "grip"
            detail = "%s: %.2fG vs your %.2fG peak — more lateral grip available." % (
                phase_name.upper(), peak_ay, ref_ay,
            )

        min_spd = phase.get("min_speed_kmh", 0.0)
        ref_spd = ref.get("min_speed_kmh", min_spd)
        if ref_spd > 20 and min_spd < ref_spd - self._t("PHASE_SPEED_GAP_KMH", 2.0):
            spd_score = (ref_spd - min_spd) / 10.0
            if spd_score > score:
                score = spd_score
                kind = "speed"
                detail = "%s: %d km/h vs your %d km/h — line or throttle timing." % (
                    phase_name.upper(), int(min_spd), int(ref_spd),
                )

        if phase_name == "exit":
            rear_slip = phase.get("max_rear_slip", 0.0)
            if rear_slip > self._t("EXIT_SLIP_COACH", 0.1):
                slip_score = rear_slip * 3.0
                if slip_score > score:
                    score = slip_score
                    kind = "control"
                    detail = "EXIT: rear slip %.0f%% — maximize traction before full throttle." % (
                        rear_slip * 100.0,
                    )

        if phase_name == "entry" and phase.get("steer_corrections", 0) >= 2:
            corr_score = phase.get("steer_corrections", 0) * 0.15
            if corr_score > score:
                score = corr_score
                kind = "line"
                narrow = line_cfg and line_cfg.get("width_bias") == "narrow"
                if narrow:
                    detail = "ENTRY: %d corrections on a tight line — one steering input, stay on rubber." % (
                        phase.get("steer_corrections", 0),
                    )
                else:
                    detail = "ENTRY: %d steering corrections — fix approach width first." % (
                        phase.get("steer_corrections", 0),
                    )

        return score, kind, detail

    def _estimate_gain_s(self, score, potential_gap_s):
        est = min(0.15, score * 0.04)
        if potential_gap_s > 0:
            est = max(est, min(potential_gap_s * 0.25, 0.08))
        return max(est, 0.005)
