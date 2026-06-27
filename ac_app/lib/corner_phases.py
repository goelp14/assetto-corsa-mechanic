# ac_app/lib/corner_phases.py
# Python 3.3 compatible — stdlib only

PHASE_ENTRY = "entry"
PHASE_MID = "mid"
PHASE_EXIT = "exit"
PHASE_STRAIGHT = "straight"


class CornerPhaseTracker(object):
    """Per-corner entry / mid / exit phase detection."""

    def __init__(self, spline_indexer=None):
        self.spline_indexer = spline_indexer
        self._corner_state = {}

    def _get_state(self, corner):
        if corner not in self._corner_state:
            self._corner_state[corner] = {
                "phase": PHASE_ENTRY,
                "peak_ay": 0.0,
                "active": False,
            }
        return self._corner_state[corner]

    def _corner_phases_cfg(self, corner):
        if self.spline_indexer is None:
            return {"entry_end_ay_pct": 0.5, "mid_end_throttle_pct": 0.5}
        cfg = self.spline_indexer.corner_config(corner)
        if cfg is None:
            return {"entry_end_ay_pct": 0.5, "mid_end_throttle_pct": 0.5}
        return cfg.get("phases", {"entry_end_ay_pct": 0.5, "mid_end_throttle_pct": 0.5})

    def update(self, corner, frame):
        if not corner:
            return PHASE_STRAIGHT
        st = self._get_state(corner)
        st["active"] = True
        ay = abs(frame.acc_g[1])
        if ay > st["peak_ay"]:
            st["peak_ay"] = ay

        phases = self._corner_phases_cfg(corner)
        entry_end_pct = phases.get("entry_end_ay_pct", 0.5)
        mid_end_pct = phases.get("mid_end_throttle_pct", 0.5)

        if st["phase"] == PHASE_ENTRY:
            if st["peak_ay"] > 0.1 and ay >= st["peak_ay"] * entry_end_pct:
                st["phase"] = PHASE_MID
        elif st["phase"] == PHASE_MID:
            if frame.throttle >= mid_end_pct or ay < st["peak_ay"] * 0.4:
                st["phase"] = PHASE_EXIT
        return st["phase"]

    def current_phase(self, corner, frame):
        if not corner:
            return PHASE_STRAIGHT
        if frame.brake > 0.1:
            st = self._get_state(corner)
            if st["phase"] == PHASE_STRAIGHT or not st["active"]:
                st["phase"] = PHASE_ENTRY
                st["peak_ay"] = abs(frame.acc_g[1])
                st["active"] = True
        return self.update(corner, frame)

    def reset_corner(self, corner):
        if corner in self._corner_state:
            del self._corner_state[corner]

    def reset_lap(self):
        self._corner_state = {}

    def on_corner_exit(self, corner):
        self.reset_corner(corner)


# Alias used by orchestrator / plan naming
CornerPhaseSegmenter = CornerPhaseTracker
