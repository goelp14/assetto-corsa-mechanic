# ac_app/lib/hud_renderer.py
# Visual HUD — GL graphics + label-friendly formatters (AC app pattern).

try:
    import ac
    import acsys
except ImportError:
    ac = None
    acsys = None

try:
    from grip_map import zone_color
except ImportError:
    from .grip_map import zone_color

TYRE_NAMES = ("LF", "RF", "LR", "RR")
TYRE_LABELS = ("LF", "RF", "LR", "RR")

# Single layout source — AC render callback draws GL *on top of* labels, so text
# and graphics must occupy disjoint vertical bands.
HUD_W = 500
HUD_H = 168
HUD_PAD = 6

# Text-only bands (no GL quads in these Y ranges)
LBL_LEARN = (58, 4)
LBL_LEARN_DETAIL = (58, 17)
LBL_SETUP = (8, 28)
LBL_SPEED = (278, 0)
LBL_SPEED_UNIT = (360, 11)
LBL_DELTA = (418, 5)
LBL_TYRE_COLS = (14, 118)   # x start, column width
LBL_TYRE_TAG_Y = 70
LBL_TYRE_VAL_Y = 66
LBL_STATUS = (10, 112)
LBL_COACH = (10, 132)
LBL_FEEDBACK = (10, 150)
LBL_CUE1 = (488, 110)
LBL_CUE2 = (488, 134)

# Graphics-only bands (no labels in these Y ranges)
GL_BARS_Y = 40
GL_BARS_H = 6
GL_STRIP_Y = 52
GL_STRIP_H = 10
GL_TYRE_Y = 88
GL_TYRE_H = 16
GL_TYRE_BAR_W = 12
GL_TYRE_BAR_X = 92   # offset from column start to bar groove

# Pit panel starts below driving HUD
LBL_PIT_Y = HUD_H + 6

# Sector breakpoints (fallback when track config missing)
DEFAULT_SECTORS = (
    (0.0, 0.33, "S1"),
    (0.33, 0.66, "S2"),
    (0.66, 1.001, "S3"),
)

CUE_STYLES = {
    "BRAKE_LATE": ((0.25, 0.55, 1.0, 0.95), "BRAKE", "LATER"),
    "TOO_FAST": ((1.0, 0.25, 0.2, 0.95), "TOO", "FAST"),
    "WAIT": ((1.0, 0.75, 0.1, 0.95), "WAIT", "APEX"),
    "SETUP": ((0.2, 0.9, 0.45, 0.95), "PIT", "SETUP"),
    "SHIFT": ((0.55, 0.75, 1.0, 0.95), "SHIFT", "TIMING"),
    "LEARN": ((0.7, 0.7, 0.7, 0.9), "KEEP", "LINE"),
}

FEEDBACK_COLORS = {
    "coaching": (1.0, 0.75, 0.15, 1.0),
    "learning": (0.35, 0.65, 1.0, 1.0),
    "setup": (0.25, 0.9, 0.45, 1.0),
    "revert": (1.0, 0.35, 0.3, 1.0),
    "analysis": (0.75, 0.5, 1.0, 1.0),
}

PHASE_BADGE = {
    "LEARNING": ("LEARN", (0.25, 0.5, 0.9, 1.0)),
    "COACH": ("COACH", (0.2, 0.78, 0.38, 1.0)),
    "BASELINE_READY": ("READY", (0.85, 0.7, 0.15, 1.0)),
    "TWEAKING": ("TWEAK", (0.65, 0.45, 0.95, 1.0)),
    "BOOTSTRAP": ("BOOT", (0.9, 0.55, 0.2, 1.0)),
}


class HudSnapshot(object):
    __slots__ = (
        "width", "height", "spline", "sector", "corner_name", "corner_display",
        "phase", "volatility_phase", "clean_laps", "target_laps", "total_laps",
        "coaching_active", "consistency_pct", "bootstrap_active",
        "tyre_temps", "tyre_ideal_lo", "tyre_ideal_hi",
        "tyre_hot_c", "tyre_cold_c", "lap_delta_s", "speed_kmh", "lap",
        "cue_id", "cue_corner", "cue_alpha", "sectors", "in_pit", "phase_name",
        "track_name", "landmark_hint",         "feedback_headline", "feedback_type",
        "feedback_alpha", "setup_note", "potential_gap_s",
        "grip_segments", "grip_hint", "grip_zone",
        "shift_line", "gear", "rpm", "last_lap_ms", "pit_queue_count",
    )

    def __init__(self):
        self.width = 500
        self.height = HUD_H
        self.spline = 0.0
        self.sector = "S1"
        self.corner_name = ""
        self.corner_display = ""
        self.phase_name = "straight"
        self.phase = "LEARNING"
        self.volatility_phase = "LEARNING"
        self.clean_laps = 0
        self.target_laps = 3
        self.total_laps = 0
        self.coaching_active = False
        self.consistency_pct = 0
        self.bootstrap_active = False
        self.tyre_temps = (0.0, 0.0, 0.0, 0.0)
        self.tyre_ideal_lo = 75
        self.tyre_ideal_hi = 95
        self.tyre_hot_c = 102
        self.tyre_cold_c = 68
        self.lap_delta_s = 0.0
        self.speed_kmh = 0.0
        self.lap = 0
        self.cue_id = ""
        self.cue_corner = ""
        self.cue_alpha = 0.0
        self.sectors = list(DEFAULT_SECTORS)
        self.in_pit = False
        self.track_name = ""
        self.landmark_hint = ""
        self.feedback_headline = ""
        self.feedback_type = ""
        self.feedback_alpha = 0.0
        self.setup_note = None
        self.potential_gap_s = 0.0
        self.grip_segments = []
        self.grip_hint = ""
        self.grip_zone = ""
        self.shift_line = ""
        self.gear = 0
        self.rpm = 0
        self.last_lap_ms = 0
        self.pit_queue_count = 0


def format_setup_hud_line(note):
    """Short in-car line: what changed and why."""
    if not note:
        return ""
    name = note.get("section_display") or note.get("section", "?")
    delta = note.get("delta", 0)
    sign = "+" if delta >= 0 else ""
    reason = short_headline(note.get("reason", ""), 32)
    src = note.get("source", "")
    if note.get("queued"):
        tag = "QUEUED"
    elif src == "bootstrap":
        tag = "BOOT"
    elif src == "tyre":
        tag = "TYRE"
    else:
        tag = "SETUP"
    line = "%s %s %s%d (%s\u2192%s)" % (
        tag, name, sign, abs(delta),
        note.get("old_value", "?"), note.get("new_value", "?"),
    )
    qn = note.get("queue_count", 0)
    if qn > 1:
        line += " +%d pit" % (qn - 1)
    if reason:
        line += " \xb7 %s" % reason
    return line


def format_setup_pit_detail(note):
    """Full pit text: what, why, how."""
    if not note:
        return ""
    name = note.get("section_display") or note.get("section", "?")
    delta = note.get("delta", 0)
    sign = "+" if delta >= 0 else ""
    what = "%s %s%d (%s \u2192 %s)" % (
        name, sign, abs(delta), note.get("old_value", "?"), note.get("new_value", "?"),
    )
    why = note.get("why") or note.get("reason", "")
    how = note.get("action", "Load Auto_Tweak.ini in the setup screen.")
    parts = ["SETUP: %s" % what]
    if why:
        parts.append("Why: %s" % why)
    parts.append("How: %s" % how)
    return " \xb7 ".join(parts)


def tyre_fill_ratio(temp_c, ideal_lo, ideal_hi, hot_c, cold_c):
    """Normalized bar height 0-1 using full cold→hot range."""
    if temp_c <= 0:
        return 0.0, (0.35, 0.35, 0.4, 1.0)
    lo = cold_c - 5.0
    hi = hot_c + 3.0
    span = max(1.0, hi - lo)
    ratio = (temp_c - lo) / span
    ratio = max(0.06, min(1.0, ratio))

    if temp_c >= hot_c:
        return ratio, (1.0, 0.2, 0.15, 1.0)
    if temp_c <= cold_c:
        return ratio, (0.25, 0.5, 1.0, 1.0)
    if ideal_lo <= temp_c <= ideal_hi:
        return ratio, (0.15, 0.85, 0.35, 1.0)
    if temp_c > ideal_hi:
        return ratio, (1.0, 0.55, 0.1, 1.0)
    return ratio, (0.35, 0.55, 1.0, 1.0)


def temp_font_color(temp_c, ideal_lo, ideal_hi, hot_c, cold_c):
    if temp_c <= 0:
        return (0.7, 0.7, 0.7, 1.0)
    if temp_c >= hot_c:
        return (1.0, 0.35, 0.3, 1.0)
    if temp_c <= cold_c:
        return (0.45, 0.65, 1.0, 1.0)
    if ideal_lo <= temp_c <= ideal_hi:
        return (0.35, 1.0, 0.45, 1.0)
    if temp_c > ideal_hi:
        return (1.0, 0.7, 0.2, 1.0)
    return (0.5, 0.75, 1.0, 1.0)


def cue_style(cue_id):
    return CUE_STYLES.get(cue_id, ((0.9, 0.9, 0.9, 0.9), "FOCUS", ""))


def format_delta(delta_s):
    if abs(delta_s) < 0.005:
        return "0.00", (0.85, 0.85, 0.85, 1.0)
    if delta_s > 0:
        return "+%.2f" % delta_s, (1.0, 0.4, 0.35, 1.0)
    return "%.2f" % delta_s, (0.4, 1.0, 0.5, 1.0)


def format_phase_line(snap):
    if snap.cue_id and snap.cue_alpha > 0.1 and not snap.in_pit:
        _, line1, line2 = cue_style(snap.cue_id)
        if line2:
            return "%s  %s" % (line1, line2)
        return line1
    if snap.corner_display:
        base = "%s  %s" % (snap.corner_display, snap.phase_name.upper())
    else:
        base = "%s  %d km/h" % (snap.sector, int(round(snap.speed_kmh)))
    if getattr(snap, "gear", 0) > 0:
        return "G%d %drpm  %s" % (snap.gear, snap.rpm, base)
    return base


def format_learn_line(snap):
    if snap.bootstrap_active:
        tag = "BOOTSTRAP"
    elif snap.coaching_active and snap.phase == "LEARNING":
        tag = "COACH"
    else:
        tag = snap.volatility_phase.replace("_", " ")
    return "%s  %d/%d clean  L%d" % (
        tag, snap.clean_laps, snap.target_laps, snap.lap,
    )


def format_learn_detail(snap):
    parts = []
    last_ms = getattr(snap, "last_lap_ms", 0)
    if last_ms and last_ms > 1000:
        parts.append("last %.3fs" % (last_ms / 1000.0))
    pit_q = getattr(snap, "pit_queue_count", 0)
    if pit_q > 0:
        parts.append("%d tweak%s for pits" % (pit_q, "s" if pit_q != 1 else ""))
    if snap.consistency_pct > 0:
        parts.append("%d%% line" % snap.consistency_pct)
    need = max(0, snap.target_laps - snap.clean_laps)
    if snap.bootstrap_active:
        parts.append("load Auto_Tweak in pits")
    elif snap.phase == "LEARNING":
        if snap.coaching_active:
            parts.append("corner coaching on")
        if need > 0:
            parts.append("%d clean lap%s left" % (need, "s" if need != 1 else ""))
        elif not snap.coaching_active:
            parts.append("coaching next lap")
    elif snap.phase == "BASELINE_READY":
        parts.append("baseline locked · pit auto-tweak ready")
    elif snap.phase == "TWEAKING":
        parts.append("setup eval · pit auto-tweak")
    if getattr(snap, "potential_gap_s", 0.0) > 0.05:
        parts.append("%.2fs untapped (your sectors)" % snap.potential_gap_s)
    if getattr(snap, "grip_segments", None):
        learned = sum(1 for s in snap.grip_segments if s.get("learned"))
        if learned >= 8:
            parts.append("grip map live")
    shift_line = getattr(snap, "shift_line", "")
    if shift_line:
        parts.append(shift_line)
    return " \xb7 ".join(parts)


def short_headline(text, max_len=38):
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"


def feedback_type_color(feedback_type):
    return FEEDBACK_COLORS.get(feedback_type, (0.75, 0.75, 0.8, 1.0))


def phase_badge_key(snap):
    if snap.bootstrap_active:
        return "BOOTSTRAP"
    if snap.phase == "LEARNING" and snap.coaching_active:
        return "COACH"
    if snap.phase in PHASE_BADGE:
        return snap.phase
    return "LEARNING"


def landmark_short(landmarks, phase_name, corner_name, upcoming=None):
    if corner_name and landmarks:
        if phase_name == "entry" and landmarks.get("brake_cue"):
            return short_headline(landmarks["brake_cue"], 42)
        if phase_name == "mid" and landmarks.get("apex_cue"):
            return short_headline(landmarks["apex_cue"], 42)
        if phase_name == "exit" and landmarks.get("exit_cue"):
            return short_headline(landmarks["exit_cue"], 42)
        if landmarks.get("approach"):
            return short_headline(landmarks["approach"], 42)
    if upcoming:
        name = upcoming.get("display_name") or upcoming.get("name", "")
        lm = upcoming.get("landmarks", {})
        brake = lm.get("brake_cue", "")
        if brake:
            return short_headline("Next %s \u2014 %s" % (name, brake), 42)
        approach = lm.get("approach", "")
        if approach:
            return short_headline("Next %s \u2014 %s" % (name, approach), 42)
        if name:
            return "Next: %s" % name
    return ""


def format_coach_hint(snap):
    if snap.cue_id and snap.cue_alpha > 0.15:
        return ""
    if getattr(snap, "grip_hint", ""):
        return snap.grip_hint
    if snap.landmark_hint:
        return snap.landmark_hint
    if snap.phase == "LEARNING" and not snap.corner_name:
        return "Repeat the same visual markers each lap"
    return ""


def format_feedback_line(snap):
    if snap.cue_id and snap.cue_alpha > 0.15:
        return ""
    if snap.feedback_headline and snap.feedback_alpha > 0.08:
        return snap.feedback_headline
    return ""


def sectors_from_indexer(spline_indexer):
    if spline_indexer is None or not spline_indexer.sectors:
        return list(DEFAULT_SECTORS)
    out = []
    prev = 0.0
    for sec in spline_indexer.sectors:
        end = sec.get("spline_end", 1.0)
        name = sec.get("name", "S?")
        out.append((prev, end, name))
        prev = end
    return out


def _quad(x, y, w, h):
    ac.glQuad(x, y, w, h)


def _panel(x, y, w, h, r, g, b, a):
    ac.glColor4f(r, g, b, a)
    _quad(x, y, w, h)


def _draw_background(w, h):
    # Thin top accent only — full-window panels are drawn in the render
    # callback ON TOP of labels and wash text out. Window opacity handles backdrop.
    _panel(0, 0, w, 2, 0.2, 0.45, 0.85, 1.0)


def _draw_learn_bar(snap, x, y, w, h):
    _panel(x, y, w, h, 0.12, 0.12, 0.15, 0.95)
    ratio = 0.0
    if snap.target_laps > 0:
        ratio = min(1.0, float(snap.clean_laps) / float(snap.target_laps))
    fill_w = max(0, int(w * ratio))
    if fill_w > 0:
        if snap.coaching_active:
            ac.glColor4f(0.2, 0.78, 0.38, 1.0)
        else:
            ac.glColor4f(0.25, 0.5, 0.9, 1.0)
        _quad(x, y, fill_w, h)


def _draw_consistency_bar(snap, x, y, w, h):
    _panel(x, y, w, h, 0.12, 0.12, 0.15, 0.95)
    ratio = max(0.0, min(1.0, float(snap.consistency_pct) / 100.0))
    fill_w = max(0, int(w * ratio))
    if fill_w > 0:
        if snap.consistency_pct >= 70:
            ac.glColor4f(0.2, 0.78, 0.38, 1.0)
        elif snap.consistency_pct >= 45:
            ac.glColor4f(0.9, 0.65, 0.15, 1.0)
        else:
            ac.glColor4f(0.9, 0.35, 0.2, 1.0)
        _quad(x, y, fill_w, h)


def _draw_phase_badge(snap, x, y, w, h):
    key = phase_badge_key(snap)
    label, color = PHASE_BADGE.get(key, PHASE_BADGE["LEARNING"])
    _panel(x, y, w, h, color[0] * 0.35, color[1] * 0.35, color[2] * 0.35, 0.95)
    ac.glColor4f(color[0], color[1], color[2], 0.95)
    _quad(x, y, 3, h)


def _draw_sector_strip(snap, x, y, w, h):
    _panel(x, y, w, h, 0.1, 0.1, 0.12, 0.95)
    segments = getattr(snap, "grip_segments", None) or []
    if segments:
        seg_w = max(2, w // max(len(segments), 1))
        for i, seg in enumerate(segments):
            sx = x + i * seg_w
            if i == len(segments) - 1:
                sw = x + w - sx
            else:
                sw = seg_w
            if seg.get("learned"):
                zone = seg.get("zone", "learning")
            else:
                zone = "learning"
            color = zone_color(zone)
            ac.glColor4f(color[0], color[1], color[2], color[3])
            _quad(sx, y + 1, sw, h - 2)
    else:
        for s0, s1, name in snap.sectors:
            zx = x + int(s0 * w)
            zw = max(2, int((s1 - s0) * w))
            active = snap.sector == name
            if active:
                ac.glColor4f(0.85, 0.7, 0.15, 0.45)
            else:
                ac.glColor4f(0.22, 0.22, 0.28, 0.6)
            _quad(zx, y + 1, zw, h - 2)

    for s0, s1, name in snap.sectors:
        zx = x + int(s1 * w)
        ac.glColor4f(0.05, 0.05, 0.08, 0.9)
        _quad(max(x, zx - 1), y, 2, h)

    dot_x = x + int(snap.spline * w)
    dot_x = max(x + 2, min(x + w - 6, dot_x))
    ac.glColor4f(1.0, 1.0, 1.0, 1.0)
    _quad(dot_x, y + 1, 5, h - 6)
    ac.glColor4f(0.1, 0.1, 0.12, 1.0)
    _quad(dot_x + 1, y + h - 5, 3, 3)


def _draw_tyre_bars(snap, x, y, col_w, bar_h):
    """Vertical temp bars on the right side of each column — away from temp text."""
    for i in range(4):
        cx = x + i * col_w
        gx = cx + GL_TYRE_BAR_X
        temp = snap.tyre_temps[i] if i < len(snap.tyre_temps) else 0.0
        _panel(gx, y, GL_TYRE_BAR_W, bar_h, 0.14, 0.14, 0.17, 0.75)
        fill, color = tyre_fill_ratio(
            temp, snap.tyre_ideal_lo, snap.tyre_ideal_hi,
            snap.tyre_hot_c, snap.tyre_cold_c,
        )
        fh = int(bar_h * fill)
        if fh > 0:
            ac.glColor4f(color[0], color[1], color[2], 1.0)
            _quad(gx + 1, y + bar_h - fh, GL_TYRE_BAR_W - 2, fh)


def _draw_cue_accent(snap, x, y_top, w, y_bot):
    """Thin horizontal accents only — never a box over the coaching text."""
    if snap.cue_id and snap.cue_alpha > 0.08:
        color, _, _ = cue_style(snap.cue_id)
        a = snap.cue_alpha * 0.95
        ac.glColor4f(color[0], color[1], color[2], a)
        _quad(x, y_top, w, 2)
        _quad(x, y_bot - 2, w, 2)
        return
    if snap.feedback_headline and snap.feedback_alpha > 0.08:
        color = feedback_type_color(snap.feedback_type)
        a = snap.feedback_alpha * 0.85
        ac.glColor4f(color[0], color[1], color[2], a)
        _quad(x, y_top, w, 2)


def draw_hud(snap):
    if ac is None:
        return

    w = snap.width
    pad = HUD_PAD

    _draw_background(w, snap.height)

    _draw_phase_badge(snap, pad, GL_BARS_Y, 46, GL_BARS_H)
    _draw_learn_bar(snap, pad + 50, GL_BARS_Y, 118, GL_BARS_H)
    _draw_consistency_bar(snap, pad + 172, GL_BARS_Y, 72, GL_BARS_H)

    _draw_sector_strip(snap, pad, GL_STRIP_Y, w - pad * 2, GL_STRIP_H)

    col_w = (w - pad * 2) / 4
    _draw_tyre_bars(snap, pad, GL_TYRE_Y, int(col_w), GL_TYRE_H)

    coach_top = LBL_STATUS[1] - 2
    coach_bot = snap.height - 2
    _draw_cue_accent(snap, pad, coach_top, w - pad * 2, coach_bot)


def build_snapshot(
    frame,
    spline_indexer,
    corner_name,
    phase_name,
    volatility,
    tyre_temps,
    tyre_thresholds,
    lap_delta_s,
    cue_id,
    cue_corner,
    cue_alpha,
    in_pit,
    width=HUD_W,
    height=HUD_H,
    track_name="",
    consistency_pct=0,
    bootstrap_active=False,
    landmarks=None,
    upcoming_corner=None,
    feedback_headline="",
    feedback_type="",
    feedback_alpha=0.0,
    setup_note=None,
    potential_gap_s=0.0,
    grip_segments=None,
    grip_hint="",
    grip_zone="",
    shift_line="",
    last_lap_ms=0,
    pit_queue_count=0,
):
    snap = HudSnapshot()
    snap.width = width
    snap.height = height
    snap.spline = frame.spline
    snap.sector = spline_indexer.sector_name(frame.spline) if spline_indexer else "S1"
    snap.corner_name = corner_name or ""
    snap.corner_display = ""
    if spline_indexer and corner_name:
        snap.corner_display = spline_indexer.corner_display_name(corner_name)
    snap.phase_name = phase_name or "straight"
    snap.phase = volatility.phase if volatility else "LEARNING"
    snap.volatility_phase = snap.phase
    clean, target = volatility.learning_progress()
    snap.clean_laps = clean
    snap.target_laps = target
    snap.total_laps = volatility.total_laps
    snap.coaching_active = volatility.coaching_allowed()
    snap.consistency_pct = consistency_pct
    snap.bootstrap_active = bootstrap_active
    snap.tyre_temps = tyre_temps
    snap.tyre_ideal_lo = tyre_thresholds.get("ideal_lo", 75)
    snap.tyre_ideal_hi = tyre_thresholds.get("ideal_hi", 95)
    snap.tyre_hot_c = tyre_thresholds.get("hot_c", 102)
    snap.tyre_cold_c = tyre_thresholds.get("cold_c", 68)
    snap.lap_delta_s = lap_delta_s
    snap.speed_kmh = frame.speed_kmh
    snap.lap = frame.lap
    snap.cue_id = cue_id or ""
    snap.cue_corner = cue_corner or ""
    snap.cue_alpha = max(0.0, min(1.0, cue_alpha))
    snap.sectors = sectors_from_indexer(spline_indexer)
    snap.in_pit = in_pit
    snap.track_name = track_name or ""
    snap.landmark_hint = landmark_short(
        landmarks or {}, phase_name, corner_name, upcoming_corner,
    )
    snap.feedback_headline = short_headline(feedback_headline)
    snap.feedback_type = feedback_type or ""
    snap.feedback_alpha = max(0.0, min(1.0, feedback_alpha))
    snap.setup_note = setup_note
    snap.potential_gap_s = max(0.0, potential_gap_s)
    snap.grip_segments = list(grip_segments or [])
    snap.grip_hint = grip_hint or ""
    snap.grip_zone = grip_zone or ""
    snap.shift_line = shift_line or ""
    snap.gear = int(getattr(frame, "gear", 0))
    snap.rpm = int(getattr(frame, "rpm", 0))
    snap.last_lap_ms = int(last_lap_ms or 0)
    snap.pit_queue_count = int(pit_queue_count or 0)
    return snap


# Back-compat for tests
def corner_zones_from_indexer(spline_indexer):
    return sectors_from_indexer(spline_indexer)
