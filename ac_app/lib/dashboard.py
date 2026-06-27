# ac_app/lib/dashboard.py
# Python 3.3 compatible — stdlib only

import math

try:
    from volatility_buffer import PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING
except ImportError:
    from .volatility_buffer import PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING

TYRE_NAMES = ("LF", "RF", "LR", "RR")


def format_lap_ms(ms):
    if not ms or ms < 1000:
        return "--:--.---"
    total_s = ms / 1000.0
    minutes = int(total_s // 60)
    seconds = total_s - minutes * 60
    return "%d:%06.3f" % (minutes, seconds)


def progress_bar(current, total, width=10, fill="#", empty="-"):
    if total <= 0:
        return "[" + empty * width + "]"
    ratio = max(0.0, min(1.0, float(current) / float(total)))
    filled = int(round(ratio * width))
    return "[" + fill * filled + empty * (width - filled) + "]"


def track_position_bar(spline, width=28):
    if width < 4:
        width = 4
    idx = int(spline * width)
    if idx >= width:
        idx = width - 1
    if idx < 0:
        idx = 0
    chars = ["."] * width
    chars[idx] = "O"
    return "[" + "".join(chars) + "]"


def _phase_label(phase, bootstrap_active=False):
    if bootstrap_active:
        return "BOOTSTRAP"
    if phase == PHASE_TWEAKING:
        return "TWEAKING"
    if phase == PHASE_BASELINE_READY:
        return "BASELINE READY"
    return "LEARNING"


def _landmark_hint(landmarks, phase_name, corner_name, upcoming=None):
    if corner_name and landmarks:
        if phase_name == "entry" and landmarks.get("brake_cue"):
            return landmarks["brake_cue"]
        if phase_name == "mid" and landmarks.get("apex_cue"):
            return landmarks["apex_cue"]
        if phase_name == "exit" and landmarks.get("exit_cue"):
            return landmarks["exit_cue"]
        if landmarks.get("approach"):
            return landmarks["approach"]
        if landmarks.get("map"):
            return landmarks["map"]
    if upcoming:
        name = upcoming.get("display_name") or upcoming.get("name", "")
        lm = upcoming.get("landmarks", {})
        approach = lm.get("approach", "")
        brake = lm.get("brake_cue", "")
        if brake:
            return "Next: %s — %s" % (name, brake)
        if approach:
            return "Next: %s — %s" % (name, approach)
        if name:
            return "Next: %s" % name
    return "Hold a consistent line — building your reference laps."


def _tyre_temp_glyph(temp_c, ideal_lo, ideal_hi, hot_c, cold_c):
    if temp_c <= 0:
        return "?"
    if temp_c >= hot_c:
        return "^"
    if temp_c <= cold_c:
        return "v"
    if ideal_lo <= temp_c <= ideal_hi:
        return "="
    if temp_c > ideal_hi:
        return "+"
    return "-"


def _balance_text(balance):
    if balance is None or not getattr(balance, "valid", False):
        return "Balance: —"
    delta = math.degrees(balance.delta_us)
    if delta > 2.5:
        return "Balance: understeer (+%.0f deg)" % delta
    if delta < -2.5:
        return "Balance: oversteer (%.0f deg)" % delta
    eff = getattr(balance, "ay_efficiency", 1.0)
    if eff < 0.92:
        return "Balance: low grip (%.0f%% peak G)" % (eff * 100.0)
    return "Balance: neutral"


class EngineerDashboard(object):
    """Human-readable multi-line dashboard for the in-game app window."""

    def build(
        self,
        frame,
        phase,
        clean_laps,
        target_laps,
        total_laps,
        spline_indexer,
        corner_name,
        corner_display,
        phase_name,
        landmarks,
        upcoming_corner,
        sector,
        lap_delta_s,
        worst_corners,
        reference_lap_ms,
        theoretical_best_ms,
        last_lap_ms,
        tyre_temps,
        tyre_ideal_lo,
        tyre_ideal_hi,
        tyre_hot_c,
        tyre_cold_c,
        driving_style,
        balance,
        bootstrap_active,
        track_display,
        coach_text,
        bucket_consistent=None,
        coaching_active=False,
        stint_ready=False,
    ):
        header = "%s %s %d/%d clean | Lap %d (%d total) | %s" % (
            _phase_label(phase, bootstrap_active),
            progress_bar(clean_laps, target_laps),
            clean_laps,
            target_laps,
            frame.lap,
            total_laps,
            track_display or frame.track or "Track",
        )

        track_map = "%s %s" % (
            track_position_bar(frame.spline),
            sector,
        )

        if corner_name:
            location = "%s · %s · %d km/h" % (
                corner_display,
                phase_name.upper(),
                int(round(frame.speed_kmh)),
            )
        else:
            location = "Straight · %s · %d km/h" % (
                sector,
                int(round(frame.speed_kmh)),
            )

        hint = _landmark_hint(landmarks, phase_name, corner_name, upcoming_corner)

        if phase == PHASE_LEARNING:
            if bootstrap_active:
                pace = "Setup bootstrap active — load Auto_Tweak in pits when prompted."
            elif coaching_active:
                pace = "Coaching active from lap %d — messy laps do not reset progress." % max(
                    2, total_laps,
                )
                if bucket_consistent is not None:
                    pace += " | Consistency %d%%" % bucket_consistent
                pace += " | %d/%d clean laps (not consecutive)" % (clean_laps, target_laps)
            elif bucket_consistent is not None:
                pace = "Lap %d: consistency %d%% | Coaching starts next lap | Need %d clean laps total" % (
                    frame.lap,
                    bucket_consistent,
                    max(0, target_laps - clean_laps),
                )
            else:
                pace = "Repeat the same lines — learning your braking and steering references."
            if last_lap_ms:
                pace += " | Last: %s" % format_lap_ms(last_lap_ms)
        elif phase == PHASE_BASELINE_READY:
            pace = "Baseline locked — driver coaching and setup evaluation enabled."
            if lap_delta_s:
                sign = "+" if lap_delta_s >= 0 else ""
                pace += " | Lap delta %s%.2fs" % (sign, lap_delta_s)
        else:
            sign = "+" if lap_delta_s >= 0 else ""
            pace = "Lap delta %s%.2fs vs reference" % (sign, lap_delta_s)
            if worst_corners:
                name, delta = worst_corners[0]
                display = spline_indexer.corner_display_name(name) if spline_indexer else name
                pace += " | Costliest: %s +%.2fs" % (display, delta)
            if theoretical_best_ms and reference_lap_ms:
                gap = (reference_lap_ms - theoretical_best_ms) / 1000.0
                pace += " | Your potential ~%s (%.2fs from your best sectors)" % (
                    format_lap_ms(theoretical_best_ms),
                    gap,
                )
            pot_gap = 0.0
            if theoretical_best_ms and last_lap_ms:
                pot_gap = max(0.0, (last_lap_ms - theoretical_best_ms) / 1000.0)
            if pot_gap > 0.05:
                pace += " | Last lap left %.2fs on table vs your stitched best" % pot_gap

        tyre_parts = []
        for i, name in enumerate(TYRE_NAMES):
            temp = tyre_temps[i] if i < len(tyre_temps) else 0.0
            glyph = _tyre_temp_glyph(temp, tyre_ideal_lo, tyre_ideal_hi, tyre_hot_c, tyre_cold_c)
            tyre_parts.append("%s %s%3.0f" % (name, glyph, temp))
        style = driving_style or {}
        agg = style.get("aggression", 0.0)
        if agg >= 0.55:
            style_word = "aggressive"
        elif agg < 0.35:
            style_word = "smooth"
        else:
            style_word = "balanced"
        tyres = "Tyres: %s | Style: %s" % ("  ".join(tyre_parts), style_word)
        if stint_ready:
            tyres += " | Stint window tracked"
        elif phase == PHASE_LEARNING:
            tyres += " | Stint tyres: need 2 clean laps"

        balance_line = _balance_text(balance)
        if phase == PHASE_LEARNING and not corner_name:
            balance_line = "Focus: hit the same visual markers each lap — watch the map dot."

        coach = coach_text
        if not coach:
            if phase == PHASE_LEARNING and coaching_active:
                coach = "Coaching live — spins are ignored for tyre setup until a clean stint builds."
            elif phase == PHASE_LEARNING:
                coach = "One more lap unlocks corner coaching — messy laps are fine."
            elif phase == PHASE_BASELINE_READY:
                coach = "Baseline ready — corner coaching is live."
            else:
                coach = "Drive cleanly — setup tweaks appear after pit stops."

        return {
            "header": header,
            "track_map": track_map,
            "location": location,
            "hint": hint,
            "pace": pace,
            "tyres": tyres,
            "balance": balance_line,
            "coach": coach,
        }
