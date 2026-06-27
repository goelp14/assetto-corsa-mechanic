# ac_app/lib/session_analyst.py
# Post-lap digest: your pace vs your potential (no alien telemetry).

import math


def _fmt_lap(ms):
    if not ms or ms < 1000:
        return "--:--.---"
    total_s = ms / 1000.0
    minutes = int(total_s // 60)
    seconds = total_s - minutes * 60
    return "%d:%06.3f" % (minutes, seconds)


class SessionAnalyst(object):
    """Synthesize lap insights from personal references only."""

    def summarize_lap(
        self,
        lap_time_ms,
        lap_analyzer,
        driving_style,
        corner_deltas,
        clean_lap,
        setup_pending=None,
    ):
        if not lap_time_ms or lap_time_ms < 1000:
            return None

        ref_ms = lap_analyzer.reference_lap_ms()
        potential_ms = lap_analyzer.theoretical_best_ms()
        potential_gap_s = 0.0
        if potential_ms and potential_ms > 0:
            potential_gap_s = max(0.0, (lap_time_ms - potential_ms) / 1000.0)

        ref_gap_s = 0.0
        if ref_ms and ref_ms > 0:
            ref_gap_s = (lap_time_ms - ref_ms) / 1000.0

        worst = []
        if corner_deltas:
            items = [(n, d) for n, d in corner_deltas.items() if d >= 0.03]
            items.sort(key=lambda x: x[1], reverse=True)
            worst = items[:3]

        style = driving_style or {}
        agg = style.get("aggression", 0.5)
        cons = style.get("consistency", 0.5)
        if agg >= 0.58:
            style_label = "aggressive"
            style_tip = "You carry speed with slip — smooth entries will unlock the next tenth."
        elif agg < 0.38:
            style_label = "smooth"
            style_tip = "Clean inputs — push brake markers deeper where you have grip left."
        else:
            style_label = "balanced"
            style_tip = "Solid base — fix the slowest corners first for free time."

        gain_action = "Repeat your reference markers at the costliest corner."
        if worst:
            name, delta = worst[0]
            gain_action = "%s costs +%.2fs — match your own best segment there." % (
                name, delta,
            )

        return {
            "lap_time": _fmt_lap(lap_time_ms),
            "potential_lap": _fmt_lap(potential_ms),
            "potential_gap_s": "%.2f" % potential_gap_s,
            "ref_gap_s": "%+.2f" % ref_gap_s,
            "clean_lap": "yes" if clean_lap else "no",
            "style_label": style_label,
            "style_tip": style_tip,
            "consistency_pct": int(round(cons * 100.0)),
            "worst_corner": worst[0][0] if worst else "",
            "worst_delta_s": "%.2f" % worst[0][1] if worst else "0",
            "gain_action": gain_action,
            "setup_note": setup_pending or "",
            "reason": (
                "Your stitched best = %s — %.3fs still in your data (seconds or hundredths)."
                % (_fmt_lap(potential_ms), potential_gap_s)
                if potential_gap_s > 0.01
                else "Near your stitched best — next gain is line, phase, or setup balance."
            ),
            "action": gain_action,
        }

    def grip_coaching(self, speed_kmh, ay_g, gg_envelope, corner_display=""):
        if gg_envelope is None or not gg_envelope.has_baseline():
            return None
        left = gg_envelope.grip_left_pct(speed_kmh, ay_g)
        if left < 8:
            return None
        usage = int(round(gg_envelope.grip_usage(speed_kmh, ay_g) * 100.0))
        return {
            "corner_name": corner_display or "Corner",
            "grip_usage_pct": usage,
            "grip_left_pct": left,
            "speed_kmh": int(round(speed_kmh)),
            "reason": (
                "You have used %d%% of your own peak grip at this speed — "
                "more is available without changing setup." % usage
            ),
            "action": "Commit to your reference line — the grip is in your data.",
        }
