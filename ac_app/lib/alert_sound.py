# ac_app/lib/alert_sound.py
# Python 3.3 compatible — stdlib only


def play_alert():
    """Windows exclamation sound. MessageBeep is asynchronous, so the game thread never waits on it."""
    try:
        import ctypes
        return bool(ctypes.windll.user32.MessageBeep(0x30))
    except Exception:
        return False


class AlertRepeater(object):
    """Plays the alert a few times, spaced out, from the per-frame update."""

    def __init__(self, gap_s=0.7, play=play_alert):
        self.gap_s = float(gap_s)
        self.play = play
        self.remaining = 0
        self.wait = 0.0

    def trigger(self, count=3):
        self.remaining = int(count)
        self.wait = 0.0

    def tick(self, delta_t):
        if self.remaining <= 0:
            return
        self.wait -= delta_t
        if self.wait <= 0.0:
            self.play()
            self.remaining -= 1
            self.wait = self.gap_s
