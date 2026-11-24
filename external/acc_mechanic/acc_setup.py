"""ACC setups for the live mechanic: AC-style levers mapped onto ACC setup JSON, and a writer.

The engineer (ac_app) reasons in AC setup sections (``ARB_FRONT``, ``PRESSURE_LF`` …) and values in
setup units. ACC setup files store click indices. Each lever here says where its clicks live in the
JSON and what one click is worth (``unit``) above click 0 (``offset``):

    value = offset + unit × clicks

Only pressures (0.1 psi from ~20.3 psi on GT3) and diff preload (10 Nm from 20 Nm) carry real
units; the rest stay in clicks (offset 0, unit 1). Higher click = stiffer / more / further forward
on every ACC car (see vre-rpy ``setup_files.FIELD_INFO``). Per-car click ranges live in the
game's encrypted data, so only the lower bound (click 0) is enforced.

The writer copies the newest setup you saved for this car + track to ``Auto_Tweak.json`` and
edits the clicks there; you load it from the setup screen like any other setup.
"""

from __future__ import annotations

import copy
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

OUTPUT_NAME = "Auto_Tweak.json"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ACC_CONFIG = os.path.join(REPO, "ac_app", "config", "acc")

_W = ("LF", "RF", "LR", "RR")
_MB = "advancedSetup.mechanicalBalance"
_DAMP = "advancedSetup.dampers"
_AL = "basicSetup.alignment"

ACC_LEVERS: List[Dict[str, Any]] = (
    [
        {"section": "ARB_FRONT", "name": "Front ARB", "tab": "MECHANICAL GRIP", "tier": "A", "path": _MB + ".aRBFront"},
        {"section": "ARB_REAR", "name": "Rear ARB", "tab": "MECHANICAL GRIP", "tier": "A", "path": _MB + ".aRBRear"},
        {"section": "FRONT_BIAS", "name": "Brake bias", "tab": "MECHANICAL GRIP", "tier": "A", "path": _MB + ".brakeBias"},
        {"section": "WING_0", "name": "Splitter", "tab": "AERO", "tier": "A", "path": "advancedSetup.aeroBalance.splitter"},
        {"section": "WING_1", "name": "Rear wing", "tab": "AERO", "tier": "A", "path": "advancedSetup.aeroBalance.rearWing"},
        {"section": "DIFF_PRELOAD", "name": "Diff preload", "tab": "MECHANICAL GRIP", "tier": "A",
         "path": "advancedSetup.drivetrain.preload", "unit": 10.0, "offset": 20.0},
    ]
    + [{"section": "PRESSURE_%s" % w, "name": "Pressure %s" % w, "tab": "TYRES", "tier": "C",
        "path": "basicSetup.tyres.tyrePressure", "index": i, "unit": 0.1, "offset": 20.3} for i, w in enumerate(_W)]
    + [{"section": "CAMBER_%s" % w, "name": "Camber %s" % w, "tab": "TYRES", "tier": "C",
        "path": _AL + ".camber", "index": i} for i, w in enumerate(_W)]
    + [{"section": "TOE_OUT_%s" % w, "name": "Toe %s" % w, "tab": "TYRES", "tier": "C",
        "path": _AL + ".toe", "index": i} for i, w in enumerate(_W)]
    + [{"section": "SPRING_RATE_%s" % w, "name": "Wheel rate %s" % w, "tab": "MECHANICAL GRIP", "tier": "B",
        "path": _MB + ".wheelRate", "index": i} for i, w in enumerate(_W)]
    + [{"section": "DAMP_BUMP_%s" % w, "name": "Slow bump %s" % w, "tab": "DAMPERS", "tier": "B",
        "path": _DAMP + ".bumpSlow", "index": i} for i, w in enumerate(_W)]
    + [{"section": "DAMP_REBOUND_%s" % w, "name": "Slow rebound %s" % w, "tab": "DAMPERS", "tier": "B",
        "path": _DAMP + ".reboundSlow", "index": i} for i, w in enumerate(_W)]
)
LEVERS_BY_SECTION = {lv["section"]: lv for lv in ACC_LEVERS}

# Chassis numbers the dynamics/balance maths needs; per-car files may override ("chassis" block).
GT3_CHASSIS = {
    "wheelbase_m": 2.7, "front_weight_frac": 0.46, "mass_kg": 1300.0,
    "understeer_gradient_K": 0.004, "max_yaw_rate_rad_s": 1.2,
    "max_road_wheel_deg": 16.0, "lat_g_base": 1.6, "lat_g_per_ms": 0.0,
}


# ---------------------------------------------------------------- locating ACC files

def candidate_acc_documents() -> List[str]:
    out = []
    env = os.environ.get("VRE_ACC_DOCUMENTS", "").strip()
    if env:
        out.append(env)
    name = "Assetto Corsa Competizione"
    if sys.platform == "win32":
        home = os.path.expanduser("~")
        for root in (os.environ.get("ONEDRIVE", ""), os.path.join(home, "OneDrive"), home):
            if root:
                out.append(os.path.join(root, "Documents", name))
    else:
        for pattern in ("/mnt/c/Users/*/OneDrive/Documents/" + name, "/mnt/c/Users/*/Documents/" + name):
            out.extend(sorted(glob.glob(pattern)))
    return [p for p in out if os.path.isdir(os.path.join(p, "Setups"))]


def acc_documents() -> Optional[str]:
    c = candidate_acc_documents()
    return c[0] if c else None


def _ci_child(parent: str, name: str) -> Optional[str]:
    """Case-insensitive child directory (ACC track folders mix 'Spa' and 'brands_hatch')."""
    try:
        for entry in os.listdir(parent):
            if entry.lower() == name.lower() and os.path.isdir(os.path.join(parent, entry)):
                return os.path.join(parent, entry)
    except OSError:
        pass
    return None


# ---------------------------------------------------------------- JSON <-> values

def _get(doc, path):
    node = doc
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _clicks(doc, lever) -> Optional[int]:
    v = _get(doc, lever["path"])
    if "index" in lever:
        if not isinstance(v, list) or lever["index"] >= len(v):
            return None
        v = v[lever["index"]]
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _set_clicks(doc, lever, clicks: int) -> bool:
    parts = lever["path"].split(".")
    node = doc
    for part in parts[:-1]:
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            return False
    key = parts[-1]
    if not isinstance(node, dict) or key not in node:
        return False
    if "index" in lever:
        arr = node[key]
        if not isinstance(arr, list) or lever["index"] >= len(arr):
            return False
        arr[lever["index"]] = clicks
    else:
        node[key] = clicks
    return True


def to_value(lever, clicks: int) -> float:
    v = lever.get("offset", 0.0) + lever.get("unit", 1.0) * clicks
    return round(v, 3) if lever.get("unit", 1.0) != 1.0 else int(clicks)


def to_clicks(lever, value: float) -> int:
    return max(0, int(round((float(value) - lever.get("offset", 0.0)) / lever.get("unit", 1.0))))


def read_values(path: str) -> Dict[str, float]:
    """Setup values per AC section from an ACC setup JSON (empty if unreadable)."""
    if not path or not os.path.isfile(path) or not path.lower().endswith(".json"):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return {}
    out = {}
    for lv in ACC_LEVERS:
        c = _clicks(doc, lv)
        if c is not None:
            out[lv["section"]] = to_value(lv, c)
    return out


# ---------------------------------------------------------------- car profile

def _load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def build_profile(car_id: str, sample_setup: Optional[str] = None) -> Dict[str, Any]:
    """AC-format car profile for an ACC car (levers limited to those present in its setup JSON)."""
    kb = _load_json(os.path.join(ACC_CONFIG, "gt3_physics_kb.json"), {}) or {}
    car = _load_json(os.path.join(ACC_CONFIG, "cars", "%s.json" % car_id), {}) or {}
    prof: Dict[str, Any] = dict(GT3_CHASSIS)
    prof.update(car.get("chassis", {}))
    prof["car_id"] = car_id
    prof["display_name"] = car.get("display_name", car_id)
    prof["game"] = "acc"
    lock = car.get("steering_lock_deg")
    if lock and "max_road_wheel_deg" not in car.get("chassis", {}):
        prof["steering_lock_deg"] = lock

    tw = (car.get("tyre_traits", {}) or {}).get("temp_window_c") or {}
    kb_tw = kb.get("tyre_temp_window_c", {})
    lo = float(tw.get("min", kb_tw.get("operating_min", 70.0)))
    hi = float(tw.get("max", kb_tw.get("operating_max", 100.0)))
    window = {"core_temp_ideal_min_c": lo, "core_temp_ideal_max_c": hi,
              "core_temp_cold_c": lo - 10.0, "core_temp_hot_c": hi + 8.0}
    prof["tyre_window"] = window
    prof["tyre_windows_by_compound"] = {"dry_compound": window}
    pt = ((car.get("tyre_traits", {}) or {}).get("pressure_targets_psi") or kb.get("tyre_pressure_windows_psi", {})).get("dry_hot", {})
    mid = (float(pt.get("min", 26.0)) + float(pt.get("max", 27.0))) / 2.0
    prof["pressure_ideal_psi"] = {"front": mid, "rear": mid}

    doc = _load_json(sample_setup, None) if sample_setup else None
    levers = []
    for lv in ACC_LEVERS:
        if doc is not None and _clicks(doc, lv) is None:
            continue
        unit, offset = lv.get("unit", 1.0), lv.get("offset", 0.0)
        levers.append({
            "section": lv["section"], "name": lv["name"], "tab": lv["tab"], "tier": lv["tier"],
            "encoding": "acc_clicks", "min": offset, "max": None, "step": unit,
        })
    prof["levers"] = levers
    prof["custom_script_id_map"] = {}
    return prof


def acc_symptom_map(symptom_map: Dict[str, Any]) -> Dict[str, Any]:
    """AC symptom map with raw-unit deltas turned into one click in the same direction.

    AC entries give most moves in ``steps`` (clicks); a few (diff preload) use raw AC units, which
    mean nothing for ACC's click scale.
    """
    out = copy.deepcopy(symptom_map)
    for sym in out.values():
        if not isinstance(sym, dict):
            continue
        for items in sym.values():
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and "delta" in it and "steps" not in it:
                    d = float(it.pop("delta"))
                    it["steps"] = 1 if d > 0 else (-1 if d < 0 else 0)
    return out


def acc_tradeoffs(tradeoffs: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(tradeoffs)
    for entry in out.values():
        if not isinstance(entry, dict):
            continue
        for bucket in entry.values():
            if not isinstance(bucket, dict):
                continue
            for moves in bucket.values():
                for mv in moves if isinstance(moves, list) else []:
                    for it in mv.get("deltas", []) if isinstance(mv, dict) else []:
                        if "delta" in it and "steps" not in it:
                            d = float(it.pop("delta"))
                            it["steps"] = 1 if d > 0 else (-1 if d < 0 else 0)
    return out


# ---------------------------------------------------------------- writer

class AccSetupWriter:
    """Same interface ac_app uses on its AC ``SetupWriter``, writing ACC setup JSON."""

    def __init__(self, car_id: str = "", documents: Optional[str] = None):
        self.car_id = car_id
        self._documents = documents
        self._active_setups_root = None
        self.last_base = None

    def _docs(self):
        if self._documents is None:
            self._documents = acc_documents() or ""
        return self._documents

    def _documents_setups_dir(self):
        docs = self._docs()
        if not docs:
            return ""
        root = os.path.join(docs, "Setups")
        return _ci_child(root, self.car_id) or os.path.join(root, self.car_id)

    def locate_track_folder(self, track_folder):
        car_dir = self._documents_setups_dir()
        if not car_dir or not os.path.isdir(car_dir):
            return None, None
        folder = _ci_child(car_dir, track_folder)
        return (car_dir, folder) if folder else (car_dir, None)

    def resolve_output_path(self, track_folder):
        car_dir = self._documents_setups_dir()
        if not car_dir:
            return ""
        folder = _ci_child(car_dir, track_folder) or os.path.join(car_dir, track_folder)
        return os.path.join(folder, OUTPUT_NAME)

    def _list_setups(self, folder):
        try:
            names = os.listdir(folder)
        except OSError:
            return []
        return [n for n in names if n.lower().endswith(".json") and n.lower() != OUTPUT_NAME.lower()]

    def find_base_ini(self, track_folder):
        """Newest setup you saved for this car + track (or $VRE_BASE_SETUP by file name)."""
        _root, folder = self.locate_track_folder(track_folder)
        if not folder:
            return None
        env = os.environ.get("VRE_BASE_SETUP", "").strip()
        if env and os.path.isfile(os.path.join(folder, env)):
            self.last_base = os.path.join(folder, env)
            return self.last_base
        best, best_t = None, -1.0
        for name in self._list_setups(folder):
            p = os.path.join(folder, name)
            try:
                t = os.path.getmtime(p)
            except OSError:
                continue
            if t > best_t:
                best, best_t = p, t
        self.last_base = best
        return best

    def sample_setup(self) -> Optional[str]:
        car_dir = self._documents_setups_dir()
        files = sorted(glob.glob(os.path.join(car_dir, "*", "*.json"))) if car_dir else []
        return files[0] if files else None

    def clone_base(self, base_path, output_path):
        with open(base_path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        self._write(output_path, doc)
        return output_path

    @staticmethod
    def _write(path, doc):
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=4)
        os.replace(tmp, path)

    def apply_deltas(self, path, deltas, lap=0, reason=""):
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        for d in deltas:
            lv = LEVERS_BY_SECTION.get(d.section)
            if lv is None:
                continue
            _set_clicks(doc, lv, to_clicks(lv, d.new_value))
        self._write(path, doc)
        return path

    def write_auto_tweak(self, base_path, track_folder, deltas, lap=0, reason=""):
        out = self.resolve_output_path(track_folder)
        if not os.path.isfile(out):
            self.clone_base(base_path, out)
        return self.apply_deltas(out, deltas, lap=lap, reason=reason)

    def ensure_auto_tweak(self, track_folder) -> Tuple[str, str]:
        out = self.resolve_output_path(track_folder)
        if out and os.path.isfile(out):
            return out, ""
        base = self.find_base_ini(track_folder)
        if not base:
            return "", "no_base_setup"
        try:
            self.clone_base(base, out)
        except (OSError, ValueError) as exc:
            return "", "clone_failed:%s" % exc
        return (out, "") if os.path.isfile(out) else ("", "clone_missing_after_write")
