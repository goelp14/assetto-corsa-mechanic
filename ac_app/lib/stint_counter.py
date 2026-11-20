# ac_app/lib/stint_counter.py
# Python 3.3 compatible — stdlib only

SETTLE = "settle"
COUNTED = "counted"
SLOW = "slow"


class StintCounter(object):
    """Lap count for one A-B setup run: settling laps, then counted laps up to a target, then box."""

    def __init__(self, settle_laps=2, target_laps=5, slow_pct=1.03):
        self.settle_laps = max(0, int(settle_laps))
        self.target_laps = max(1, int(target_laps))
        self.slow_pct = float(slow_pct)
        self.block = 0
        self.reset()

    def reset(self):
        self.block += 1
        self.settled = 0
        self.counted = 0
        self.last_role = ""

    @property
    def done(self):
        return self.counted >= self.target_laps

    def on_lap(self, lap_time_ms, best_ms):
        """Classify a completed flying lap. Returns (role, target_reached_on_this_lap)."""
        if self.settled < self.settle_laps:
            self.settled += 1
            self.last_role = SETTLE
            return SETTLE, False
        # Same rule as driver_lab compare --max-lap: spins and big offs are not counted.
        if best_ms > 0 and lap_time_ms > best_ms * self.slow_pct:
            self.last_role = SLOW
            return SLOW, False
        self.counted += 1
        self.last_role = COUNTED
        return COUNTED, self.counted == self.target_laps

    def hud_text(self):
        if self.settled < self.settle_laps:
            return "SETTLE LAP %d/%d" % (self.settled + 1, self.settle_laps)
        if self.done:
            return "BOX BOX - %d/%d DONE" % (self.counted, self.target_laps)
        text = "COUNTED %d/%d - %d TO GO" % (
            self.counted, self.target_laps, self.target_laps - self.counted)
        if self.last_role == SLOW:
            text += " (LAST SLOW)"
        return text
