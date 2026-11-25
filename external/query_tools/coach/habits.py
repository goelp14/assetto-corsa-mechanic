"""Driving habits and tendencies from corner-by-corner analysis — any car, any track, AC or ACC.

Input: the analysis produced by ``vre-rpy analyze`` (``vre.acc_rpy.analysis.v1``): per corner window
and lap, events such as braking ramp, re-application, minimum speed, full-throttle point, margins.

A *habit* is a pattern that repeats (≥ half the laps at a corner, or ≥ 3 corners). Each one gets:
- polarity: ``weakness`` (costs time vs the reference and/or correlates with your slower laps),
  ``strength`` (you are better than the reference there and it pays), or ``style`` (different but
  no measurable cost — recorded, not corrected);
- evidence: the numbers it was detected from, with corner keys for citation;
- pace impact: section time lost in the corners where it shows up.
Thresholds are relative (vs the reference, or vs your own spread), never car/track constants.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA = "vre.habits.v1"


@dataclass
class Instance:
    corner: str
    key: str
    evidence: Dict[str, Any]
    lap_fraction: float
    loss_s: Optional[float] = None
    own_r: Optional[float] = None


@dataclass
class Habit:
    id: str
    group: str
    title: str
    detail: str
    polarity: str
    instances: List[Instance] = field(default_factory=list)

    @property
    def pace_impact_s(self) -> float:
        return round(sum(max(i.loss_s or 0.0, 0.0) for i in self.instances), 3)

    def to_json(self) -> Dict[str, Any]:
        d = asdict(self)
        d["pace_impact_s"] = self.pace_impact_s
        d["corners"] = [i.corner for i in self.instances]
        d["repeats"] = len(self.instances)
        return d


def _med(c: Optional[Dict[str, Any]], k: str) -> Optional[float]:
    """Median over laps; with fewer than 3 laps (e.g. a single reference lap) the best lap's value."""
    if not c:
        return None
    v = (c.get("consistency") or {}).get(k)
    if v is not None:
        return v["median"]
    bl = c.get("best_lap") or {}
    x = bl.get(k)
    return None if x is None else float(x)


def _r(c: Dict[str, Any], k: str) -> Optional[float]:
    v = (c.get("consistency") or {}).get(k)
    return None if v is None else v.get("r_with_time")


def _frac(c: Dict[str, Any], pred) -> float:
    laps = c.get("laps") or []
    if not laps:
        return 0.0
    return sum(1 for l in laps if pred(l)) / len(laps)


def _name(key: str) -> str:
    return key.split("#")[0]


# Each rule: (id, group, title, detail-template, detector(me, ref) -> evidence dict or None, polarity hint)
def _rules():
    def slow_build(me, ref):
        a, b = _med(me, "brake_ramp_m"), _med(ref, "brake_ramp_m") if ref else None
        if a is None:
            return None
        if b is not None and a > max(18.0, 1.6 * b):
            return {"you_brake_ramp_m": a, "ref_brake_ramp_m": b}
        if b is None and a > 30.0:
            return {"you_brake_ramp_m": a}
        return None

    def rebrake(me, ref):
        f = _frac(me, lambda l: (l.get("rebrake_peak") or 0) > 0.15)
        fr = _frac(ref, lambda l: (l.get("rebrake_peak") or 0) > 0.15) if ref else 0.0
        return {"laps_with_second_application": round(f, 2), "ref": round(fr, 2)} if f >= 0.5 and f > fr + 0.3 else None

    def no_trail(me, ref):
        a, b = _med(me, "brake_at_turn_in"), _med(ref, "brake_at_turn_in") if ref else None
        return {"you_brake_at_turn_in": a, "ref": b} if a is not None and b is not None and a < 0.05 and b > 0.15 else None

    def heavy_trail(me, ref):
        f = _frac(me, lambda l: (l.get("entry_lock_min") or 0) < -0.10)
        return {"laps_locking_front": round(f, 2)} if f >= 0.5 else None

    def hero_entry(me, ref):
        if not ref:
            return None
        ti, ti_r = _med(me, "turn_in_kmh"), _med(ref, "turn_in_kmh")
        vm, vm_r = _med(me, "vmin_kmh"), _med(ref, "vmin_kmh")
        if None in (ti, ti_r, vm, vm_r):
            return None
        if ti > ti_r + 3.0 and vm < vm_r - 2.0:
            return {"turn_in_kmh": ti, "ref_turn_in_kmh": ti_r, "vmin_kmh": vm, "ref_vmin_kmh": vm_r}
        return None

    def over_slow(me, ref):
        if not ref:
            return None
        vm, vm_r = _med(me, "vmin_kmh"), _med(ref, "vmin_kmh")
        ap, ap_r = _med(me, "vmin_vs_apex_m"), _med(ref, "vmin_vs_apex_m")
        if None in (vm, vm_r) or vm >= vm_r - 3.0:
            return None
        if ap is not None and ap_r is not None and ap < ap_r - 8.0:
            return {"vmin_kmh": vm, "ref_vmin_kmh": vm_r, "slowest_vs_apex_m": ap, "ref_slowest_vs_apex_m": ap_r}
        return None

    def late_throttle(me, ref):
        a, b = _med(me, "full_throttle_m"), _med(ref, "full_throttle_m") if ref else None
        return {"full_throttle_m": a, "ref_full_throttle_m": b} if a is not None and b is not None and a > b + 8.0 else None

    def early_throttle_strength(me, ref):
        a, b = _med(me, "full_throttle_m"), _med(ref, "full_throttle_m") if ref else None
        return {"full_throttle_m": a, "ref_full_throttle_m": b} if a is not None and b is not None and a < b - 8.0 else None

    def lifts(me, ref):
        f = _frac(me, lambda l: (l.get("throttle_lifts") or 0) >= 1)
        fr = _frac(ref, lambda l: (l.get("throttle_lifts") or 0) >= 1) if ref else 0.0
        return {"laps_with_lift": round(f, 2), "ref": round(fr, 2)} if f >= 0.5 and f > fr + 0.3 else None

    def coasting(me, ref):
        a, b = _med(me, "coast_s"), _med(ref, "coast_s") if ref else None
        return {"coast_s": a, "ref_coast_s": b} if a is not None and a > 0.3 and (b is None or a > b + 0.2) else None

    def _dt(c):
        return _med(c, "input_dt_s") or 0.0

    def overlap_more(me, ref):
        """You brake with the throttle still past half for longer than the reference (left-foot handover)."""
        a, b = _med(me, "brake_overlap_s"), _med(ref, "brake_overlap_s") if ref else None
        if a is None:
            return None
        res = max(_dt(me), _dt(ref) if ref else 0.0)
        if a > max(0.10, 1.5 * _dt(me)) and (b is None or a > b + max(res, 0.05)):
            return {"brake_overlap_s": a, "ref_brake_overlap_s": b, "input_dt_s": round(res, 3)}
        return None

    def ref_overlaps(me, ref):
        """The reference is already braking while still on the throttle; you lift first."""
        if not ref:
            return None
        a, b = _med(me, "brake_overlap_s"), _med(ref, "brake_overlap_s")
        if None in (a, b):
            return None
        res = max(_dt(me), _dt(ref))
        if b > max(0.10, 1.5 * _dt(ref)) and b > a + max(res, 0.05):
            ev = {"brake_overlap_s": a, "ref_brake_overlap_s": b, "input_dt_s": round(res, 3)}
            ba, bb = _med(me, "brake_at_lift"), _med(ref, "brake_at_lift")
            if ba is not None and bb is not None:
                ev.update(brake_at_lift=ba, ref_brake_at_lift=bb)
            return ev
        return None

    def lift_gap(me, ref):
        a, b = _med(me, "lift_gap_s"), _med(ref, "lift_gap_s") if ref else None
        if a is None:
            return None
        if a > max(0.15, 1.5 * _dt(me)) and (b is None or a > b + 0.10):
            return {"lift_gap_s": a, "ref_lift_gap_s": b}
        return None

    def waits_straight(me, ref):
        a, s = _med(me, "full_throttle_m"), _med(me, "wheel_straight_m")
        b, sr = (_med(ref, "full_throttle_m"), _med(ref, "wheel_straight_m")) if ref else (None, None)
        if None in (a, s, b, sr):
            return None
        if a >= s - 2 and b < sr - 8:
            return {"you_full_throttle_vs_straight_m": round(a - s, 1), "ref": round(b - sr, 1)}
        return None

    def apex_wide(me, ref):
        a, b = _med(me, "apex_margin_m"), _med(ref, "apex_margin_m") if ref else None
        return {"apex_margin_m": a, "ref_apex_margin_m": b} if a is not None and b is not None and a > b + 1.0 else None

    def exit_unused(me, ref):
        a, b = _med(me, "exit_margin_m"), _med(ref, "exit_margin_m") if ref else None
        return {"exit_margin_m": a, "ref_exit_margin_m": b} if a is not None and b is not None and a > b + 1.0 else None

    def crest_braking(me, ref):
        def on_crest(l):
            return any(t["kind"] == "crest" and t["brake"] > 0.3 for t in (l.get("terrain") or []))

        f = _frac(me, on_crest)
        fr = _frac(ref, on_crest) if ref else 0.0
        return {"laps_braking_over_crest": round(f, 2), "ref": round(fr, 2)} if f >= 0.5 and f > fr + 0.3 else None

    def inconsistent(me, ref):
        c = me.get("consistency") or {}
        vm, bo = c.get("vmin_kmh"), c.get("brake_on_m")
        if vm and vm["n"] >= 5 and vm["iqr"] > 4.0:
            return {"vmin_iqr_kmh": vm["iqr"], "laps": vm["n"]}
        if bo and bo["n"] >= 5 and bo["iqr"] > 15.0:
            return {"brake_on_iqr_m": bo["iqr"], "laps": bo["n"]}
        return None

    # --- rotation (coach/rotation.py metrics; absent on bundles built without frames) ---
    def rotation_snap(me, ref):
        """Rotation snapped in at turn-in rather than built up as speed falls (peak yaw acceleration)."""
        a, b = _med(me, "rotation_jerk_dps2"), _med(ref, "rotation_jerk_dps2") if ref else None
        if a is None or b is None:
            return None
        if a > max(1.5 * b, b + 15.0):
            ev = {"rotation_jerk_dps2": a, "ref_rotation_jerk_dps2": b}
            sa, sb = _med(me, "entry_slip_peak_deg"), _med(ref, "entry_slip_peak_deg")
            if sa is not None and sb is not None:
                ev.update(entry_slip_peak_deg=sa, ref_entry_slip_peak_deg=sb)
            return ev
        return None

    def brakes_then_turns(me, ref):
        """All the slowing is done before turning; the reference keeps shedding speed while the car rotates."""
        a, b = _med(me, "kmh_lost_turn_in_to_mrp"), _med(ref, "kmh_lost_turn_in_to_mrp") if ref else None
        if a is None or b is None:
            return None
        if b > a + 8.0:
            return {"kmh_lost_turn_in_to_mrp": a, "ref_kmh_lost_turn_in_to_mrp": b,
                    "heading_to_mrp_deg": _med(me, "heading_to_mrp_deg"),
                    "ref_heading_to_mrp_deg": _med(ref, "heading_to_mrp_deg")}
        return None

    def rotates_slower(me, ref):
        """Peak rotation happens at a clearly lower speed than the reference ('paying' more speed for rotation)."""
        a, b = _med(me, "mrp_kmh"), _med(ref, "mrp_kmh") if ref else None
        if _med(me, "kmh_lost_turn_in_to_mrp") is None:  # braked corners only
            return None
        if a is None or b is None or a >= b - 3.0:
            return None
        return {"mrp_kmh": a, "ref_mrp_kmh": b, "mrp_vs_apex_m": _med(me, "mrp_vs_apex_m"),
                "ref_mrp_vs_apex_m": _med(ref, "mrp_vs_apex_m")}

    def throttle_before_rotation(me, ref):
        a, b = _med(me, "throttle_on_vs_mrp_m"), _med(ref, "throttle_on_vs_mrp_m") if ref else None
        if a is None or b is None or a >= -5.0 or b < -5.0:  # only where the reference waits for the rotation
            return None
        return {"throttle_on_vs_mrp_m": a, "ref_throttle_on_vs_mrp_m": b}

    def accelerates_before_half_rotation(me, ref):
        """Throttle before about half the corner's rotation is done (on the brakes is where rotation is cheap)."""
        a, b = _med(me, "rotation_before_throttle_frac"), _med(ref, "rotation_before_throttle_frac") if ref else None
        if a is None or b is None or a >= 0.5 or b < 0.5 or a > b - 0.15:
            return None
        return {"rotation_before_throttle_pct": round(100 * a), "ref_rotation_before_throttle_pct": round(100 * b)}

    def maintenance_throttle(me, ref):
        a, b = _med(me, "maintenance_throttle_s"), _med(ref, "maintenance_throttle_s") if ref else None
        if a is None or a < 0.3 or (b is not None and a < b + 0.25):
            return None
        return {"maintenance_throttle_s": a, "ref_maintenance_throttle_s": b}

    def grip_gap(me, ref):
        """A dip in combined g between braking and turning (tyres 'go quiet'), and your own laps pay for it."""
        a, b, r = _med(me, "grip_gap_frac"), _med(ref, "grip_gap_frac") if ref else None, _r(me, "grip_gap_frac")
        if a is None or a < 0.08 or r is None or r < 0.4 or (b is not None and a < b + 0.04):
            return None
        return {"grip_gap_frac": a, "ref_grip_gap_frac": b, "own_r_with_time": r}

    def downshift_spread(me, ref):
        c = (me.get("consistency") or {}).get("last_downshift_vs_apex_m")
        if not c or c["n"] < 5 or c["iqr"] <= 15.0:
            return None
        return {"last_downshift_iqr_m": c["iqr"], "laps": c["n"], "last_downshift_vs_apex_m": c["median"],
                "ref_last_downshift_vs_apex_m": _med(ref, "last_downshift_vs_apex_m") if ref else None}

    return [
        ("grip_gap_braking_to_turning", "entry", "Grip gap between braking and turning", "Combined grip dips as the brake comes off before the steering takes over; your slower laps have the bigger dip", grip_gap, "weakness", "grip_gap_frac"),
        ("inconsistent_downshifts", "braking", "Downshifts land in a different place every lap", "The last downshift before the corner moves by more than 15 m (IQR) lap to lap, so the entry balance changes every lap", downshift_spread, "weakness", "last_downshift_vs_apex_m"),
        ("rotation_snap", "rotation", "Rotation snapped in, not built", "The car's rotation jumps right after turn-in instead of building as speed falls (closing spiral)", rotation_snap, "weakness", "rotation_jerk_dps2"),
        ("brakes_then_turns", "rotation", "Brake straight, then turn", "Little speed is shed between turn-in and peak rotation; the reference keeps slowing while the car rotates", brakes_then_turns, "weakness", "kmh_lost_turn_in_to_mrp"),
        ("rotates_at_lower_speed", "rotation", "Rotates at a lower speed", "Peak rotation (MRP) happens at a lower speed than the reference", rotates_slower, "weakness", "mrp_kmh"),
        ("throttle_before_rotation", "exit", "Throttle before the car has rotated", "Throttle comes in before the maximum rotation point", throttle_before_rotation, "weakness", "throttle_on_vs_mrp_m"),
        ("accelerates_before_half_rotation", "exit", "Accelerating before half the rotation is done", "Throttle comes in with less than half of the corner's rotation done; the reference rotates more on the brakes first", accelerates_before_half_rotation, "weakness", "rotation_before_throttle_frac"),
        ("maintenance_throttle", "exit", "Part throttle that doesn't accelerate", "Throttle held part-way after the slowest point while the car isn't accelerating", maintenance_throttle, "weakness", "maintenance_throttle_s"),
        ("slow_brake_build", "braking", "Slow brake build", "Full brake pressure arrives late after the braking point", slow_build, "weakness", "brake_ramp_m"),
        ("second_brake_application", "braking", "Brake, release, brake again", "A second brake application near turn-in (classic 'brake too early, then re-brake')", rebrake, "weakness", "rebrake_peak"),
        ("lift_gap_before_brake", "braking", "Lift, pause, then brake", "Neither pedal between lifting and braking: coasting at top speed", lift_gap, "weakness", "lift_gap_s"),
        ("brake_overlap", "braking", "Brake while still on throttle", "Braking starts with the throttle still past half, longer than the reference (left-foot handover)", overlap_more, "style", "brake_overlap_s"),
        ("ref_brake_overlap", "braking", "Reference brakes before lifting", "The reference is already braking with the throttle still past half; you lift first, so pressure starts building later", ref_overlaps, "style", "brake_at_lift"),
        ("no_trail", "braking", "No trail braking", "Brake fully released before turn-in where the reference trails", no_trail, "style", "brake_at_turn_in"),
        ("heavy_trail_lock", "braking", "Heavy trail locks the fronts", "Front wheels lock on entry on most laps", heavy_trail, "weakness", "entry_lock_min"),
        ("hero_entry", "entry", "Hero entry, slower middle", "Faster at turn-in but lower minimum speed", hero_entry, "weakness", "vmin_kmh"),
        ("over_slowing", "entry", "Over-slowing early", "Lower minimum speed reached earlier than the reference", over_slow, "weakness", "vmin_kmh"),
        ("late_full_throttle", "exit", "Late full throttle", "Full throttle (that stays) comes later than the reference", late_throttle, "weakness", "full_throttle_m"),
        ("early_full_throttle", "exit", "Early, committed throttle", "Full throttle earlier than the reference", early_throttle_strength, "strength", "full_throttle_m"),
        ("throttle_lifts", "exit", "Throttle lifts after committing", "Throttle drops after the first application on most laps", lifts, "weakness", "throttle_lifts"),
        ("coasting", "exit", "Coasting between pedals", "Time with neither pedal between brake release and throttle", coasting, "weakness", "coast_s"),
        ("waits_for_straight_wheel", "rotation", "Waits for a straight wheel", "Full throttle only once the wheel is straight; the reference unwinds on throttle", waits_straight, "weakness", "full_throttle_m"),
        ("wide_apex", "line", "Apex further from the inside", "Inside wheel further from the apex edge than the reference", apex_wide, "style", "apex_margin_m"),
        ("exit_width_unused", "line", "Exit width left unused", "Further from the exit edge than the reference", exit_unused, "style", "exit_margin_m"),
        ("braking_over_crest", "terrain", "Braking over a crest", "Still braking where a crest unloads the car", crest_braking, "weakness", "rebrake_peak"),
        ("inconsistent_corner", "consistency", "Inconsistent corner", "Large lap-to-lap spread in minimum speed or braking point", inconsistent, "weakness", "vmin_kmh"),
    ]


def detect(analysis: Dict[str, Any], *, me: Optional[str] = None, ref: Optional[str] = None) -> Dict[str, Any]:
    me = me or (analysis.get("labels") or {}).get("me")
    ref = ref if ref is not None else (analysis.get("labels") or {}).get("ref")
    drivers = analysis.get("drivers") or {}
    mine = (drivers.get(me) or {}).get("corners") or {}
    theirs = (drivers.get(ref) or {}).get("corners") or {} if ref else {}
    loss = {f"{r['corner']}#{r['index']}": r["loss_s"] for r in analysis.get("corner_loss_best_vs_ref") or []}
    habits: Dict[str, Habit] = {}
    for hid, group, title, detail, fn, polarity, metric in _rules():
        for key, c in mine.items():
            rc = theirs.get(key)
            ev = fn(c, rc)
            if not ev:
                continue
            h = habits.setdefault(hid, Habit(hid, group, title, detail, polarity))
            own_r = _r(c, metric)
            h.instances.append(Instance(corner=_name(key), key=key, evidence=ev,
                                        lap_fraction=1.0, loss_s=loss.get(key), own_r=own_r))
    out = []
    for h in habits.values():
        repeat_ok = len(h.instances) >= 3 or any(i.evidence.get("laps_with_second_application", 1) >= 0.5 for i in h.instances)
        if not repeat_ok and len(h.instances) < 2:
            # single-corner pattern: keep only if it is a consistent per-lap pattern (fraction evidence)
            if not any(k.startswith("laps_") for i in h.instances for k in i.evidence):
                continue
        # polarity from pace: weakness needs a cost; strength needs a gain
        if h.polarity == "weakness" and h.pace_impact_s <= 0.02 and not any((i.own_r or 0) > 0.4 for i in h.instances):
            h.polarity = "style"
        if h.polarity == "strength":
            gains = [i.loss_s for i in h.instances if i.loss_s is not None]
            if not gains or sum(gains) > 0:
                h.polarity = "style"
        out.append(h.to_json())
    out.sort(key=lambda h: ({"weakness": 0, "strength": 1, "style": 2}[h["polarity"]], -h["pace_impact_s"]))
    return {"schema": SCHEMA, "driver": me, "reference": ref, "track": analysis.get("track"), "habits": out}
