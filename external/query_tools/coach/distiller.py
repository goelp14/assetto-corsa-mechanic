"""Turn habits into 1-2 pace-first fixes that correct a wrong mental model (any car/track, AC or ACC).

Each mental model has: what the driver tends to believe, the habits that reveal it, the correct
model, the physics reason, a drill, a visual cue and a success metric. Numbers in every fix come
from the analysis (cited by corner key and metric); cues come from track notes or terrain when
available, otherwise they are marked "unverified — pick a landmark in-game".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import landmarks, physics

SCHEMA = "vre.coaching.v1"

MENTAL_MODELS: List[Dict[str, Any]] = [
    {"id": "build_brake_smoothly", "habits": ["slow_brake_build"],
     "belief": "Brake pressure should build up smoothly",
     "correct": "Peak pressure belongs at the start of the stop, when the car is fastest and has the most "
                "load and downforce; then bleed it off as speed falls (HPAcademy brake-trace practice).",
     "why": "Grip is highest at the start of the braking zone; pressure that arrives late wastes it and the car "
            "reaches turn-in too fast, so you brake again or over-slow.",
     "drill": "Same braking point, but reach full pressure within ~{ref_ramp:.0f} m ({ref_ramp_cl}) of touching the pedal; you take {you_ramp:.0f} m ({you_ramp_cl}).",
     "metric": "full pressure within {target:.0f} m ({target_cl}) of touching the brake, on 4 of 5 laps", "group": "braking"},
    {"id": "brake_later_is_faster", "habits": ["hero_entry", "second_brake_application"],
     "belief": "Braking later / carrying more speed to turn-in is faster",
     "correct": "Minimum speed and exit decide the time, not the turn-in speed. Arrive at turn-in slower, "
                "with the car rotated, and you carry more speed through the slowest point.",
     "why": "Too much entry speed forces a second brake application or a wide, slow middle; the loss shows up "
            "on the following straight.",
     "drill": "Turn in at about {ref_ti:.0f} km/h (you: {you_ti:.0f}); aim for a minimum of {ref_vmin:.0f} km/h (you: {you_vmin:.0f}).",
     "metric": "minimum speed ≥ {target_vmin:.0f} km/h with no second brake application", "group": "entry"},
    {"id": "wait_for_straight_wheel", "habits": ["waits_for_straight_wheel", "late_full_throttle"],
     "belief": "Full throttle only once the wheel is straight",
     "correct": "Once the car is pointed, go to throttle and unwind the wheel with it; the throttle and the "
                "unwind happen together.",
     "why": "Waiting for a straight wheel delays the acceleration phase that carries onto the straight.",
     "drill": "Commit to full throttle with lock still on: the reference is flat {ref_ft_phrase}; you are flat {you_ft_phrase}. Squeeze to full as you unwind.",
     "metric": "full throttle before the wheel is straight on 4 of 5 laps", "group": "exit"},
    {"id": "brake_through_crest", "habits": ["braking_over_crest"],
     "belief": "Keep braking the same over every part of the braking zone",
     "correct": "A crest takes load off the tyres: brake hard before it and be done (or very light) over it.",
     "why": "With less load the tyres lock or slide earlier, so braking over the crest stops you less and unsettles the car.",
     "drill": "Finish the hard braking before the crest {crest_where}.", "metric": "brake < 30% at the crest on 4 of 5 laps",
     "group": "terrain"},
    {"id": "coasting_is_neutral", "habits": ["coasting"],
     "belief": "Coasting between the pedals is harmless",
     "correct": "A coasting car has neither front load from braking nor rear load from throttle; overlap the "
                "release of the brake with the start of the throttle.",
     "why": "Unloaded tyres give less grip for the same steering; the car drifts wide and you wait longer for throttle.",
     "drill": "Cut the gap between brake release and throttle from {you_coast:.2f} s to under 0.2 s.",
     "metric": "under 0.2 s between brake release and throttle, on 4 of 5 laps", "group": "exit"},
    {"id": "one_commitment", "habits": ["throttle_lifts"],
     "belief": "Feeding the throttle in and out is careful driving",
     "correct": "Wait until the car is pointed, then one committed application that stays.",
     "why": "Each lift unloads the rear and restarts the acceleration.", "drill": "One throttle application per exit.",
     "metric": "one throttle application per exit (no lifts) on 4 of 5 laps", "group": "exit"},
    {"id": "consistency_first", "habits": ["inconsistent_corner"],
     "belief": "Each lap is a fresh attempt at the corner",
     "correct": "Lock in one reference (braking marker, turn-in point) and repeat it; spread is where the time is.",
     "why": "Large lap-to-lap spread means some laps throw away the speed the best laps show is available.",
     "drill": "Pick one braking marker and one turn-in marker and hit them for 5 laps.",
     "metric": "minimum-speed spread (IQR) under 2 km/h", "group": "consistency"},
]


def _cues(analysis: Dict[str, Any], corner: str) -> List[str]:
    notes = ((analysis.get("pack") or {}).get("corners") or [])
    for c in notes:
        if (c.get("display_name") or "") == corner and c.get("notes"):
            return list(c["notes"].get("cues") or [])
    return []


def _corner_data(analysis, who, key):
    return ((analysis.get("drivers") or {}).get(who) or {}).get("corners", {}).get(key) or {}


def _val(c, k):
    v = (c.get("consistency") or {}).get(k)
    if v:
        return v["median"]
    return (c.get("best_lap") or {}).get(k)


def build_fix(mm, habit, analysis) -> Optional[Dict[str, Any]]:
    labels = analysis.get("labels") or {}
    me, ref = labels.get("me"), labels.get("ref")
    inst = max(habit["instances"], key=lambda i: (i.get("loss_s") or 0))
    key, corner = inst["key"], inst["corner"]
    a, b = _corner_data(analysis, me, key), _corner_data(analysis, ref, key) if ref else {}
    nums = {
        "you_ramp": _val(a, "brake_ramp_m") or 0, "ref_ramp": _val(b, "brake_ramp_m") or 0,
        "you_ti": _val(a, "turn_in_kmh") or 0, "ref_ti": _val(b, "turn_in_kmh") or 0,
        "you_vmin": _val(a, "vmin_kmh") or 0, "ref_vmin": _val(b, "vmin_kmh") or 0,
        "you_ft": _val(a, "full_throttle_m") or 0, "ref_ft": _val(b, "full_throttle_m") or 0,
        "you_coast": _val(a, "coast_s") or 0,
    }
    nums["target"] = max(nums["ref_ramp"] * 1.2, 10.0)
    nums["target_vmin"] = nums["ref_vmin"] - 1.0 if nums["ref_vmin"] else nums["you_vmin"] + 2.0
    crest = next((t for l in (a.get("laps") or []) for t in (l.get("terrain") or []) if t["kind"] == "crest"), None)
    nums["crest_m"] = crest["at_m"] if crest else 0
    # driver-language positions: relative to the corner apex and in car lengths, not raw lap metres
    corners = [dict(c, start_m=c.get("start_m", c["apex_m"] - 50.0), end_m=c.get("end_m", c["apex_m"] + 50.0))
               for c in (analysis.get("pack") or {}).get("corners") or [] if isinstance(c.get("apex_m"), (int, float))]
    cl = landmarks.car_length_m((analysis.get("car_state") or {}).get(me))
    nums["you_ramp_cl"] = landmarks.car_lengths(nums["you_ramp"], cl)
    nums["ref_ramp_cl"] = landmarks.car_lengths(nums["ref_ramp"], cl)
    nums["target_cl"] = landmarks.car_lengths(nums["target"], cl)
    gap = nums["you_ft"] - nums["ref_ft"]
    nums.update(ft_gap=abs(gap), ft_gap_cl=landmarks.car_lengths(gap, cl), ft_dir="earlier" if gap > 0 else "later",
                ft_where_ref="where the reference does", crest_where=f"at {nums['crest_m']:.0f} m")
    ev = inst.get("evidence") or {}
    if "you_full_throttle_vs_straight_m" in ev:
        def _ph(d: float) -> str:  # d = full-throttle point minus wheel-straight point (m)
            if abs(d) < 3:
                return "as the wheel straightens"
            return f"{abs(d):.0f} m ({landmarks.car_lengths(d, cl)}) {'before' if d < 0 else 'after'} the wheel is straight"
        nums.update(you_ft_phrase=_ph(ev["you_full_throttle_vs_straight_m"]), ref_ft_phrase=_ph(ev.get("ref") or 0.0))
    if corners and nums["ref_ft"]:
        anc = landmarks.anchor_corner(nums["ref_ft"], "full_throttle_m", corners, corners[0])
        nums["ft_where_ref"] = landmarks.anchor_phrase(nums["ref_ft"], anc)["text"]
    if corners and crest:
        anc = landmarks.anchor_corner(crest["at_m"], "turn_in_m", corners, corners[0])
        nums["crest_where"] = landmarks.anchor_phrase(crest["at_m"], anc)["text"]
    try:
        drill = mm["drill"].format(**nums)
        metric = mm["metric"].format(**nums)
    except (KeyError, ValueError):
        drill, metric = mm["drill"], mm["metric"]
    cues = _cues(analysis, corner)
    physics_notes = []
    for l in (a.get("best_lap") or {}).get("terrain") or []:
        eff = physics.crest_effect(l.get("expected_dg", 0), None)
        physics_notes.append(f"{l['kind']} at {l['at_m']:.0f} m: {eff['meaning']} (≈{abs(l.get('expected_dg', 0)) * 100:.0f}% load change at {l['speed_kmh']:.0f} km/h; you: brake {l['brake'] * 100:.0f}%, throttle {l['throttle'] * 100:.0f}%)")
    return {
        "id": f"{mm['id']}@{key}",
        "mental_model": mm["id"], "group": mm["group"], "corner": corner, "corner_key": key,
        "title": f"{corner}: {mm['correct'].split('.')[0]}",
        "belief": mm["belief"], "correct_model": mm["correct"], "why": mm["why"],
        "what": {k: v for k, v in inst["evidence"].items()},
        "drill": drill, "success_metric": metric,
        "cues": cues or ["unverified — pick a fixed landmark in-game at the target point"],
        "physics": physics_notes,
        "pace_impact_s": habit["pace_impact_s"], "corner_loss_s": inst.get("loss_s"),
        "repeats": habit["repeats"], "corners_with_habit": habit["corners"],
        "citations": [f"analysis.drivers.{me}.corners.{key}", f"habits.{habit['id']}"],
        "confidence": "proven on these laps" if habit["repeats"] >= 3 or (inst.get("own_r") or 0) > 0.4
                      else "hypothesis — 5-lap test",
    }


def distill(analysis: Dict[str, Any], habits: Dict[str, Any], *, profile: Optional[Dict[str, Any]] = None,
            setup: Optional[Dict[str, Any]] = None, max_fixes: int = 2) -> Dict[str, Any]:
    by_id = {h["id"]: h for h in habits.get("habits") or [] if h["polarity"] == "weakness"}
    prefs = " ".join((profile or {}).get("preferences") or []).lower()
    cands = []
    for mm in MENTAL_MODELS:
        hs = [by_id[h] for h in mm["habits"] if h in by_id]
        if not hs:
            continue
        h = max(hs, key=lambda x: x["pace_impact_s"])
        score = h["pace_impact_s"] * min(1.0, h["repeats"] / 3.0 + 0.34)
        if "stability" in prefs and mm["group"] == "braking":
            score *= 1.0  # pace-first: preferences never promote calming changes
        fix = build_fix(mm, h, analysis)
        if fix:
            fix["score"] = round(score, 3)
            cands.append(fix)
    cands.sort(key=lambda f: -f["score"])
    fixes, used = [], set()
    for f in cands:
        if f["group"] in used:
            continue
        fixes.append(f)
        used.add(f["group"])
        if len(fixes) >= max_fixes:
            break
    later = [f for f in cands if f not in fixes]
    strengths = [h for h in habits.get("habits") or [] if h["polarity"] == "strength"]
    cs = (analysis.get("car_state") or {}).get((analysis.get("labels") or {}).get("me")) or {}
    setup_notes = []
    bb = physics.braking_balance_check(cs, (setup or {}).get("fingerprint")) if setup else None
    if bb:
        setup_notes.append(bb)
    return {
        "schema": SCHEMA, "track": analysis.get("track"), "driver": habits.get("driver"),
        "reference": habits.get("reference"),
        "fixes": fixes, "later": later[:5], "strengths": strengths,
        "setup_checks": setup_notes,
        "car_state": cs,
        "rules": ["at most 2 fixes per session", "every number cites the analysis",
                  "pace first: no change is recommended for being calmer"],
    }
