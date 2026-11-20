import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from external.query_tools.acc_ingest.setup_hints import (  # noqa: E402
    diff_setup_json,
    infer_setup_hints,
)


def test_front_grain_low_psi_prioritizes_pressure_not_dampers():
    delta = {
        "symptom": "front_grain",
        "front_grain": True,
        "low_front_hot_psi": True,
    }
    hints = infer_setup_hints(delta, car_id="ferrari_296_gt3")
    levers = [h["lever"] for h in hints if not h.get("rejected")]
    assert levers
    assert levers[0] in ("PRESSURE_FRONT", "BRAKE_DUCT_FRONT")
    assert not any("BUMP" in lev or "REBOUND" in lev for lev in levers)


def test_calm_only_tc_without_pace_evidence_rejected():
    hints = infer_setup_hints({"calm_only_tc": True}, car_id="ferrari_296_gt3")
    assert len(hints) == 1
    assert hints[0].get("rejected") is True

    hints_calm_req = infer_setup_hints({"calm_tc_request": True}, car_id="ferrari_296_gt3")
    assert hints_calm_req[0].get("rejected") is True

    with_tc = infer_setup_hints(
        {"calm_only_tc": True, "tc_cutting": True},
        car_id="ferrari_296_gt3",
    )
    assert any(h.get("lever") == "TC2" for h in with_tc if not h.get("rejected"))


def test_diff_setup_json_returns_changed_keys():
    a = {"tyres": {"PRESSURE_FRONT": 27.0}, "electronics": {"TC1": 3}}
    b = {"tyres": {"PRESSURE_FRONT": 27.5}, "electronics": {"TC1": 3}}
    diffs = diff_setup_json(a, b)
    keys = {d["key"] for d in diffs}
    assert "tyres.PRESSURE_FRONT" in keys
    assert all(d["a"] != d["b"] for d in diffs)


def test_296_steering_lock_400_in_electronics_skill():
    skill_path = os.path.join(
        ROOT,
        ".agents",
        "skills",
        "vre-acc-electronics",
        "SKILL.md",
    )
    with open(skill_path, encoding="utf-8") as fh:
        text = fh.read()
    assert "400" in text
    assert "steering_lock" in text.lower() or "steering lock" in text.lower()