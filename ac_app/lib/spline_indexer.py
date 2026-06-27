# ac_app/lib/spline_indexer.py
# Python 3.3 compatible — stdlib only

import json
import os


DEFAULT_NUM_BUCKETS = 360


class SplineIndexer(object):
    """Map spline position to discrete bucket and corner name."""

    def __init__(self, track_config=None, num_buckets=DEFAULT_NUM_BUCKETS, spline_offset=0.0):
        self.num_buckets = num_buckets
        self.spline_offset = spline_offset
        self.corners = []
        self.sectors = []
        self.track_id = ""
        self.display_name = ""
        self.length_m = 0.0
        if track_config is not None:
            self.load_config(track_config)

    def load_config(self, track_config):
        if isinstance(track_config, dict):
            cfg = track_config
        else:
            with open(track_config, "r") as fh:
                cfg = json.load(fh)
        self.track_id = cfg.get("track_id", "")
        self.display_name = cfg.get("display_name", "")
        self.length_m = cfg.get("length_m", 0.0)
        self.spline_offset = cfg.get("spline_offset", 0.0)
        self.corners = cfg.get("corners", [])
        self.sectors = cfg.get("sectors", [])
        self.line_chains_meta = cfg.get("line_chains", [])

    @classmethod
    def from_track_file(cls, track_path, num_buckets=DEFAULT_NUM_BUCKETS):
        inst = cls(num_buckets=num_buckets)
        inst.load_config(track_path)
        return inst

    def _normalize_spline(self, spline):
        s = spline + self.spline_offset
        while s < 0.0:
            s += 1.0
        while s >= 1.0:
            s -= 1.0
        return s

    def bin(self, spline):
        s = self._normalize_spline(spline)
        idx = int(s * self.num_buckets)
        if idx >= self.num_buckets:
            idx = self.num_buckets - 1
        if idx < 0:
            idx = 0
        return idx

    def spline_from_bin(self, bucket):
        return (float(bucket) + 0.5) / float(self.num_buckets)

    def corner_name(self, spline):
        s = self._normalize_spline(spline)
        for corner in self.corners:
            start = corner.get("spline_start", 0.0)
            end = corner.get("spline_end", 0.0)
            if start <= end:
                if start <= s <= end:
                    return corner.get("name", "")
            else:
                if s >= start or s <= end:
                    return corner.get("name", "")
        return ""

    def corner_at_bin(self, bucket):
        return self.corner_name(self.spline_from_bin(bucket))

    def corner_config(self, corner_name):
        for corner in self.corners:
            if corner.get("name") == corner_name:
                return corner
        return None

    def corner_display_name(self, corner_name):
        corner = self.corner_config(corner_name)
        if corner is None:
            return corner_name
        return corner.get("display_name") or corner.get("name", corner_name)

    def corner_landmarks(self, corner_name):
        corner = self.corner_config(corner_name)
        if corner is None:
            return {}
        return dict(corner.get("landmarks", {}))

    def corner_speed_class(self, corner_name):
        corner = self.corner_config(corner_name)
        if corner is None:
            return "medium"
        return corner.get("speed_class", "medium")

    def corner_line(self, corner_name):
        corner = self.corner_config(corner_name)
        if corner is None:
            return {}
        line = corner.get("line", {})
        if line:
            return dict(line)
        landmarks = corner.get("landmarks", {})
        if landmarks.get("line_hint"):
            return {
                "profile": "geometric",
                "width_bias": "wide",
                "line_hint": landmarks.get("line_hint", ""),
            }
        return {}

    def line_chains(self):
        if self.line_chains_meta:
            return list(self.line_chains_meta)
        try:
            from line_defaults import LineDefaults
        except ImportError:
            from .line_defaults import LineDefaults
        return LineDefaults.infer_chains(self.corners)

    def next_corner_name(self, corner_name):
        if not self.corners:
            return ""
        ordered = sorted(self.corners, key=lambda c: c.get("spline_start", 0.0))
        names = [c.get("name", "") for c in ordered]
        if corner_name not in names:
            return ""
        idx = names.index(corner_name)
        if idx + 1 < len(names):
            return names[idx + 1]
        return ""

    def corner_line(self, corner_name, car_profile=None):
        corner = self.corner_config(corner_name)
        if corner and corner.get("line"):
            return dict(corner["line"])
        try:
            from line_defaults import LineDefaults
        except ImportError:
            from .line_defaults import LineDefaults
        speed = self.corner_speed_class(corner_name)
        nxt = self.next_corner_name(corner_name)
        return LineDefaults.infer(corner, speed, car_profile, nxt)

    def chain_role_for(self, corner_name, chain_id):
        for chain in self.line_chains():
            if chain.get("id") != chain_id:
                continue
            roles = chain.get("roles", {})
            if corner_name in roles:
                return roles[corner_name]
            corners = chain.get("corners", [])
            if corner_name in corners:
                idx = corners.index(corner_name)
                if idx == 0:
                    return "setup"
                if idx == len(corners) - 1:
                    return "payoff"
                return "link"
        return ""

    def sector_name(self, spline):
        s = self._normalize_spline(spline)
        name = "S1"
        for sector in self.sectors:
            end = sector.get("spline_end", 1.0)
            name = sector.get("name", name)
            if s <= end:
                return name
        return name

    def bucket_length_m(self):
        if self.length_m <= 0:
            return 0.0
        return self.length_m / float(self.num_buckets)

    def in_corner_range(self, spline, corner_name):
        corner = self.corner_config(corner_name)
        if corner is None:
            return False
        s = self._normalize_spline(spline)
        start = corner.get("spline_start", 0.0)
        end = corner.get("spline_end", 0.0)
        if start <= end:
            return start <= s <= end
        return s >= start or s <= end

    def upcoming_corner(self, spline, lookahead=0.06):
        """Next corner within lookahead fraction of lap distance ahead."""
        s = self._normalize_spline(spline)
        best = None
        best_dist = lookahead + 1.0
        for corner in self.corners:
            start = corner.get("spline_start", 0.0)
            dist = start - s
            if dist < 0.0:
                dist += 1.0
            if 0.0 < dist <= lookahead and dist < best_dist:
                best_dist = dist
                best = corner
        return best


def default_config_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
