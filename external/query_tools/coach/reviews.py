"""Video-review documents for Lap Studio: schema, grounding validation, automatic breakdown.

A review is an ordered list of *scenes*. Each scene frames a stretch of track (``s0_m``-``s1_m``, metres
from the S/F line), says which laps to show and how (same place / same moment, playback rate),
where to pause and what to say, what to draw (pins, zones, arrows, text at metres), and which data
backs it (``citations``: dotted paths into analysis / coaching / habits / limits).

Grounding rule (enforced by ``validate``): every number in a scene's narration or callouts must match
a numeric value inside one of the scene's cited objects (within 1 % or 0.6 units). That keeps AI-written
reviews tied to the data.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

SCHEMA = "vre.review.v1"
NUM = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?")
OVERLAY_KINDS = {"pin", "zone", "arrow", "text", "line"}


def _resolve(sources: Dict[str, Any], path: str) -> Any:
    head, *rest = path.split(".", 1)
    node = sources.get(head)
    if not rest:
        return node
    for part in rest[0].split("."):
        if node is None:
            return None
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(node, dict):
            if part in node:
                node = node[part]
            else:
                # keys may themselves contain dots-free '#' ids like "La Source#0"
                node = next((v for k, v in node.items() if k.replace(" ", "_") == part), None)
        else:
            return None
    return node


def _numbers(obj: Any, out: Optional[List[float]] = None) -> List[float]:
    out = [] if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers(v, out)
    elif isinstance(obj, str):
        out.extend(float(x) for x in NUM.findall(obj))
    return out


def _supported(raw: str, pool: Iterable[float]) -> bool:
    """A written number is supported if it rounds from a cited value at the precision it is written with."""
    x = float(raw)
    dec = len(raw.split(".")[1]) if "." in raw else 0
    tol = 0.6 * 10 ** (-dec)
    for v in pool:
        for cand in (v, abs(v), v * 100.0, abs(v) * 100.0):  # allow % ↔ fraction and magnitudes
            if abs(x - cand) <= max(tol, 0.01 * abs(cand) if dec == 0 else tol):
                return True
    return False


def validate(review: Dict[str, Any], sources: Dict[str, Any], *, track_length_m: Optional[float] = None) -> List[str]:
    """Return a list of problems (empty = valid)."""
    errs: List[str] = []
    if review.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA}")
    scenes = review.get("scenes") or []
    if not scenes:
        errs.append("a review needs at least one scene")
    for i, sc in enumerate(scenes):
        tag = f"scene {i} ({sc.get('title', '?')})"
        s0, s1 = sc.get("s0_m"), sc.get("s1_m")
        if not isinstance(s0, (int, float)) or not isinstance(s1, (int, float)) or s1 <= s0:
            errs.append(f"{tag}: s0_m < s1_m required")
        elif track_length_m and (s0 < -5 or s1 > track_length_m + 5):
            errs.append(f"{tag}: window outside the lap")
        if sc.get("mode", "dist") not in ("dist", "time"):
            errs.append(f"{tag}: mode must be 'dist' or 'time'")
        cites = sc.get("citations") or []
        if not cites:
            errs.append(f"{tag}: needs citations")
        pool: List[float] = []
        for c in cites:
            node = _resolve(sources, c)
            if node is None:
                errs.append(f"{tag}: citation not found: {c}")
            else:
                _numbers(node, pool)
        texts = [sc.get("narration", "")] + [p.get("text", "") for p in sc.get("pauses") or []] + \
                [o.get("text", "") for o in sc.get("overlays") or []]
        for t in texts:
            for raw in NUM.findall(t or ""):
                x = float(raw)
                if abs(x) < 3 and "." not in raw:   # small counts ("2 fixes", "1 lap") are not data claims
                    continue
                if not _supported(raw.lstrip("+"), pool):
                    errs.append(f"{tag}: number {raw} in '{t[:60]}' is not in the cited data")
        for o in sc.get("overlays") or []:
            if o.get("kind") not in OVERLAY_KINDS:
                errs.append(f"{tag}: overlay kind must be one of {sorted(OVERLAY_KINDS)}")
            if "at_m" in o and isinstance(s0, (int, float)) and not (s0 - 50 <= o["at_m"] <= s1 + 50):
                errs.append(f"{tag}: overlay at {o['at_m']} m is outside the scene")
    return errs


def _fmt(x: Optional[float], nd=0) -> str:
    return "—" if x is None else (f"{x:.{nd}f}")


def auto_breakdown(analysis: Dict[str, Any], coaching: Dict[str, Any], *, max_scenes: int = 5) -> Dict[str, Any]:
    """A coach-style review generated from the data: one scene per biggest loss, fixes first."""
    labels = analysis.get("labels") or {}
    me, ref = labels.get("me"), labels.get("ref")
    wins = {f"{w['corner']}#{w['index']}": w for w in analysis.get("windows") or []}
    scenes: List[Dict[str, Any]] = []
    fix_keys = [f["corner_key"] for f in coaching.get("fixes") or []]
    loss_rows = sorted(analysis.get("corner_loss_best_vs_ref") or [], key=lambda r: -r["loss_s"])
    order = fix_keys + [f"{r['corner']}#{r['index']}" for r in loss_rows if f"{r['corner']}#{r['index']}" not in fix_keys]
    loss_by_key = {f"{r['corner']}#{r['index']}": r for r in loss_rows}
    for key in order[:max_scenes]:
        w = wins.get(key)
        if not w:
            continue
        mine = ((analysis.get("drivers") or {}).get(me) or {}).get("corners", {}).get(key, {}).get("best_lap") or {}
        theirs = ((analysis.get("drivers") or {}).get(ref) or {}).get("corners", {}).get(key, {}).get("best_lap") or {} if ref else {}
        loss = loss_by_key.get(key, {}).get("loss_s")
        idx = list((analysis.get("drivers") or {}).get(me, {}).get("corners", {}).keys()).index(key) if key in (analysis.get("drivers") or {}).get(me, {}).get("corners", {}) else None
        cites = [f"analysis.drivers.{me}.corners.{key}.best_lap"]
        if ref:
            cites.append(f"analysis.drivers.{ref}.corners.{key}.best_lap")
        loss_idx = next((i for i, r in enumerate(analysis.get("corner_loss_best_vs_ref") or [])
                         if f"{r['corner']}#{r['index']}" == key), None)
        if loss_idx is not None:
            cites.append(f"analysis.corner_loss_best_vs_ref.{loss_idx}")
        pauses, overlays = [], []
        lm = (coaching.get("landmarks") or {}).get(key)
        if lm:
            cites.append(f"coaching.landmarks.{key}")
            for ev in ("brake_on_m", "brake_full_m", "turn_in_m", "throttle_on_m"):
                row = lm["events"].get(ev)
                if row:
                    pauses.append({"at_m": row["me_m"], "driver": "me", "event": ev, "text": row["text"]})
        else:
            for who, ev, color in ((ref, theirs, "ref"), (me, mine, "me")):
                if who and ev and ev.get("brake_full_m") is not None:
                    pauses.append({"at_m": ev["brake_full_m"], "driver": color,
                                   "text": f"{who}: full brake at {_fmt(ev['brake_full_m'])} m ({_fmt(ev.get('brake_ramp_m'))} m after braking starts)"})
        for who, ev, color in ((ref, theirs, "ref"), (me, mine, "me")):
            if not who or not ev:
                continue
            if ev.get("vmin_m") is not None:
                overlays.append({"kind": "pin", "at_m": ev["vmin_m"], "driver": color,
                                 "text": f"{who} slowest {_fmt(ev.get('vmin_kmh'), 1)} km/h"})
        for ev_name, color in (("brake_on_m", "me"),):
            row = (lm or {}).get("events", {}).get(ev_name) if lm else None
            if row and row.get("ref_m") is not None and abs(row["gap_m"]) >= 1:
                overlays.append({"kind": "zone", "s0_m": min(row["me_m"], row["ref_m"]), "s1_m": max(row["me_m"], row["ref_m"]),
                                 "driver": color, "text": "braking-point gap"})
        fix = next((f for f in coaching.get("fixes") or [] if f["corner_key"] == key), None)
        narration = (f"{w['corner']}: {_fmt(loss, 2)} s lost to {ref} through this section." if ref and loss is not None
                     else f"{w['corner']}.")
        if fix:
            narration += " " + fix["drill"]
            cites.append(f"coaching.fixes.{(coaching.get('fixes') or []).index(fix)}")
        scenes.append({
            "title": w["corner"], "corner_key": key, "s0_m": w["s0_m"], "s1_m": min(w["s1_m"], w["s0_m"] + 450.0),
            "mode": "dist", "rate": 0.5, "laps": {"me": "best", "ref": "best"},
            "narration": narration, "pauses": sorted(pauses, key=lambda p: p["at_m"]), "overlays": overlays,
            "lanes": ["delta", "speed", "brake", "throttle", "steer"], "citations": cites, "author": "auto",
        })
    return {"schema": SCHEMA, "title": "Automatic breakdown", "author": "auto", "scenes": scenes,
            "note": "generated from analysis + coaching; edit or extend in Lap Studio or via the viewer MCP tools"}
