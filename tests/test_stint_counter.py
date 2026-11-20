import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ac_app"))

from lib.stint_counter import StintCounter, SETTLE, COUNTED, SLOW  # noqa: E402


def test_settle_then_count_to_target():
    s = StintCounter(settle_laps=2, target_laps=3)
    assert s.hud_text() == "SETTLE LAP 1/2"
    assert s.on_lap(97000, 97000) == (SETTLE, False)
    assert s.hud_text() == "SETTLE LAP 2/2"
    assert s.on_lap(96000, 96000) == (SETTLE, False)
    assert s.hud_text() == "COUNTED 0/3 - 3 TO GO"
    assert s.on_lap(95500, 95500) == (COUNTED, False)
    assert s.on_lap(95600, 95500) == (COUNTED, False)
    assert s.hud_text() == "COUNTED 2/3 - 1 TO GO"
    assert s.on_lap(95400, 95400) == (COUNTED, True)
    assert s.done and s.hud_text() == "BOX BOX - 3/3 DONE"
    assert s.on_lap(95400, 95400) == (COUNTED, False)


def test_slow_lap_does_not_count():
    s = StintCounter(settle_laps=0, target_laps=5, slow_pct=1.03)
    assert s.on_lap(95000, 95000) == (COUNTED, False)
    assert s.on_lap(99000, 95000) == (SLOW, False)
    assert s.counted == 1
    assert s.hud_text() == "COUNTED 1/5 - 4 TO GO (LAST SLOW)"


def test_reset_starts_new_block():
    s = StintCounter(settle_laps=1, target_laps=1)
    s.on_lap(96000, 96000)
    s.on_lap(95000, 95000)
    assert s.done and s.block == 1
    s.reset()
    assert s.block == 2 and not s.done and s.hud_text() == "SETTLE LAP 1/1"


def test_settle_laps_count_even_when_slow():
    s = StintCounter(settle_laps=1, target_laps=2)
    assert s.on_lap(120000, 95000) == (SETTLE, False)


def test_alert_repeater_spaces_beeps():
    from lib.alert_sound import AlertRepeater
    played = []
    r = AlertRepeater(gap_s=0.5, play=lambda: played.append(1))
    r.tick(0.1)
    assert played == []
    r.trigger(3)
    for _ in range(30):
        r.tick(0.1)
    assert len(played) == 3
