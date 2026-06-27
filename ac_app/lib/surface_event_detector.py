# ac_app/lib/surface_event_detector.py
# Detect kerbs, bumps, grip loss from wheel load, suspension, slip, vertical G.

import math


class SurfacePhaseStats(object):
    """Per-phase surface aggregates — attached to corner phase metrics."""

    __slots__ = (
        "kerb_contacts", "kerb_grip_loss", "bump_hits", "platform_hops",
        "painted_kerb_slip", "max_vert_g", "max_load_drop_pct", "max_susp_pct",
        "_prev_load", "_prev_vert", "_prev_susp", "_kerb_recent", "_hop_logged",
    )

    def __init__(self):
        self.kerb_contacts = 0
        self.kerb_grip_loss = 0
        self.bump_hits = 0
        self.platform_hops = 0
        self.painted_kerb_slip = 0
        self.max_vert_g = 0.0
        self.max_load_drop_pct = 0.0
        self.max_susp_pct = 0.0
        self._prev_load = None
        self._prev_vert = None
        self._prev_susp = None
        self._kerb_recent = 0
        self._hop_logged = False

    def observe(self, frame, dynamics, balance, thresholds):
        t = thresholds or {}
        kerb_susp = float(t.get("KERB_SUSP_PCT", 0.85))
        bump_vert = float(t.get("BUMP_VERT_G", 1.0))
        load_drop = float(t.get("SURFACE_LOAD_DROP_PCT", 0.12))
        slip_spike = float(t.get("SURFACE_SLIP_SPIKE", 0.08))
        painted_lo = float(t.get("PAINTED_KERB_SUSP_LO", 0.45))
        painted_hi = float(t.get("PAINTED_KERB_SUSP_HI", 0.84))

        ratios = getattr(frame, "susp_ratio", None) or ()
        loads = getattr(frame, "wheel_load", None) or ()
        slips = getattr(frame, "slip_ratio", getattr(frame, "slip", ())) or ()
        acc = getattr(frame, "acc_g", (0.0, 0.0, 0.0))
        vert = abs(acc[2]) if len(acc) > 2 else 0.0

        if vert > self.max_vert_g:
            self.max_vert_g = vert

        susp_max = max(ratios) if ratios else 0.0
        if susp_max > self.max_susp_pct:
            self.max_susp_pct = susp_max

        load_sum = sum(loads) if loads else 0.0
        slip_max = max(slips) if slips else 0.0
        slip_lr_delta = 0.0
        if len(slips) >= 4:
            slip_lr_delta = abs((slips[0] + slips[1]) * 0.5 - (slips[2] + slips[3]) * 0.5)

        kerb_now = susp_max >= kerb_susp
        if kerb_now:
            self.kerb_contacts += 1
            self._kerb_recent = 3
            self._hop_logged = False
        elif self._kerb_recent > 0:
            self._kerb_recent -= 1

        if self._prev_load is not None and load_sum > 100.0:
            drop = (self._prev_load - load_sum) / self._prev_load
            if drop > self.max_load_drop_pct:
                self.max_load_drop_pct = drop
            if drop >= load_drop and (kerb_now or self._kerb_recent > 0):
                if slip_max > slip_spike or (
                    balance is not None and balance.valid and abs(balance.delta_us) > 0.04
                ):
                    self.kerb_grip_loss += 1

        if vert >= bump_vert and susp_max < kerb_susp:
            self.bump_hits += 1

        if self._kerb_recent > 0 and not self._hop_logged and vert >= bump_vert * 0.65:
            yaw = abs(getattr(dynamics, "yaw_rate_err", 0.0)) if dynamics else 0.0
            if yaw > float(t.get("SURFACE_HOP_YAW_ERR", 0.15)):
                self.platform_hops += 1
                self._hop_logged = True

        if painted_lo <= susp_max <= painted_hi and slip_max > slip_spike:
            if len(ratios) >= 2 and abs(ratios[0] - ratios[1]) > 0.12:
                self.painted_kerb_slip += 1
            elif slip_lr_delta > slip_spike:
                self.painted_kerb_slip += 1

        if self._prev_susp is not None and kerb_now and susp_max - self._prev_susp > 0.25:
            if slip_max > slip_spike:
                self.kerb_grip_loss += 1

        self._prev_load = load_sum if load_sum > 0 else self._prev_load
        self._prev_vert = vert
        self._prev_susp = susp_max

    def to_dict(self):
        return {
            "kerb_contacts": self.kerb_contacts,
            "kerb_grip_loss": self.kerb_grip_loss,
            "bump_hits": self.bump_hits,
            "platform_hops": self.platform_hops,
            "painted_kerb_slip": self.painted_kerb_slip,
            "max_vert_g": round(self.max_vert_g, 2),
            "max_load_drop_pct": round(self.max_load_drop_pct * 100.0, 1),
            "max_susp_pct": round(self.max_susp_pct, 3),
        }


def primary_surface_symptom(surface, thresholds=None):
    """Return (symptom_key, confidence, detail) from merged surface dict."""
    if not surface:
        return None
    t = thresholds or {}
    if surface.get("platform_hops", 0) >= int(t.get("PLATFORM_HOP_MIN", 1)):
        return ("platform_hop", 0.82, "Chassis hopped after kerb — tyres unloaded.")
    if surface.get("kerb_grip_loss", 0) >= int(t.get("KERB_GRIP_LOSS_MIN", 1)):
        return ("kerb_grip_loss", 0.85, "Load and grip dropped on kerb contact.")
    if surface.get("painted_kerb_slip", 0) >= int(t.get("PAINTED_KERB_MIN", 1)):
        return ("painted_kerb_slip", 0.75, "Slip spike with light kerb — likely low-grip painted edge.")
    if surface.get("kerb_contacts", 0) >= int(t.get("KERB_OVERLOAD_COUNT", 2)):
        if surface.get("max_susp_pct", 0) >= float(t.get("KERB_SUSP_PCT", 0.85)):
            return ("kerb_overload", 0.7, "Heavy kerb use — suspension at travel limit.")
    if surface.get("bump_hits", 0) >= int(t.get("BUMP_HIT_MIN", 2)):
        return ("bump_unsettled", 0.72, "Vertical impact unsettled the platform.")
    return None
