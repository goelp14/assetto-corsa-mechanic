"""Tool registry for evidence retrieval from replay bundles."""

from __future__ import print_function

import json
import os

from evidence_pack import build_evidence_pack, collect_evidence, load_lap_samples


class CoachTools(object):
    def __init__(self, bundle_dir):
        self.bundle_dir = bundle_dir
        self._evidence = None
        self._pack = None

    def _raw(self):
        if self._evidence is None:
            self._evidence = collect_evidence(self.bundle_dir)
        return self._evidence

    def get_corner_report(self, corner, lap=None):
        items = self._raw().get("corner_reports") or []
        out = [x for x in items if x.get("corner") == corner or x.get("corner_display") == corner]
        if lap is not None:
            out = [x for x in out if x.get("lap") == lap]
        return out

    def get_time_loss(self, corner=None, lap=None):
        tl = self._raw().get("time_loss") or {}
        corners = []
        for lap_key, lap_data in (tl.get("laps") or {}).items():
            if lap is not None and int(lap_key) != lap:
                continue
            for c in lap_data.get("corners", []):
                if corner and c.get("corner") != corner:
                    continue
                corners.append(c)
        return corners

    def get_incidents(self, corner=None, lap=None):
        items = self._raw().get("incidents") or []
        if corner:
            items = [x for x in items if x.get("corner") == corner]
        if lap is not None:
            items = [x for x in items if x.get("lap") == lap]
        return items

    def get_samples_window(self, spline, lap, radius=0.02):
        samples = load_lap_samples(self.bundle_dir, lap)
        return [s for s in samples if abs(float(s.get("spline", 0)) - spline) <= radius]

    def compare_to_reference(self, corner, phase="exit"):
        refs = self._raw().get("sector_bests") or {}
        ref = refs.get(corner, {})
        return ref.get("phases", {}).get(phase, ref)

    def get_session_plan(self):
        return self._raw().get("session_plan") or {}

    def get_track_landmarks(self, corner):
        pack = build_evidence_pack(self.bundle_dir, corner=corner)
        return pack.get("track_landmarks") or {}

    def build_pack(self, corner=None, spline=None, lap=None, question_type=None):
        self._pack = build_evidence_pack(
            self.bundle_dir, corner=corner, spline=spline, lap=lap, question_type=question_type,
        )
        return self._pack

    def run_tool(self, name, **kwargs):
        fn = getattr(self, name, None)
        if fn is None or name.startswith("_"):
            raise ValueError("Unknown tool: %s" % name)
        return fn(**kwargs)
