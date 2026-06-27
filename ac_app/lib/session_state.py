# ac_app/lib/session_state.py
# Python 3.3 compatible — stdlib only

try:
    from volatility_buffer import PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING
except ImportError:
    from .volatility_buffer import PHASE_LEARNING, PHASE_BASELINE_READY, PHASE_TWEAKING

LAP_FLYING = "flying"
LAP_OUT = "out_lap"
LAP_IN = "in_lap"


class CornerExitEvent(object):
    __slots__ = ("lap", "corner", "phase", "bucket", "spline", "timestamp")

    def __init__(self, lap, corner, phase, bucket, spline, timestamp):
        self.lap = lap
        self.corner = corner
        self.phase = phase
        self.bucket = bucket
        self.spline = spline
        self.timestamp = timestamp


class SessionState(object):
    """Lap boundaries, phase tracking, pit/out/in lap classification."""

    def __init__(self):
        self.phase = PHASE_LEARNING
        self.current_lap = 0
        self.last_completed_lap = -1
        self.lap_start_t = 0.0
        self.in_pit = False
        self.was_in_pit = None
        self.pit_entry_lap = None
        self.pit_exit_lap = None
        self._prev_corner = ""
        self._corner_events = []
        self._lap_complete_callbacks = []
        self._pit_entry_callbacks = []
        self._pit_exit_callbacks = []
        self._corner_exit_callbacks = []
        self._lap_started_in_pit = False
        self._pit_entry_this_lap = False
        self._pit_exit_this_lap = False
        self._ended_in_pit = False

    def on_lap_complete(self, callback):
        self._lap_complete_callbacks.append(callback)

    def on_pit_entry(self, callback):
        self._pit_entry_callbacks.append(callback)

    def on_pit_exit(self, callback):
        self._pit_exit_callbacks.append(callback)

    def on_corner_exit(self, callback):
        self._corner_exit_callbacks.append(callback)

    def set_phase(self, phase):
        self.phase = phase

    @staticmethod
    def classify_lap(started_in_pit, pit_entry, pit_exit, ended_in_pit):
        if pit_entry or ended_in_pit:
            return LAP_IN
        if started_in_pit or pit_exit:
            return LAP_OUT
        return LAP_FLYING

    def _reset_lap_pit_flags(self, in_pit):
        self._lap_started_in_pit = in_pit
        self._pit_entry_this_lap = False
        self._pit_exit_this_lap = False
        self._ended_in_pit = False

    def update(self, frame, spline_indexer, corner_phase=None):
        events = []
        lap_changed = False
        pit_entry = False
        pit_exit = False
        completed_lap_type = LAP_FLYING

        if frame.lap != self.current_lap:
            if self.current_lap >= 0 and frame.lap > self.last_completed_lap:
                lap_changed = True
                completed_lap_type = self.classify_lap(
                    self._lap_started_in_pit,
                    self._pit_entry_this_lap,
                    self._pit_exit_this_lap,
                    self._ended_in_pit,
                )
                self.last_completed_lap = self.current_lap
                for cb in self._lap_complete_callbacks:
                    cb(self.last_completed_lap, frame, completed_lap_type)
            self.current_lap = frame.lap
            self.lap_start_t = frame.t
            self._prev_corner = ""
            self._reset_lap_pit_flags(frame.in_pit)

        if self.was_in_pit is None:
            self.was_in_pit = frame.in_pit
            self.in_pit = frame.in_pit
            self._lap_started_in_pit = frame.in_pit
            self.current_lap = frame.lap
            self.lap_start_t = frame.t
        elif frame.in_pit and not self.was_in_pit:
            pit_entry = True
            self.pit_entry_lap = frame.lap
            if not self._lap_started_in_pit:
                self._pit_entry_this_lap = True
            for cb in self._pit_entry_callbacks:
                cb(frame.lap, frame)
        elif not frame.in_pit and self.was_in_pit:
            pit_exit = True
            self.pit_exit_lap = frame.lap
            self._pit_exit_this_lap = True
            for cb in self._pit_exit_callbacks:
                cb(frame.lap, frame)

        self._ended_in_pit = frame.in_pit
        self.was_in_pit = frame.in_pit
        self.in_pit = frame.in_pit

        corner = spline_indexer.corner_name(frame.spline)
        phase = "straight"
        if corner_phase is not None:
            phase = corner_phase.current_phase(corner, frame)

        if self._prev_corner and not corner:
            bucket = spline_indexer.bin(frame.spline)
            evt = CornerExitEvent(
                frame.lap, self._prev_corner, phase, bucket, frame.spline, frame.t
            )
            self._corner_events.append(evt)
            events.append(evt)
            for cb in self._corner_exit_callbacks:
                cb(evt, frame)
            self._prev_corner = ""
        elif corner:
            self._prev_corner = corner

        return {
            "lap_changed": lap_changed,
            "lap_type": completed_lap_type if lap_changed else None,
            "pit_entry": pit_entry,
            "pit_exit": pit_exit,
            "corner_exit_events": events,
        }

    def recent_corner_events(self, limit=20):
        if limit <= 0:
            return []
        return self._corner_events[-limit:]

    def clear_corner_events(self):
        self._corner_events = []
