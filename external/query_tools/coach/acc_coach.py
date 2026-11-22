"""One command from replay analysis to coaching: habits → fixes → diagnosis → driver profile.

    python -m external.query_tools.coach.acc_coach --analysis analysis.json [--setup setup.json] \\
        --out coaching.json [--update-profile]

``analysis.json`` comes from ``vre-rpy analyze``; ``setup.json`` (optional) from ``vre-rpy setup``.
Works for any car/track. The driver profile (``ac_app/data/driver_profile.json`` or
``VRE_DRIVER_PROFILE``) is shared with AC sessions; ACC entries carry ``"game": "acc"``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .diagnosis import diagnose
from .distiller import distill
from .habits import detect

REPO = Path(__file__).resolve().parents[3]


def profile_path() -> Path:
    return Path(os.environ.get("VRE_DRIVER_PROFILE") or REPO / "ac_app" / "data" / "driver_profile.json")


def load_profile() -> Dict[str, Any]:
    p = profile_path()
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"preferences": [], "entries": []}


def profile_entry(analysis: Dict[str, Any], habits: Dict[str, Any]) -> Dict[str, Any]:
    me = (analysis.get("labels") or {}).get("me")
    d = (analysis.get("drivers") or {}).get(me) or {}
    cs = (analysis.get("car_state") or {}).get(me) or {}
    metrics: Dict[str, float] = {}
    for key in ("brake_ramp_m", "rebrake_peak", "coast_s", "peak_slip_deg", "vmin_vs_apex_m"):
        vals = [c["consistency"][key]["median"] for c in (d.get("corners") or {}).values()
                if key in (c.get("consistency") or {})]
        if vals:
            metrics[key] = round(sum(vals) / len(vals), 3)
    if d.get("lap_ms"):
        best, med = min(d["lap_ms"]), sorted(d["lap_ms"])[len(d["lap_ms"]) // 2]
        metrics.update({"best_lap_s": best / 1000.0, "median_lap_s": med / 1000.0,
                        "consistency_pct": round(100 * (med - best) / best, 3), "laps": len(d["lap_ms"])})
    return {
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "game": "acc",
        "car": ((analysis.get("drivers") or {}) and (cs.get("car") or None)) or analysis.get("car"),
        "track": analysis.get("track"),
        "reference": (analysis.get("labels") or {}).get("ref"),
        "metrics": metrics,
        "habits": [{"id": h["id"], "polarity": h["polarity"], "pace_impact_s": h["pace_impact_s"],
                    "repeats": h["repeats"]} for h in habits.get("habits") or []],
        "car_state": {k: cs.get(k) for k in ("understeer_gradient_deg_per_g", "aero_front_share", "mass_kg")},
    }


def persistent_habits(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Weakness habits seen on ≥ 2 different tracks or cars: the real habits."""
    seen: Dict[str, set] = {}
    for e in profile.get("entries") or []:
        for h in e.get("habits") or []:
            if h.get("polarity") == "weakness":
                seen.setdefault(h["id"], set()).add((e.get("track"), e.get("car")))
    return [{"id": k, "where": sorted(map(str, v))} for k, v in seen.items() if len(v) >= 2]


def run(analysis: Dict[str, Any], setup: Optional[Dict[str, Any]] = None, *, update_profile: bool = False) -> Dict[str, Any]:
    habits = detect(analysis)
    prof = load_profile()
    coaching = distill(analysis, habits, profile=prof, setup=setup)
    coaching["habits"] = habits
    coaching["diagnosis"] = diagnose(analysis, habits, setup)
    if update_profile:
        prof.setdefault("entries", []).append(profile_entry(analysis, habits))
        p = profile_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(prof, indent=1), encoding="utf-8")
    coaching["persistent_habits"] = persistent_habits(prof)
    coaching["preferences"] = prof.get("preferences") or []
    return coaching


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--analysis", type=Path, required=True)
    ap.add_argument("--setup", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--update-profile", action="store_true")
    a = ap.parse_args(argv)
    analysis = json.loads(a.analysis.read_text(encoding="utf-8"))
    setup = json.loads(a.setup.read_text(encoding="utf-8")) if a.setup else None
    out = run(analysis, setup, update_profile=a.update_profile)
    a.out.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    for f in out["fixes"]:
        print(f"FIX  {f['title']}  ({f['pace_impact_s']:.2f}s, {f['confidence']})\n     drill: {f['drill']}\n     success: {f['success_metric']}")
    for r in out["diagnosis"]["setup_recommendations"]:
        print(f"SETUP {r['lever'].split('.')[-1]}: {r['direction']} — {r['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
