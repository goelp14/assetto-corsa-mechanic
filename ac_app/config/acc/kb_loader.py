# ac_app/config/acc/kb_loader.py
# Python 3.3+ compatible — ACC GT3 knowledge base loaders (stdlib only).

import json
import os
import re

_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))

KB_FILENAME = "gt3_physics_kb.json"
ERA_MAP_FILENAME = "physics_era_map.json"
CARS_DIR = "cars"


def _read_json(filename):
    path = os.path.join(_CONFIG_DIR, filename)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _parse_version_tuple(version):
    """Parse dotted ACC version into comparable integer tuple (major, minor, patch)."""
    if not version:
        return (0, 0, 0)
    text = str(version).strip()
    parts = text.split(".")
    nums = []
    for part in parts[:3]:
        try:
            nums.append(int(re.sub(r"[^0-9].*$", "", part)))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def load_kb():
    """Load GT3 physics knowledge base."""
    return _read_json(KB_FILENAME)


def load_era_map():
    """Load ACC physics era map."""
    return _read_json(ERA_MAP_FILENAME)


def load_car_profile(car_id):
    """Load per-car ACC profile JSON by car_id (e.g. ferrari_296_gt3)."""
    safe_id = str(car_id).strip()
    if not safe_id or "/" in safe_id or ".." in safe_id:
        raise ValueError("invalid car_id: {0!r}".format(car_id))
    filename = safe_id + ".json"
    path = os.path.join(_CONFIG_DIR, CARS_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "no ACC car profile for {0!r} at {1}".format(car_id, path)
        )
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def check_stale(installed_version, kb_verified_on):
    """
    Return a warning string if installed ACC is older than KB verification, else None.
    """
    installed = _parse_version_tuple(installed_version)
    verified = _parse_version_tuple(kb_verified_on)
    if installed < verified:
        return (
            "Installed ACC {0} is behind KB verified_on {1}; "
            "some damper/tyre facts may not match your build.".format(
                installed_version, kb_verified_on
            )
        )
    return None


# Pre-1.9 / legacy pressure advice patterns (forum meta, old hot targets).
_PRE19_PRESSURE_HINTS = re.compile(
    r"(?:"
    r"pre[\s-]?1\.9|before\s+1\.9|legacy\s+pressure|old\s+meta|"
    r"27\.5\s*psi|28\s*psi|29\s*psi|"
    r"hot\s+pressure.{0,24}(?:27\.[89]|28\.|29\.)"
    r")",
    re.IGNORECASE,
)

_CURRENT_DRY_WINDOW = re.compile(
    r"26\s*[-–]\s*27|26\.0\s*[-–]\s*27\.0|26\s*to\s*27",
    re.IGNORECASE,
)


def reject_pre_19_advice(text):
    """
    Return True if free-text setup advice looks like pre-1.9 pressure dogma
    without citing the 1.9+ dry hot window (26–27 psi).
    """
    if not text or not str(text).strip():
        return False
    body = str(text)
    if not _PRE19_PRESSURE_HINTS.search(body):
        return False
    if _CURRENT_DRY_WINDOW.search(body):
        return False
    return True