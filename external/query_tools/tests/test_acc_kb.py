import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ACC_CFG = os.path.join(ROOT, "ac_app", "config", "acc")
if ACC_CFG not in sys.path:
    sys.path.insert(0, ACC_CFG)

import kb_loader  # noqa: E402


def test_reject_pre_19_pressure_advice_without_26_27_window():
    legacy = "Use pre-1.9 meta: 27.8 psi hot all around for consistency."
    assert kb_loader.reject_pre_19_advice(legacy) is True

    current = "On slicks, target 26-27 psi hot after a stint — pace-first."
    assert kb_loader.reject_pre_19_advice(current) is False


def test_ferrari_296_steering_lock_is_400():
    profile = kb_loader.load_car_profile("ferrari_296_gt3")
    assert profile["steering_lock_deg"] == 400


def test_dry_pressure_window_is_26_27():
    kb = kb_loader.load_kb()
    window = kb["tyre_pressure_windows_psi"]["dry_hot"]
    assert window["min"] == 26.0
    assert window["max"] == 27.0