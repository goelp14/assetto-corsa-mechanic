import os

from feedback_presenter import FeedbackPresenter


def test_render_early_brake(config_dir):
    fp = FeedbackPresenter(os.path.join(config_dir, "feedback_templates.json"))
    event = fp.render("early_brake", {
        "corner": "Rascasse",
        "corner_name": "Rascasse",
        "brake_cue": "Brake when the second pool kerb is behind you",
        "early_m": 15,
        "wait_s": "0.2",
        "gain_kmh": 4,
        "gain_s": "0.1",
    })
    assert "Rascasse" in event.headline
    assert "pool kerb" not in event.voice  # short voice now
    assert "Brake later" in event.voice
    assert event.voice
