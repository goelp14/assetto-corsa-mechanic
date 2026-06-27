# ac_app/lib/session_phase_store.py
# Python 3.3 compatible — stdlib only

import json
import os

try:
    from volatility_buffer import (
        PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING,
    )
except ImportError:
    from .volatility_buffer import (
        PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING,
    )

VALID_PHASES = (PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING)


class SessionPhaseStore(object):
    """Persist learning phase across AC reloads."""

    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "session_phase",
            )
        self.data_dir = data_dir

    def _path(self, track_id):
        safe = track_id.replace(" ", "_").lower()
        return os.path.join(self.data_dir, "%s.json" % safe)

    def load(self, track_id, baseline_sample_total=0):
        path = self._path(track_id)
        phase = PHASE_LEARNING
        clean_laps = 0
        total_laps = 0
        if os.path.isfile(path):
            try:
                with open(path, "r") as fh:
                    data = json.load(fh)
                phase = data.get("phase", PHASE_LEARNING)
                clean_laps = int(data.get("clean_laps", 0))
                total_laps = int(data.get("total_laps", 0))
            except (IOError, ValueError):
                pass
        if phase == PHASE_LEARNING and baseline_sample_total >= 500:
            phase = PHASE_TWEAKING
            clean_laps = max(clean_laps, 3)
            total_laps = max(total_laps, 8)
        if phase not in VALID_PHASES:
            phase = PHASE_LEARNING
        return {
            "phase": phase,
            "clean_laps": clean_laps,
            "total_laps": total_laps,
        }

    def save(self, track_id, phase, clean_laps, total_laps):
        if not track_id or phase not in VALID_PHASES:
            return
        parent = self.data_dir
        if not os.path.isdir(parent):
            os.makedirs(parent)
        path = self._path(track_id)
        with open(path, "w") as fh:
            json.dump({
                "track_id": track_id,
                "phase": phase,
                "clean_laps": int(clean_laps),
                "total_laps": int(total_laps),
            }, fh, indent=2)
            fh.write("\n")
