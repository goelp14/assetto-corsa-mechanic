# ac_app/lib/feedback_manager.py
# Python 3.3 compatible — stdlib only

import heapq
import time

try:
    from feedback_presenter import FeedbackEvent
except ImportError:
    from .feedback_presenter import FeedbackEvent


class _QueueItem(object):
    __slots__ = ("neg_priority", "seq", "event")

    def __init__(self, neg_priority, seq, event):
        self.neg_priority = neg_priority
        self.seq = seq
        self.event = event

    def __lt__(self, other):
        if self.neg_priority != other.neg_priority:
            return self.neg_priority < other.neg_priority
        return self.seq < other.seq


class FeedbackManager(object):
    """Priority queue and ticker dispatch for feedback events."""

    TYPE_PRIORITY = {
        "revert": 5,
        "setup": 3,
        "coaching": 2,
        "analysis": 1,
        "learning": 1,
    }

    def __init__(self, voice_writer=None, ticker_duration_s=5.0):
        self.voice_writer = voice_writer
        self.ticker_duration_s = ticker_duration_s
        self._queue = []
        self._seq = 0
        self._active = None
        self._active_until = 0.0
        self._dispatched = []

    def enqueue(self, event):
        prio = event.priority
        if event.type in self.TYPE_PRIORITY:
            prio = max(prio, self.TYPE_PRIORITY[event.type])
        self._seq += 1
        heapq.heappush(
            self._queue,
            _QueueItem(-prio, self._seq, event),
        )

    def tick(self, delta_t, safe_for_audio=False, in_pit=False):
        now = time.time()
        dispatched = []

        if self._active is not None and now >= self._active_until:
            self._active = None

        can_dispatch = safe_for_audio or in_pit
        burst_limit = 3 if in_pit else 1

        while can_dispatch and self._queue and len(dispatched) < burst_limit:
            if self._active is not None and not in_pit:
                break
            item = heapq.heappop(self._queue)
            event = item.event
            self._active = event
            self._active_until = now + self.ticker_duration_s
            dispatched.append(event)
            self._dispatched.append(event)
            if self.voice_writer is not None and event.voice:
                self.voice_writer.append(event.voice)

        cue = ""
        cue_corner = ""
        headline_short = ""
        feedback_type = ""
        feedback_alpha = 0.0
        if self._active is not None:
            meta = self._active.metadata or {}
            remaining = self._active_until - now
            feedback_alpha = max(0.0, min(1.0, remaining / max(0.1, self.ticker_duration_s)))
            if not in_pit:
                cue = meta.get("cue", "")
                cue_corner = meta.get("corner_name") or self._active.corner or ""
                headline_short = self._short_headline(self._active.headline)
                feedback_type = self._active.type or ""

        return {
            "dispatched": dispatched,
            "ticker": self._active.headline if self._active and in_pit else "",
            "cue": cue if not in_pit else "",
            "cue_corner": cue_corner if not in_pit else "",
            "headline_short": headline_short if not in_pit else "",
            "feedback_type": feedback_type if not in_pit else "",
            "feedback_alpha": feedback_alpha if not in_pit else 0.0,
            "queue_size": len(self._queue),
        }

    @staticmethod
    def _short_headline(text, max_len=38):
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "\u2026"

    def current_ticker(self):
        if self._active is None:
            return ""
        return self._active.headline

    def clear(self):
        self._queue = []
        self._active = None

    def recent(self, limit=10):
        if limit <= 0:
            return []
        return self._dispatched[-limit:]
