# ac_app/lib/shift_analyzer.py
# Gear-change timing vs car balance (Python 3.3 — AC sequential / F1-style).
#
# F1/racing shift physics (simplified for coaching):
# - Upshifts cut torque briefly; seamless boxes minimize loss but still move load.
# - Downshifts apply engine-braking torque to the rear; ECU blip matches revs.
# - Shifts under lateral load (mid-corner) unsettle the platform — yaw/slip spike.
# - Downshifts belong in the braking zone with steering straight (settling).
# - Upshifts belong on straights or after the car is unwound at corner exit.

import math

VERDICT_SETTLING = "settling"
VERDICT_UNSETTLING = "unsettling"
VERDICT_LATE = "late"
VERDICT_EARLY = "early"
VERDICT_HARSH = "harsh"

DIRECTION_UP = "upshift"
DIRECTION_DOWN = "downshift"


class ShiftEvent(object):
    __slots__ = (
        "lap", "spline", "corner", "corner_display", "phase",
        "direction", "from_gear", "to_gear", "rpm",
        "speed_kmh", "throttle", "brake", "steer_deg",
        "lat_g", "long_g", "verdict", "quality", "template_key",
        "post_yaw_spike", "post_rear_slip_spike", "issue",
    )

    def __init__(self):
        self.lap = 0
        self.spline = 0.0
        self.corner = ""
        self.corner_display = ""
        self.phase = "straight"
        self.direction = DIRECTION_UP
        self.from_gear = 0
        self.to_gear = 0
        self.rpm = 0
        self.speed_kmh = 0.0
        self.throttle = 0.0
        self.brake = 0.0
        self.steer_deg = 0.0
        self.lat_g = 0.0
        self.long_g = 0.0
        self.verdict = VERDICT_SETTLING
        self.quality = "good"
        self.template_key = ""
        self.post_yaw_spike = 0.0
        self.post_rear_slip_spike = 0.0
        self.issue = ""

    def is_coaching(self):
        return self.quality != "good"

    def to_dict(self):
        return {
            "lap": self.lap,
            "spline": round(self.spline, 4),
            "corner": self.corner,
            "corner_display": self.corner_display,
            "phase": self.phase,
            "direction": self.direction,
            "from_gear": self.from_gear,
            "to_gear": self.to_gear,
            "rpm": self.rpm,
            "speed_kmh": round(self.speed_kmh, 1),
            "throttle": round(self.throttle, 3),
            "brake": round(self.brake, 3),
            "steer_deg": round(self.steer_deg, 1),
            "lat_g": round(self.lat_g, 3),
            "long_g": round(self.long_g, 3),
            "verdict": self.verdict,
            "quality": self.quality,
            "template_key": self.template_key,
            "post_yaw_spike": round(self.post_yaw_spike, 4),
            "post_rear_slip_spike": round(self.post_rear_slip_spike, 4),
            "issue": self.issue,
        }


class _PendingShift(object):
    __slots__ = (
        "event", "frames_left", "base_yaw", "base_rear_slip",
        "max_yaw_spike", "max_rear_slip_spike", "thresholds", "classify_fn",
    )

    def __init__(self, event, thresholds, classify_fn):
        self.event = event
        self.frames_left = int(thresholds.get("SHIFT_FOLLOWUP_FRAMES", 5))
        self.base_yaw = 0.0
        self.base_rear_slip = 0.0
        self.max_yaw_spike = 0.0
        self.max_rear_slip_spike = 0.0
        self.thresholds = thresholds
        self.classify_fn = classify_fn

    def observe_followup(self, frame, dynamics):
        slips = getattr(frame, "slip_ratio", frame.slip)
        rear = (slips[2] + slips[3]) * 0.5 if slips and len(slips) >= 4 else 0.0
        yaw = abs(frame.yaw_rate)
        if self.frames_left == int(self.thresholds.get("SHIFT_FOLLOWUP_FRAMES", 5)):
            self.base_yaw = yaw
            self.base_rear_slip = rear
        self.max_yaw_spike = max(self.max_yaw_spike, abs(yaw - self.base_yaw))
        self.max_rear_slip_spike = max(self.max_rear_slip_spike, rear - self.base_rear_slip)

        self.frames_left -= 1
        if self.frames_left > 0:
            return None

        ev = self.event
        ev.post_yaw_spike = self.max_yaw_spike
        ev.post_rear_slip_spike = max(0.0, self.max_rear_slip_spike)
        self.classify_fn(ev, self.thresholds)
        return ev


class ShiftAnalyzer(object):
    """Detect and classify gear changes vs corner phase and platform stability."""

    def __init__(self, thresholds=None, spline_indexer=None):
        self.thresholds = thresholds or {}
        self.spline_indexer = spline_indexer
        self._prev_gear = None
        self._pending = None
        self._events = []
        self._lap_events = []

    def reset_lap(self):
        self._lap_events = []
        self._pending = None

    def _t(self, key, default):
        return float(self.thresholds.get(key, default))

    def _corner_display(self, corner):
        if not corner:
            return ""
        if self.spline_indexer is not None:
            return self.spline_indexer.corner_display_name(corner)
        return corner

    @staticmethod
    def _classify(event, thresholds):
        lat = abs(event.lat_g)
        steer = abs(event.steer_deg)
        phase = event.phase or "straight"
        is_straight = phase == "straight" or (lat < thresholds.get("SHIFT_STRAIGHT_LAT_G", 0.25)
                                              and steer < thresholds.get("SHIFT_STRAIGHT_STEER_DEG", 6.0))
        braking = event.brake >= thresholds.get("SHIFT_BRAKING_THRESH", 0.15)
        harsh_yaw = event.post_yaw_spike >= thresholds.get("SHIFT_HARSH_YAW_SPIKE", 0.35)
        harsh_slip = event.post_rear_slip_spike >= thresholds.get("SHIFT_HARSH_REAR_SLIP", 0.08)
        loaded = (
            lat >= thresholds.get("SHIFT_LOADED_LAT_G", 0.45)
            or steer >= thresholds.get("SHIFT_LOADED_STEER_DEG", 10.0)
        )

        if event.direction == DIRECTION_DOWN:
            if harsh_yaw or harsh_slip:
                event.verdict = VERDICT_HARSH
                event.quality = "bad"
                event.issue = "rear_platform"
                event.template_key = "shift_harsh_downshift"
            elif loaded and phase in ("mid", "exit"):
                event.verdict = VERDICT_UNSETTLING
                event.quality = "bad"
                event.issue = "mid_corner_load"
                event.template_key = "shift_unsettling_downshift"
            elif phase == "mid" and steer >= thresholds.get("SHIFT_LATE_STEER_DEG", 8.0):
                event.verdict = VERDICT_LATE
                event.quality = "bad"
                event.issue = "after_turn_in"
                event.template_key = "shift_late_downshift"
            elif braking and lat < thresholds.get("SHIFT_GOOD_DOWN_LAT_G", 0.4):
                event.verdict = VERDICT_SETTLING
                event.quality = "good"
                event.template_key = "shift_settling_downshift"
            elif is_straight and braking:
                event.verdict = VERDICT_SETTLING
                event.quality = "good"
                event.template_key = "shift_settling_downshift"
            elif loaded:
                event.verdict = VERDICT_UNSETTLING
                event.quality = "bad"
                event.issue = "lateral_load"
                event.template_key = "shift_unsettling_downshift"
            else:
                event.verdict = VERDICT_SETTLING
                event.quality = "good"
                event.template_key = "shift_settling_downshift"
        else:
            if harsh_yaw or (harsh_slip and event.throttle > 0.3):
                event.verdict = VERDICT_HARSH
                event.quality = "bad"
                event.issue = "torque_cut"
                event.template_key = "shift_harsh_upshift"
            elif loaded and phase in ("mid", "exit") and event.throttle > 0.25:
                event.verdict = VERDICT_EARLY
                event.quality = "bad"
                event.issue = "still_loaded"
                event.template_key = "shift_early_upshift"
            elif loaded:
                event.verdict = VERDICT_UNSETTLING
                event.quality = "bad"
                event.issue = "lateral_load"
                event.template_key = "shift_unsettling_upshift"
            elif is_straight and event.throttle > thresholds.get("SHIFT_GOOD_UP_THROTTLE", 0.4):
                event.verdict = VERDICT_SETTLING
                event.quality = "good"
                event.template_key = "shift_settling_upshift"
            elif is_straight:
                event.verdict = VERDICT_SETTLING
                event.quality = "good"
                event.template_key = "shift_settling_upshift"
            else:
                event.verdict = VERDICT_SETTLING
                event.quality = "good"
                event.template_key = "shift_settling_upshift"

    def observe(self, frame, corner, phase, dynamics=None):
        finalized = None
        if self._pending is not None:
            finalized = self._pending.observe_followup(frame, dynamics)
            if finalized is not None:
                self._events.append(finalized)
                self._lap_events.append(finalized)
                self._pending = None

        gear = int(getattr(frame, "gear", 0))
        if gear <= 0:
            return finalized

        if self._prev_gear is not None and gear != self._prev_gear:
            delta = gear - self._prev_gear
            if abs(delta) == 1 and self._prev_gear > 0:
                ev = ShiftEvent()
                ev.lap = frame.lap
                ev.spline = frame.spline
                ev.corner = corner or ""
                ev.corner_display = self._corner_display(corner)
                ev.phase = phase or "straight"
                ev.direction = DIRECTION_UP if delta > 0 else DIRECTION_DOWN
                ev.from_gear = self._prev_gear
                ev.to_gear = gear
                ev.rpm = int(getattr(frame, "rpm", 0))
                ev.speed_kmh = frame.speed_kmh
                ev.throttle = frame.throttle
                ev.brake = frame.brake
                ev.steer_deg = frame.steer * 57.2958
                ev.lat_g = frame.acc_g[1]
                ev.long_g = frame.acc_g[0]
                self._pending = _PendingShift(ev, self.thresholds, self._classify)

        self._prev_gear = gear
        return finalized

    def lap_summary(self):
        total = len(self._lap_events)
        bad = sum(1 for e in self._lap_events if e.quality != "good")
        settling = sum(1 for e in self._lap_events if e.quality == "good")
        last = self._lap_events[-1] if self._lap_events else None
        return {
            "total_shifts": total,
            "unsettling_shifts": bad,
            "settling_shifts": settling,
            "last_event": last.to_dict() if last else None,
        }

    def hud_line(self):
        if not self._lap_events:
            gear = self._prev_gear or 0
            if gear > 0:
                return "Gear %d · no shifts this lap" % gear
            return ""
        last = self._lap_events[-1]
        gear = last.to_gear
        rpm = last.rpm
        bad = sum(1 for e in self._lap_events if e.quality != "good")
        total = len(self._lap_events)
        tag = "OK" if last.quality == "good" else "!"
        where = last.corner_display or last.phase.upper()
        return "G%d %drpm · %s %s (%d/%d clean shifts)" % (
            gear, rpm, tag, where, total - bad, total,
        )

    def corner_shifts(self, corner):
        return [e for e in self._lap_events if e.corner == corner]

    def primary_corner_symptom(self, corner):
        """Map repeated bad shifts at a corner to a setup/coaching symptom."""
        bad = [e for e in self.corner_shifts(corner) if e.quality != "good"]
        if not bad:
            return None
        ev = bad[-1]
        if ev.template_key == "shift_unsettling_downshift":
            if ev.phase == "entry":
                return "shift_unsettling_downshift_entry"
            return "shift_unsettling_downshift"
        if ev.template_key == "shift_harsh_downshift":
            return "shift_harsh_downshift"
        if ev.template_key in ("shift_unsettling_upshift", "shift_early_upshift"):
            return "shift_unsettling_upshift"
        return "shift_unsettling_downshift"

    def coaching_evidence(self, event):
        direction = "Upshift" if event.direction == DIRECTION_UP else "Downshift"
        return {
            "corner_name": event.corner_display or "Straight",
            "phase": event.phase.upper(),
            "from_gear": event.from_gear,
            "to_gear": event.to_gear,
            "gear_change": "%d→%d" % (event.from_gear, event.to_gear),
            "direction": direction,
            "rpm": event.rpm,
            "lat_g": "%.2f" % abs(event.lat_g),
            "steer_deg": "%.0f" % abs(event.steer_deg),
            "speed_kmh": int(round(event.speed_kmh)),
            "issue": event.issue.replace("_", " "),
        }

    def all_events(self):
        return list(self._events)
