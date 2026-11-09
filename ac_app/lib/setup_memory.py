# ac_app/lib/setup_memory.py
# Python 3.3 compatible — stdlib only

import json
import os
import time

STATUS_PENDING = "pending_evaluation"
STATUS_CONFIRMED = "confirmed"
STATUS_REVERTED = "reverted"
STATUS_INCONCLUSIVE = "inconclusive"


class SetupMemory(object):
    """Tweak lifecycle, effectiveness scoring, learned weights."""

    def __init__(self, data_dir=None, thresholds=None):
        self.data_dir = data_dir
        self.thresholds = thresholds or {}
        self.track_id = ""
        self.tweaks = []
        self.tweak_weights = {}
        self._pending = None
        self._last_write_lap = -999
        self._tweak_counter = 0

    def _thresh(self, key, default):
        return self.thresholds.get(key, default)

    def _path(self):
        if self.data_dir is None:
            base = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "setup_memory"
            )
        else:
            base = self.data_dir
        safe = self.track_id.replace(" ", "_").lower()
        return os.path.join(base, "%s.json" % safe)

    def load(self, track_id):
        self.track_id = track_id
        self.tweaks = []
        self.tweak_weights = {}
        self._tweak_counter = 0
        self._pending = None
        path = self._path()
        if not os.path.isfile(path):
            return False
        with open(path, "r") as fh:
            data = json.load(fh)
        self.tweaks = data.get("tweaks", [])
        self.tweak_weights = data.get("tweak_weights", {})
        self._tweak_counter = data.get("counter", len(self.tweaks))
        return True

    def save(self):
        if not self.track_id:
            return
        path = self._path()
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w") as fh:
            json.dump({
                "track_id": self.track_id,
                "counter": self._tweak_counter,
                "tweaks": self.tweaks,
                "tweak_weights": self.tweak_weights,
            }, fh, indent=2)
            fh.write("\n")

    def can_write(self, lap):
        cooldown = int(self._thresh("SETUP_WRITE_COOLDOWN_LAPS", 3))
        return lap - self._last_write_lap >= cooldown

    def record_pending(self, tweak_delta, lap, corner="", phase="", symptom="", before=None):
        self._tweak_counter += 1
        tweak_id = "%s_%03d" % (self.track_id.replace(" ", "_"), self._tweak_counter)
        record = {
            "tweak_id": tweak_id,
            "lap_applied": lap,
            "parameter": tweak_delta.section,
            "delta": tweak_delta.delta,
            "old_value": tweak_delta.old_value,
            "new_value": tweak_delta.new_value,
            "symptom": symptom,
            "corner": corner,
            "phase": phase,
            "before": before or {},
            "after": None,
            "effectiveness": None,
            "status": STATUS_PENDING,
            "timestamp": time.time(),
        }
        self.tweaks.append(record)
        self._pending = record
        self._last_write_lap = lap
        self.save()
        return tweak_id

    def _weight_key(self, parameter, direction):
        sign = 1 if direction >= 0 else -1
        return "%s:%d" % (parameter, sign)

    def approve_tweak(self, parameter, delta):
        key = self._weight_key(parameter, delta)
        weight = self.tweak_weights.get(key, 0.0)
        return weight >= -0.5

    def get_weight(self, parameter, delta):
        return self.tweak_weights.get(self._weight_key(parameter, delta), 0.0)

    def best_weight_for_symptom(self, symptom):
        """Highest learned weight among candidates for this symptom (if any)."""
        if not symptom or not self.tweak_weights:
            return 0.0
        best = 0.0
        for weight in self.tweak_weights.values():
            if weight > best:
                best = weight
        return best

    def rerank_candidates(self, candidates, symptom):
        def score(cand):
            key = self._weight_key(cand["section"], cand["delta"])
            return self.tweak_weights.get(key, 0.0)
        return sorted(candidates, key=score, reverse=True)

    def evaluate_pending(self, after_metrics):
        if self._pending is None:
            return None
        rec = self._pending
        before = rec.get("before", {})
        lap_delta = after_metrics.get("lap_time_ms", 0) - before.get("lap_time_ms", 0)
        corner_delta = (
            before.get("corner_delta", 0) - after_metrics.get("corner_delta", 0)
        )
        symptom_delta = (
            after_metrics.get("symptom_metric", 0) - before.get("symptom_metric", 0)
        )

        score = 0.0
        if lap_delta < -150:
            score += 0.4
        elif lap_delta > 100:
            score -= 0.5
        elif lap_delta > 50:
            score -= 0.3
        if corner_delta >= 0.05:
            score += 0.3
        elif corner_delta <= -0.05:
            score -= 0.3
        if symptom_delta > 0:
            score += 0.3
        elif symptom_delta < 0:
            score -= 0.3

        rec["after"] = after_metrics
        rec["effectiveness"] = score
        confirm = self._thresh("TWEAK_EFFECTIVENESS_CONFIRM", 0.3)
        revert = self._thresh("TWEAK_EFFECTIVENESS_REVERT", -0.3)

        if score >= confirm:
            rec["status"] = STATUS_CONFIRMED
            self._adjust_weight(rec["parameter"], rec["delta"], 0.1)
        elif score <= revert:
            rec["status"] = STATUS_REVERTED
            self._adjust_weight(rec["parameter"], rec["delta"], -0.2)
        else:
            rec["status"] = STATUS_INCONCLUSIVE

        self._pending = None
        self.save()
        return rec

    def _adjust_weight(self, parameter, delta, amount):
        key = self._weight_key(parameter, delta)
        self.tweak_weights[key] = self.tweak_weights.get(key, 0.0) + amount

    def recommend_direction(self, symptom):
        best = None
        best_score = -999.0
        for key, weight in self.tweak_weights.items():
            if weight > best_score:
                best_score = weight
                parts = key.split(":")
                if len(parts) == 2:
                    best = {"section": parts[0], "direction": int(parts[1])}
        return best
