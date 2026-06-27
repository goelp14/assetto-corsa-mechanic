# ac_app/lib/feedback_presenter.py
# Python 3.3 compatible — stdlib only

import json
import os


class FeedbackEvent(object):
    __slots__ = (
        "type", "priority", "corner", "phase", "headline",
        "what", "why", "action", "expected", "voice", "metadata",
    )

    def __init__(self, type="coaching", priority=1, corner="", phase="",
                 headline="", what="", why="", action="", expected="",
                 voice="", metadata=None):
        self.type = type
        self.priority = priority
        self.corner = corner
        self.phase = phase
        self.headline = headline
        self.what = what
        self.why = why
        self.action = action
        self.expected = expected
        self.voice = voice
        self.metadata = metadata or {}


class FeedbackPresenter(object):
    """Render FeedbackEvent from template keys and evidence dicts."""

    def __init__(self, templates_path=None):
        self.templates = {}
        if templates_path:
            self.load_templates(templates_path)

    def load_templates(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            self.templates = json.load(fh)

    @staticmethod
    def _format_field(template, evidence):
        try:
            return template % evidence
        except (KeyError, TypeError, ValueError):
            return template

    def render(self, template_key, evidence=None):
        evidence = evidence or {}
        tpl = self.templates.get(template_key)
        if tpl is None:
            return FeedbackEvent(
                headline=template_key,
                what=str(evidence),
            )

        merged = dict(evidence)
        if "corner" not in merged:
            merged["corner"] = ""
        if "corner_name" not in merged:
            merged["corner_name"] = merged.get("corner", "")
        for key in ("map", "approach", "brake_cue", "apex_cue", "exit_cue"):
            merged.setdefault(key, "")
        if "delta_sign" not in merged and "delta" in merged:
            d = merged["delta"]
            merged["delta_sign"] = "+" if d >= 0 else ""
            merged["delta_abs"] = abs(d)

        metadata = dict(merged)
        metadata["cue"] = tpl.get("cue", "")

        return FeedbackEvent(
            type=tpl.get("type", "coaching"),
            priority=tpl.get("priority", 1),
            corner=merged.get("corner", ""),
            phase=merged.get("phase", ""),
            headline=self._format_field(tpl.get("headline", ""), merged),
            what=self._format_field(tpl.get("what", ""), merged),
            why=self._format_field(tpl.get("why", ""), merged),
            action=self._format_field(tpl.get("action", ""), merged),
            expected=self._format_field(tpl.get("expected", ""), merged),
            voice=self._format_field(tpl.get("voice", ""), merged),
            metadata=metadata,
        )

    def from_setup_delta(self, delta, corner="", expected=""):
        sign = "+" if delta.delta >= 0 else ""
        evidence = {
            "section_name": delta.section,
            "delta": delta.delta,
            "delta_sign": sign,
            "delta_abs": abs(delta.delta),
            "reason": delta.reason,
            "corner": corner,
            "expected": expected or delta.reason,
        }
        return self.render("setup_tweak", evidence)

    @classmethod
    def default_templates_path(cls):
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "feedback_templates.json",
        )
