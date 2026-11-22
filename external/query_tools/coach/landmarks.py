"""Turn raw lap distances into driver language: boards, corner anchors and car lengths (any car/track).

A driver can't act on "brake at 266 m vs 260 m". They can act on "you brake at about the 100 m board;
the faster lap brakes a car length later". This module does that translation.

Anchors (track-fixed, in metres from the S/F line, from the generated track pack):
    corner start (geometric turn-in onset) and apex.
Braking boards:
    * curated — a track notes file may give real board positions per corner
      (``"boards_m": {"100": 266.0}``, metres from S/F). Those are used as-is.
    * otherwise no board is named. Board spacing is fixed (50/100/150/200 m…) but where the count
      starts differs per corner, so geometry alone puts them in the wrong place (tested: Spa La Source
      came out as the "50 m board" against the guides' 100-120 m). Braking is then described as
      metres before the apex of the corner it leads into, which is exact and track-fixed.
Each event is anchored to the corner it physically belongs to (a braking point to the next apex,
other events to the corner they happen in), not to the analysis window's name, so a combined
window like "Campus" (which also contains Fagnes) still says "into Fagnes".
Car length comes from the car's measured wheelbase (GT-class overhangs: length ≈ 1.72 × wheelbase),
falling back to 4.6 m.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

EVENT_WORDS = {
    "brake_on_m": "start braking",
    "brake_full_m": "reach full brake",
    "brake_off_m": "release the brake",
    "turn_in_m": "turn in",
    "vmin_m": "reach minimum speed",
    "throttle_on_m": "pick up the throttle",
    "full_throttle_m": "reach full throttle",
}


def car_length_m(car_state: Optional[Dict[str, Any]]) -> float:
    wb = (car_state or {}).get("wheelbase_m")
    return round(1.72 * wb, 2) if isinstance(wb, (int, float)) and 2.0 < wb < 3.5 else 4.6


def car_lengths(dist_m: float, car_len: float) -> str:
    """'half a car length', 'a car length', '3 car lengths' — rounded the way a driver would say it."""
    n = abs(dist_m) / car_len
    if n < 0.35:
        return "less than half a car length"
    if n < 0.75:
        return "half a car length"
    if n < 1.4:
        return "a car length"
    if n < 2.5:
        return "two car lengths"
    return f"{round(n):d} car lengths"


def corner_for(corners: List[Dict[str, Any]], key_or_name: str) -> Optional[Dict[str, Any]]:
    name = key_or_name.split("#")[0]
    idx = key_or_name.split("#")[1] if "#" in key_or_name else None
    if idx is not None and idx.isdigit() and int(idx) < len(corners):
        c = corners[int(idx)]
        if name in (c.get("display_name"), c.get("name")):
            return c
    return next((c for c in corners if name in (c.get("display_name"), c.get("name"))), None)


def board_phrase(s_m: float, corner: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Where a point sits relative to curated braking boards of the corner (None when not curated)."""
    curated = ((corner.get("notes") or {}).get("boards_m")) or {}
    if not curated:
        return None
    bs, b = min(((float(v), int(k)) for k, v in curated.items()), key=lambda x: abs(x[0] - s_m))
    off = s_m - bs  # + = after (closer to the corner)
    text = f"at the {b} m board" if abs(off) <= 6 else f"{abs(off):.0f} m {'after' if off > 0 else 'before'} the {b} m board"
    return {"board_m": b, "offset_m": round(off, 1), "source": "curated", "text": text}


def anchor_corner(s_m: float, event: str, corners: List[Dict[str, Any]], fallback: Dict[str, Any]) -> Dict[str, Any]:
    """The corner an event physically belongs to."""
    if not corners:
        return fallback
    if event in ("brake_on_m", "brake_full_m"):
        ahead = [c for c in corners if c["apex_m"] > s_m + 5]
        return min(ahead, key=lambda c: c["apex_m"]) if ahead else fallback
    inside = [c for c in corners if c["start_m"] - 40 <= s_m <= c["end_m"] + 60]
    if inside:
        return min(inside, key=lambda c: abs(c["apex_m"] - s_m))
    return min(corners, key=lambda c: abs(c["apex_m"] - s_m))


def _name(c: Dict[str, Any]) -> str:
    return c.get("display_name") or c.get("name") or "the corner"


def anchor_phrase(s_m: float, corner: Dict[str, Any], *, braking: bool = False) -> Dict[str, Any]:
    """Distance to the corner's apex (negative = before), phrased for the event type."""
    d_start = s_m - corner["start_m"]
    d_apex = s_m - corner["apex_m"]
    nm = _name(corner)
    if braking or d_apex < -3:
        text = f"{-d_apex:.0f} m before the {nm} apex" if d_apex < -3 else f"at the {nm} apex"
    elif d_apex <= 3:
        text = f"at the {nm} apex"
    else:
        text = f"{d_apex:.0f} m after the {nm} apex"
    return {"corner": nm, "to_corner_m": round(d_start, 1), "to_apex_m": round(d_apex, 1), "text": text}


def compare_event(event: str, me_s: Optional[float], ref_s: Optional[float], corner: Dict[str, Any],
                  car_len: float, me: str = "you", ref: str = "the reference",
                  corners: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """One sentence comparing where two laps do the same thing in a corner."""
    if me_s is None:
        return None
    verb = EVENT_WORDS.get(event, event)
    braking = event in ("brake_on_m", "brake_full_m")
    anchor = anchor_corner(me_s, event, corners or [], corner)
    out: Dict[str, Any] = {"event": event, "me_m": me_s, "anchor": anchor_phrase(me_s, anchor, braking=braking)}
    board = board_phrase(me_s, anchor) if event == "brake_on_m" else None
    where = out["anchor"]["text"]
    if board:
        out["board"] = board
        where = f"{board['text']} ({where})"
    text = f"{me.capitalize()} {verb} {where}"
    if ref_s is not None:
        gap = ref_s - me_s  # + = reference does it later on the road
        out.update({"ref_m": ref_s, "gap_m": round(gap, 1), "gap_car_lengths": round(abs(gap) / car_len, 2)})
        if abs(gap) < 0.35 * car_len:
            text += f"; {ref} does it at the same place"
        else:
            later = "later" if gap > 0 else "earlier"
            text += f"; {ref} does it {car_lengths(gap, car_len)} {later} ({abs(gap):.0f} m)"
    out["text"] = text + "."
    return out


def corner_landmarks(corner_key: str, analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """All event comparisons for one corner on the best laps."""
    labels = analysis.get("labels") or {}
    me, ref = labels.get("me"), labels.get("ref")
    corners = [dict(c, start_m=c.get("start_m", c["apex_m"] - 50.0), end_m=c.get("end_m", c["apex_m"] + 50.0))
               for c in (analysis.get("pack") or {}).get("corners") or [] if isinstance(c.get("apex_m"), (int, float))]
    corner = corner_for(corners, corner_key)
    if not corner:
        return None
    d = analysis.get("drivers") or {}
    mine = (((d.get(me) or {}).get("corners") or {}).get(corner_key) or {}).get("best_lap") or {}
    theirs = (((d.get(ref) or {}).get("corners") or {}).get(corner_key) or {}).get("best_lap") or {} if ref else {}
    cl = car_length_m((analysis.get("car_state") or {}).get(me))
    rows = [r for r in (compare_event(ev, mine.get(ev), theirs.get(ev), corner, cl, "you", ref or "the reference", corners)
                        for ev in EVENT_WORDS) if r]
    return {"corner": corner.get("display_name") or corner.get("name"), "start_m": corner["start_m"],
            "apex_m": corner["apex_m"], "car_length_m": cl,
            "boards": "curated" if (corner.get("notes") or {}).get("boards_m") else "none (add boards_m to the track notes)",
            "events": {r["event"]: r for r in rows}}


def all_landmarks(analysis: Dict[str, Any]) -> Dict[str, Any]:
    keys = list(((analysis.get("drivers") or {}).get((analysis.get("labels") or {}).get("me")) or {}).get("corners", {}).keys())
    out = {}
    for k in keys:
        lm = corner_landmarks(k, analysis)
        if lm:
            out[k] = lm
    return out
