# ac_app/lib/setup_constraints.py
# Setup law enforcement before INI writes (Python 3.3).

import json
import os


class SetupConstraints(object):
    """Block contradictory or premature setup changes."""

    def __init__(self, config_path=None):
        self.tyres_before_chassis = True
        self.blocked_axle_sections = {}
        self.contradictions = []
        self.speed_class_aero = {}
        if config_path:
            self.load(config_path)

    def load(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.tyres_before_chassis = data.get("tyres_before_chassis", True)
        self.blocked_axle_sections = data.get("blocked_axle_sections", {})
        self.contradictions = data.get("contradictions", [])
        self.speed_class_aero = data.get("speed_class_aero", {})

    @classmethod
    def default_path(cls):
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "setup_constraints.json",
        )

    def blocked_axles(self, tyre_symptoms):
        axles = set()
        for sym in tyre_symptoms or []:
            low = sym.lower()
            if "front" in low or low.startswith("lf") or low.startswith("rf"):
                axles.add("front")
            if "rear" in low or low.startswith("lr") or low.startswith("rr"):
                axles.add("rear")
        return axles

    def is_blocked(self, section, symptom, context=None):
        context = context or {}
        tyre_axles = context.get("tyre_axles") or set()
        active_symptoms = context.get("active_symptoms") or []
        speed_class = context.get("speed_class", "medium")

        if self.tyres_before_chassis and tyre_axles:
            for axle in tyre_axles:
                blocked = self.blocked_axle_sections.get(axle, [])
                if section in blocked:
                    return True, "tyre_window_%s" % axle

        all_symptoms = list(active_symptoms)
        if symptom and symptom not in all_symptoms:
            all_symptoms.append(symptom)
        for rule in self.contradictions:
            needed = set(rule.get("symptoms", []))
            if needed.issubset(set(all_symptoms)):
                if section in rule.get("block_sections", []):
                    return True, "contradiction"

        allowed = self.speed_class_aero.get(speed_class)
        if allowed and section in ("WING_0", "WING_1"):
            if section not in allowed:
                return True, "speed_class_%s" % speed_class

        return False, ""

    def filter_candidates(self, candidates, symptom, context=None):
        out = []
        for cand in candidates:
            section = cand.get("section", "")
            blocked, _reason = self.is_blocked(section, symptom, context)
            if not blocked:
                out.append(cand)
        return out
