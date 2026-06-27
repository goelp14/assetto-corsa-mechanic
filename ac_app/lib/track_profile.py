# ac_app/lib/track_profile.py
# Python 3.3 compatible — stdlib only

import json
import os


class TrackProfile(object):
    """Per-track characteristics and bootstrap setup hints."""

    def __init__(self, profile_id, data):
        self.profile_id = profile_id
        self.data = data
        self.character = data.get("character", {})
        self.learning = data.get("learning", {})
        self.bootstrap_hints = data.get("bootstrap_hints", [])
        self.traits_summary = data.get("traits_summary", "")
        self.display_name = data.get("display_name", profile_id)
        self._bootstrap_index = 0
        self.bootstrap_active = False

    def clean_fraction(self, default=0.70):
        return float(self.learning.get("clean_fraction", default))

    def bootstrap_after_laps(self, default=3):
        return int(self.learning.get("bootstrap_after_laps", default))

    def should_bootstrap(self, total_laps, clean_laps):
        if self._bootstrap_index >= len(self.bootstrap_hints):
            return False
        return total_laps >= self.bootstrap_after_laps()

    def next_bootstrap_hint(self):
        if self._bootstrap_index >= len(self.bootstrap_hints):
            return None
        hint = self.bootstrap_hints[self._bootstrap_index]
        self._bootstrap_index += 1
        self.bootstrap_active = True
        return hint

    def allows_setup_during_learning(self):
        return self.bootstrap_active or self._bootstrap_index > 0

    def reset_bootstrap(self):
        self._bootstrap_index = 0
        self.bootstrap_active = False


class TrackProfileStore(object):
    def __init__(self, path=None):
        self.path = path or self.default_path()
        self._profiles = {}
        self._alias_map = {}
        self._default_id = "balanced"
        self._load()

    @classmethod
    def default_path(cls):
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "config", "track_profiles.json",
        )

    def _load(self):
        with open(self.path, "r") as fh:
            payload = json.load(fh)
        self._default_id = payload.get("default_profile", "balanced")
        for pid, data in payload.get("profiles", {}).items():
            self._profiles[pid] = data
            self._alias_map[pid.lower()] = pid
            for alias in data.get("aliases", []):
                self._alias_map[alias.lower()] = pid

    def resolve(self, track_name):
        key = (track_name or "").replace(" ", "_").lower()
        pid = self._alias_map.get(key, self._default_id)
        if pid not in self._profiles:
            pid = self._default_id
        return TrackProfile(pid, self._profiles.get(pid, {}))
