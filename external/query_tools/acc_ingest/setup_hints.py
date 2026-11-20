"""ACC setup JSON diff and KB-backed setup hints (pace-first)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ACC_CFG = os.path.join(_REPO, "ac_app", "config", "acc")
if _ACC_CFG not in sys.path:
    sys.path.insert(0, _ACC_CFG)

import kb_loader  # noqa: E402

# Symptom keys → ordered hint templates (priority = list order).
_SYMPTOM_HINTS: dict[str, list[dict[str, Any]]] = {
    "front_grain": [
        {
            "lever": "PRESSURE_FRONT",
            "direction": "increase_cold_to_hit_hot_window",
            "why": "Hot front psi below 26 psi and inside-shoulder grain on telemetry.",
            "expected_pace_effect": "More consistent front grip once hot band 26–27 psi is reached.",
            "require_ab_test": True,
            "source_fact_id": "tyre_dry_hot_pressure",
            "requires_delta": ("low_front_hot_psi",),
        },
        {
            "lever": "BRAKE_DUCT_FRONT",
            "direction": "close_or_reduce_if_under_temp",
            "why": "Front core temps below 70 °C after 3+ flying laps.",
            "expected_pace_effect": "Faster front heat build → graining risk drops without softening dampers.",
            "require_ab_test": True,
            "source_fact_id": "tyre_temp_window",
            "requires_delta": ("slow_front_heat",),
        },
        {
            "lever": "CAMBER_FRONT",
            "direction": "adjust_for_even_temp",
            "why": "Grain persists with pressures in window — uneven shoulder temps.",
            "expected_pace_effect": "Even wear across stint; pace if grain was costing mid-corner.",
            "require_ab_test": True,
            "source_fact_id": "tyre_temp_window",
        },
    ],
    "low_front_hot_psi": [
        {
            "lever": "PRESSURE_FRONT",
            "direction": "increase",
            "why": "Stint median LF/RF hot psi under 26.0.",
            "expected_pace_effect": "Front contact patch stability into braking zones.",
            "require_ab_test": True,
            "source_fact_id": "tyre_dry_hot_pressure",
        },
    ],
    "slow_front_heat": [
        {
            "lever": "BRAKE_DUCT_FRONT",
            "direction": "reduce_cooling",
            "why": "Front tyre_core stuck below operating band despite flying laps.",
            "expected_pace_effect": "Earlier entry into 70–100 °C window.",
            "require_ab_test": True,
            "source_fact_id": "tyre_temp_window",
        },
        {
            "lever": "PRESSURE_FRONT",
            "direction": "small_increase",
            "why": "Under-temp fronts often need pressure + heat before aero changes.",
            "expected_pace_effect": "Pace once fronts stay in window through a stint.",
            "require_ab_test": True,
            "source_fact_id": "tyre_dry_hot_pressure",
        },
    ],
    "entry_understeer": [
        {
            "lever": "BRAKE_BIAS",
            "direction": "rearward",
            "why": "High entry speed with low front lat G vs steering — rotation cost on entry.",
            "expected_pace_effect": "Faster rotation into apex if front tyres not already overheating.",
            "require_ab_test": True,
            "source_fact_id": "brakes_bias_migration",
            "requires_delta": ("entry_understeer",),
        },
        {
            "lever": "ARB_FRONT / ARB_REAR",
            "direction": "mechanical_balance",
            "why": "Entry push without exit traction loss.",
            "expected_pace_effect": "Mid-corner speed if roll stiffness was limiting front.",
            "require_ab_test": True,
            "source_fact_id": "springs_arb_mechanical_balance",
        },
    ],
    "mid_push": [
        {
            "lever": "ARB_FRONT / ARB_REAR",
            "direction": "reduce_front_or_stiffen_rear",
            "why": "Lat G plateau mid-corner with excess steering.",
            "expected_pace_effect": "Mid-corner minimum speed if push costs sector time.",
            "require_ab_test": True,
            "source_fact_id": "springs_arb_mechanical_balance",
            "requires_delta": ("mid_push",),
        },
    ],
    "exit_snap": [
        {
            "lever": "DIFF_EXIT",
            "direction": "reduce_lock_or_preload",
            "why": "Yaw spike on throttle with rear slip trace.",
            "expected_pace_effect": "Earlier throttle without snap if diff was binding rotation.",
            "require_ab_test": True,
            "source_fact_id": "diff_entry_mid_exit",
            "requires_delta": ("exit_snap",),
        },
    ],
    "tc_cutting": [
        {
            "lever": "TC2",
            "direction": "increase_slip_tolerance",
            "why": "TC intervention counts high on exit with measurable lap-time loss.",
            "expected_pace_effect": "Earlier full throttle when mechanical grip supports it.",
            "require_ab_test": True,
            "source_fact_id": "electronics_tc_abs",
            "requires_delta": ("tc_cutting",),
        },
        {
            "lever": "DIFF_EXIT",
            "direction": "mechanical_first",
            "why": "TC fighting diff exit lock — fix mechanical before more TC1 cut.",
            "expected_pace_effect": "Less TC dependency on power.",
            "require_ab_test": True,
            "source_fact_id": "diff_entry_mid_exit",
            "requires_delta": ("tc_cutting",),
        },
    ],
    "abs_locking": [
        {
            "lever": "ABS",
            "direction": "increase_map",
            "why": "ABS active under trail with lock spikes and entry time loss.",
            "expected_pace_effect": "Shorter braking zone if lock was limiting decel.",
            "require_ab_test": True,
            "source_fact_id": "electronics_tc_abs",
            "requires_delta": ("abs_locking",),
        },
    ],
}

# Low-priority levers when tyre evidence is present — pace-first ordering.
_DEPRIORITIZE_WHEN_TYRE_EVIDENCE = frozenset(
    {
        "Bump/rebound",
        "BUMP",
        "REBOUND",
        "dampers",
    }
)

_CALM_ONLY_LEVERS = frozenset({"TC1", "TC2", "ABS"})


def _flatten_keys(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(val, dict):
                out.update(_flatten_keys(val, path))
            else:
                out[path] = val
    else:
        out[prefix or "value"] = obj
    return out


def diff_setup_json(a: dict, b: dict) -> list[dict]:
    """Return literal key diffs between two ACC setup JSON dicts."""
    flat_a = _flatten_keys(a)
    flat_b = _flatten_keys(b)
    keys = sorted(set(flat_a) | set(flat_b))
    diffs: list[dict] = []
    for key in keys:
        va = flat_a.get(key, _MISSING)
        vb = flat_b.get(key, _MISSING)
        if va != vb:
            diffs.append({"key": key, "a": va, "b": vb})
    return diffs


_MISSING = object()


def _delta_flag(delta_summary: dict, name: str) -> bool:
    val = delta_summary.get(name)
    if val is True:
        return True
    if isinstance(val, (int, float)) and val > 0:
        return True
    return False


def _pace_evidence_present(delta_summary: dict) -> bool:
    pace_keys = (
        "tc_cutting",
        "abs_locking",
        "exit_snap",
        "entry_understeer",
        "mid_push",
        "front_grain",
        "low_front_hot_psi",
        "lap_time_delta_s",
        "sector_loss_s",
    )
    return any(_delta_flag(delta_summary, k) for k in pace_keys)


def infer_setup_hints(
    delta_summary: dict,
    car_id: str = "ferrari_296_gt3",
) -> list[dict]:
    """
    Map telemetry/symptom flags to setup hints using GT3 KB + car profile.
    """
    kb = kb_loader.load_kb()
    profile = kb_loader.load_car_profile(car_id)
    _ = kb  # doctrine + facts validated at load time
    _ = profile

    if delta_summary.get("calm_tc_request") or delta_summary.get("calm_only_tc"):
        if not _delta_flag(delta_summary, "tc_cutting"):
            return [
                {
                    "rejected": True,
                    "reason": (
                        "pace-first: no TC/ABS bump for calm alone — "
                        "need tc_cutting or lap-time evidence"
                    ),
                }
            ]

    tyre_evidence = any(
        _delta_flag(delta_summary, k)
        for k in ("front_grain", "low_front_hot_psi", "slow_front_heat")
    )

    symptom = delta_summary.get("symptom")
    templates: list[dict[str, Any]] = []
    if symptom and symptom in _SYMPTOM_HINTS:
        templates.extend(_SYMPTOM_HINTS[symptom])
    for key, hints in _SYMPTOM_HINTS.items():
        if key == symptom:
            continue
        if _delta_flag(delta_summary, key):
            templates.extend(hints)

    seen_levers: set[str] = set()
    out: list[dict] = []
    for tpl in templates:
        req = tpl.get("requires_delta")
        if req and not all(_delta_flag(delta_summary, r) for r in req):
            continue
        lever_key = tpl["lever"].split("/")[0].strip()
        if lever_key in seen_levers:
            continue
        seen_levers.add(lever_key)

        lever = tpl["lever"]
        if tyre_evidence:
            if any(d in lever for d in _DEPRIORITIZE_WHEN_TYRE_EVIDENCE):
                continue
        if lever.split()[0] in _CALM_ONLY_LEVERS and not _pace_evidence_present(delta_summary):
            continue

        hint = {k: v for k, v in tpl.items() if k != "requires_delta"}
        out.append(hint)

    return out


def _symptom_to_delta(symptom: str) -> dict:
    base: dict[str, Any] = {"symptom": symptom}
    # Default evidence flags so CLI is useful for coaching walkthroughs.
    defaults = {
        "front_grain": {"front_grain": True, "low_front_hot_psi": True},
        "slow_front_heat": {"slow_front_heat": True},
        "tc_cutting": {"tc_cutting": True},
        "abs_locking": {"abs_locking": True},
        "entry_understeer": {"entry_understeer": True},
        "exit_snap": {"exit_snap": True},
        "mid_push": {"mid_push": True},
        "low_front_hot_psi": {"low_front_hot_psi": True},
        "calm_only_tc": {"calm_only_tc": True},
    }
    base.update(defaults.get(symptom, {symptom: True}))
    return base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACC setup hints from symptoms or setup diff")
    parser.add_argument("--symptom", help="Symptom key (e.g. front_grain)")
    parser.add_argument("--car", default="ferrari_296_gt3")
    parser.add_argument("--setup-a", type=str, help="Path to setup JSON A")
    parser.add_argument("--setup-b", type=str, help="Path to setup JSON B")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args(argv)

    result: dict[str, Any] = {"car_id": args.car, "hints": [], "diffs": []}

    if args.setup_a and args.setup_b:
        with open(args.setup_a, encoding="utf-8") as fh:
            setup_a = json.load(fh)
        with open(args.setup_b, encoding="utf-8") as fh:
            setup_b = json.load(fh)
        result["diffs"] = diff_setup_json(setup_a, setup_b)

    if args.symptom:
        delta = _symptom_to_delta(args.symptom)
        result["delta_summary"] = delta
        result["hints"] = infer_setup_hints(delta, car_id=args.car)

    if not args.symptom and not (args.setup_a and args.setup_b):
        parser.error("Provide --symptom and/or --setup-a with --setup-b")

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())