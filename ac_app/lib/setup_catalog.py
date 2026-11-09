# ac_app/lib/setup_catalog.py
# Python 3.3 compatible — stdlib only

import json
import os
import re


_MIRROR = {"LF": "RF", "RF": "LF", "LR": "RR", "RR": "LR"}


class SetupLever(object):
    __slots__ = (
        "section", "name", "tab", "tier", "min_val", "max_val",
        "step", "default", "lever_id", "lut", "ext_controller", "encoding",
    )

    def __init__(self, data):
        self.section = data.get("section", "")
        self.name = data.get("name", self.section)
        self.tab = data.get("tab", "")
        self.tier = data.get("tier")
        self.min_val = data.get("min")
        self.max_val = data.get("max")
        self.step = data.get("step", 1)
        self.default = data.get("default")
        self.lever_id = data.get("id")
        self.lut = data.get("lut")
        self.ext_controller = data.get("ext_controller")
        self.encoding = data.get("encoding", "raw")


class SetupCatalog(object):
    """Car setup lever registry with symptom-based recommendations."""

    TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}

    def __init__(self, car_config_path=None, symptom_map_path=None):
        self.car_id = ""
        self.display_name = ""
        self.car_config = {}
        self.levers = {}
        self.symptom_map = {}
        self.tradeoffs = {}
        self.custom_script_id_map = {}
        if car_config_path:
            self.load_car_config(car_config_path)
        if symptom_map_path:
            self.load_symptom_map(symptom_map_path)

    def load_car_config(self, path):
        with open(path, "r") as fh:
            self.load_car_profile(json.load(fh))

    def load_car_profile(self, profile):
        self.car_config = profile or {}
        self.car_id = self.car_config.get("car_id", "")
        self.display_name = self.car_config.get("display_name", "")
        self.custom_script_id_map = self.car_config.get("custom_script_id_map", {})
        self.levers = {}
        for item in self.car_config.get("levers", []):
            lever = SetupLever(item)
            self.levers[lever.section] = lever

    def load_symptom_map(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            self.symptom_map = json.load(fh)

    def load_tradeoffs(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self.tradeoffs = json.load(fh)
        except (IOError, ValueError):
            self.tradeoffs = {}

    def is_at_limit(self, section, current_value, delta):
        applied, _new_val = self.validate_delta(section, current_value, delta)
        return applied == 0 and delta != 0

    def tradeoff_moves(self, section, delta, symptom):
        section = self.resolve_section(section)
        entry = self.tradeoffs.get(section, {})
        if delta > 0:
            bucket = entry.get("max", {})
        elif delta < 0:
            bucket = entry.get("min", {})
        else:
            return []
        moves = bucket.get(symptom, [])
        if not moves:
            moves = bucket.get("any", [])
        return moves

    def item_delta(self, item, section=None):
        """Delta in setup-file units. `steps` = in-game clicks (car-agnostic); `delta` = raw units."""
        if "steps" not in item:
            return item.get("delta", 0)
        lever = self.lever(self.resolve_section(section or item.get("section", "")))
        step = lever.step if lever is not None and lever.step else 1
        return item["steps"] * step

    @staticmethod
    def mirror_section(section):
        """LF<->RF / LR<->RR counterpart for per-corner levers, else None."""
        if section.startswith("PRESSURE_"):
            return None
        suffix = section[-2:]
        if len(section) > 3 and section[-3] == "_" and suffix in _MIRROR:
            return section[:-2] + _MIRROR[suffix]
        return None

    def build_tradeoff_deltas(self, move, current_values):
        """Return list of (section, delta, new_val, reason) from a tradeoff move."""
        out = []
        reason = move.get("reason", "Limit reached — alternate balance path")
        for item in move.get("deltas", []):
            section = self.resolve_section(item.get("section", ""))
            cur = current_values.get(section, 0)
            d, nv = self.validate_delta(section, cur, self.item_delta(item, section))
            if d != 0:
                out.append((section, d, nv, reason))
        return out

    def all_levers(self):
        return list(self.levers.values())

    def lever(self, section):
        return self.levers.get(section)

    def resolve_section(self, section_or_id):
        if section_or_id in self.levers:
            return section_or_id
        for logical, physical in self.custom_script_id_map.items():
            if logical == section_or_id or physical == section_or_id:
                return physical
        aliases = self.symptom_map.get("custom_script_aliases", {})
        if section_or_id in aliases:
            return aliases[section_or_id]
        return section_or_id

    def validate_delta(self, section, current_value, delta):
        section = self.resolve_section(section)
        lever = self.lever(section)
        if lever is None:
            return 0, current_value
        try:
            cur = float(current_value)
        except (TypeError, ValueError):
            cur = 0.0
        try:
            d = float(delta)
        except (TypeError, ValueError):
            d = 0.0
        new_val = cur + d
        if lever.min_val is not None and new_val < lever.min_val:
            new_val = lever.min_val
            d = new_val - cur
        if lever.max_val is not None and new_val > lever.max_val:
            new_val = lever.max_val
            d = new_val - cur
        if lever.step and lever.step > 0 and lever.min_val is not None:
            steps = round((new_val - lever.min_val) / float(lever.step))
            new_val = lever.min_val + steps * float(lever.step)
            d = new_val - cur
        return d, new_val

    def recommend(self, symptom, phase, tier_max="B"):
        phase_key = phase if phase in ("entry", "mid", "exit", "straight", "any") else "any"
        symptom_data = self.symptom_map.get(symptom, {})
        candidates = symptom_data.get(phase_key, symptom_data.get("any", []))
        max_rank = self.TIER_ORDER.get(tier_max, 1)
        ranked = []
        for item in candidates:
            section = self.resolve_section(item.get("section", ""))
            lever = self.lever(section)
            if lever is None:
                continue
            tier = item.get("tier", lever.tier or "B")
            if self.TIER_ORDER.get(tier, 9) > max_rank:
                continue
            ranked.append({
                "section": section,
                "delta": self.item_delta(item, section),
                "tier": tier,
                "reason": item.get("reason", ""),
                "name": lever.name,
            })
        return ranked

    @staticmethod
    def parse_setup_ini(text):
        sections = {}
        current = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("//") or line.startswith(";"):
                continue
            m = re.match(r"\[([^\]]+)\]", line)
            if m:
                current = m.group(1)
                sections[current] = {}
                continue
            if current and "=" in line:
                k, v = line.split("=", 1)
                sections[current][k.strip()] = v.strip()
        return sections

    def read_current_values(self, ini_path):
        with open(ini_path, "r") as fh:
            text = fh.read()
        parsed = self.parse_setup_ini(text)
        values = {}
        for section, props in parsed.items():
            if "VALUE" in props:
                raw = props["VALUE"]
                try:
                    if "." in raw:
                        values[section] = float(raw)
                    else:
                        values[section] = int(raw)
                except ValueError:
                    values[section] = raw
        return values

    def describe_change(self, section, old_value, new_value):
        lever = self.lever(self.resolve_section(section))
        name = lever.name if lever else section
        return "%s: %s -> %s" % (name, old_value, new_value)

    @classmethod
    def default_paths(cls, car_id="rss_formula_hybrid_x_2026"):
        base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        return (
            os.path.join(base, "cars", "%s.json" % car_id),
            os.path.join(base, "setup_symptom_map.json"),
        )
