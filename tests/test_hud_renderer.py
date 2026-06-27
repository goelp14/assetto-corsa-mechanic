from hud_renderer import (
    tyre_fill_ratio, cue_style, sectors_from_indexer, format_delta,
    temp_font_color, format_learn_detail, short_headline, landmark_short,
    format_setup_hud_line, format_setup_pit_detail,
    CUE_STYLES,
)


class _FakeIndexer(object):
    sectors = [
        {"name": "S1", "spline_end": 0.33},
        {"name": "S2", "spline_end": 0.66},
        {"name": "S3", "spline_end": 1.0},
    ]
    corners = []

    def sector_name(self, spline):
        return "S3"


def test_tyre_fill_uses_full_range():
    ratio_cold, _ = tyre_fill_ratio(65, 75, 95, 102, 68)
    ratio_hot, _ = tyre_fill_ratio(100, 75, 95, 102, 68)
    assert ratio_hot > ratio_cold
    assert ratio_cold >= 0.06


def test_temp_font_color_hot():
    c = temp_font_color(110, 75, 95, 102, 68)
    assert c[0] > 0.9


def test_sectors_from_indexer():
    sectors = sectors_from_indexer(_FakeIndexer())
    assert len(sectors) == 3
    assert sectors[0][2] == "S1"


def test_format_delta():
    text, color = format_delta(0.15)
    assert text.startswith("+")
    assert color[0] > 0.9


def test_format_learn_detail():
    class _Snap(object):
        consistency_pct = 72
        target_laps = 3
        clean_laps = 2
        phase = "LEARNING"
        coaching_active = True
        bootstrap_active = False
        corner_name = ""

    detail = format_learn_detail(_Snap())
    assert "72%" in detail
    assert "coaching" in detail
    assert "1 clean" in detail


def test_short_headline_truncates():
    long = "A" * 50
    assert len(short_headline(long)) == 38
    assert short_headline("short") == "short"


def test_landmark_short_brake_cue():
    lm = {"brake_cue": "Brake at the red curb before the barrier"}
    text = landmark_short(lm, "entry", "rascasse", None)
    assert "Brake" in text
    assert len(text) <= 42


def test_format_setup_hud_line():
    note = {
        "section": "WING_0",
        "section_display": "Front Wing",
        "delta": 2,
        "old_value": 12,
        "new_value": 14,
        "reason": "More front downforce for slow corners",
        "source": "bootstrap",
    }
    line = format_setup_hud_line(note)
    assert "BOOT" in line
    assert "Front Wing" in line
    assert "+2" in line
    assert "downforce" in line


def test_format_setup_pit_detail():
    note = {
        "section_display": "Front Wing",
        "delta": 2,
        "old_value": 12,
        "new_value": 14,
        "why": "Monaco needs high front downforce.",
        "action": "Load Auto_Tweak in pits.",
    }
    text = format_setup_pit_detail(note)
    assert "SETUP:" in text
    assert "Why:" in text
    assert "How:" in text
    assert "Monaco" in text
