import os
import sys

QT = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
COACH = os.path.join(QT, "coach")
for p in (QT, COACH):
    if p not in sys.path:
        sys.path.insert(0, p)

import driver_lab  # noqa: E402
from coach_service import classify_question  # noqa: E402


def test_classify_routes_setup_and_line_questions():
    assert classify_question("should I move brake bias rearward?") == "setup"
    assert classify_question("is my turn-in point too early, should I be more right?") == "line"
    assert classify_question("why did I spin at turn 7") == "incident"
    assert classify_question("I keep coasting on the exit") == "technique"


def test_corr_sign():
    assert driver_lab.corr([1, 2, 3, 4], [2, 4, 6, 8]) > 0.99
    assert driver_lab.corr([1, 2, 3, 4], [8, 6, 4, 2]) < -0.99
    assert driver_lab.corr([1, 1, 1], [1, 2, 3]) == 0.0


def test_controls_flags_swallowing_brake_gamma(tmp_path, monkeypatch, capsys):
    ini = tmp_path / "controls.ini"
    ini.write_text("[THROTTLE]\nGAMMA=1\n[BRAKES]\nGAMMA=2.4\n[CLUTCH]\nGAMMA=1\n[STEER]\nLOCK=900\n")
    monkeypatch.setenv("VRE_AC_CONTROLS", str(ini))
    assert driver_lab.main(["controls"]) == 0
    out = capsys.readouterr().out
    assert "BRAKES   GAMMA 2.40" in out
    assert "20%->2%" in out
    assert "swallowed" in out


def test_session_spec_lap_range(tmp_path):
    (tmp_path / "laps").mkdir()
    d, rng = driver_lab.Context._parse_spec(str(tmp_path) + ":6-21")
    assert d == str(tmp_path) and rng == (6, 21)
    d, rng = driver_lab.Context._parse_spec(str(tmp_path) + ":23")
    assert rng == (23, 10 ** 6)
    d, rng = driver_lab.Context._parse_spec(str(tmp_path))
    assert rng is None


def _style(**kw):
    m = dict(entry_slide_deg=6.0, slide_helps_r=0.0, brake_at_turn_in=0.2, throttle_ramp_s=1.5, v_ratio=0.8,
             fast_corner_gap_pct=3.0, slow_corner_gap_pct=3.0, coast_rotation_wait_s=0.5, coast_pedal_swap_s=0.5)
    m.update(kw)
    return m


def test_style_labels_rotation_first_and_setup_fit_forbids_stability_levers():
    m = _style(entry_slide_deg=12.0, slide_helps_r=-0.3, throttle_ramp_s=0.8, v_ratio=0.6)
    labels = driver_lab.style_labels(m)
    assert any("rotation-first" in x for x in labels)
    assert any(x.startswith("V-shape") for x in labels)
    assert "do NOT add diff coast lock" in driver_lab.setup_fit(m)


def test_style_labels_pedal_gaps_and_fast_corner_reserve():
    labels = driver_lab.style_labels(_style(coast_rotation_wait_s=1.8, coast_pedal_swap_s=3.5,
                                            fast_corner_gap_pct=6.0, slow_corner_gap_pct=2.0))
    assert any("pedal gaps" in x for x in labels)
    assert any("holds back in fast corners" in x for x in labels)


def test_controls_linear_brake_not_flagged(tmp_path, monkeypatch, capsys):
    ini = tmp_path / "controls.ini"
    ini.write_text("[BRAKES]\nGAMMA=1\n")
    monkeypatch.setenv("VRE_AC_CONTROLS", str(ini))
    driver_lab.main(["controls"])
    assert "swallowed" not in capsys.readouterr().out
