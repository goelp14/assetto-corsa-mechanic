"""Technique vs setup vs terrain, per corner, pace first (any car/track, AC or ACC).

Rules (in order):
1. A corner whose loss coincides with a technique weakness habit → technique (fix the driving first).
2. A loss tied to a crest/dip interaction → terrain (technique or line around the feature).
3. A symptom that repeats across ≥ 3 corners where technique looks clean → setup candidate, with one
   lever, its mechanism, an A/B protocol and what in the data should change. Never "calmer" as a goal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import physics

SCHEMA = "vre.diagnosis.v1"


def diagnose(analysis: Dict[str, Any], habits: Dict[str, Any], setup: Optional[Dict[str, Any]] = None,
             *, max_setup_changes: int = 2) -> Dict[str, Any]:
    weak = [h for h in habits.get("habits") or [] if h["polarity"] == "weakness"]
    by_corner: Dict[str, List[str]] = {}
    for h in weak:
        for c in h["corners"]:
            by_corner.setdefault(c, []).append(h["id"])
    rows = []
    for r in analysis.get("corner_loss_best_vs_ref") or []:
        if r["loss_s"] <= 0.05:
            continue
        hs = by_corner.get(r["corner"], [])
        terrain = "braking_over_crest" in hs
        kind = "terrain" if terrain else ("technique" if hs else "unexplained")
        rows.append({"corner": r["corner"], "loss_s": r["loss_s"], "cause": kind, "habits": hs})
    clean = [r for r in rows if r["cause"] == "unexplained"]
    me = (analysis.get("labels") or {}).get("me")
    cs = (analysis.get("car_state") or {}).get(me) or {}
    recs: List[Dict[str, Any]] = []
    bb = physics.braking_balance_check(cs, (setup or {}).get("fingerprint")) if setup else None
    if bb and bb.get("lever"):
        recs.append({"lever": "advancedSetup.mechanicalBalance.brakeBias", "direction": bb["direction"],
                     "why": bb["verdict"], "test": bb["test"],
                     "expect": "front and rear braking slip closer to their load shares; same or shorter stops",
                     "evidence": bb, "calibrated": False})
    ug = cs.get("understeer_gradient_deg_per_g")
    if ug is not None and len(clean) >= 3 and ug > 1.5:
        recs.append({"lever": "advancedSetup.mechanicalBalance.aRBFront", "direction": "softer front bar (−1 to −2 clicks)",
                     "why": f"understeer gradient {ug}°/g with mid-corner losses in {len(clean)} corners where technique looks clean",
                     "mechanism": physics.MECHANISM["aRBFront"],
                     "test": "5 laps each way, same fuel/tyres; keep only if lap time or minimum speeds improve",
                     "expect": "lower understeer gradient, higher minimum speed in medium corners", "calibrated": False})
    return {
        "schema": SCHEMA,
        "corners": rows,
        "setup_recommendations": recs[:max_setup_changes],
        "order": "fix technique corners first; setup only for patterns that repeat with clean technique",
        "unexplained_corners": [r["corner"] for r in clean],
    }
