# ac_app/lib/volatility_buffer.py
# Python 3.3 compatible — stdlib only

import math

PHASE_LEARNING = "LEARNING"
PHASE_BASELINE_READY = "BASELINE_READY"
PHASE_TWEAKING = "TWEAKING"


class WelfordState(object):
    __slots__ = ("n", "mean", "m2")

    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0

    def observe(self, value):
        self.n += 1
        delta = value - self.mean
        self.mean += delta / float(self.n)
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def variance(self):
        if self.n < 2:
            return 0.0
        return self.m2 / float(self.n - 1)

    def std(self):
        return math.sqrt(self.variance())


class BucketVolatility(object):
    __slots__ = ("speed", "steer", "brake_onset", "peak_steer", "lap_count")

    def __init__(self):
        self.speed = WelfordState()
        self.steer = WelfordState()
        self.brake_onset = None
        self.peak_steer = 0.0
        self.lap_count = 0


class VolatilityBuffer(object):
    """Per-bucket online variance for driver input consistency."""

    def __init__(self, num_buckets=360, thresholds=None):
        self.num_buckets = num_buckets
        self.thresholds = thresholds or {}
        self.phase = PHASE_LEARNING
        self.clean_laps = 0
        self.total_laps = 0
        self._last_lap_clean = False
        self._bins = [BucketVolatility() for _ in range(num_buckets)]
        self._lap_had_brake = [False] * num_buckets
        self._current_lap = 0

    def _thresh(self, key, default):
        return self.thresholds.get(key, default)

    def reset_lap(self, lap_number):
        self._current_lap = lap_number
        self._lap_had_brake = [False] * self.num_buckets
        for b in self._bins:
            b.speed = WelfordState()
            b.steer = WelfordState()
            b.brake_onset = None
            b.peak_steer = 0.0

    def observe(self, bucket, speed_kmh, steer_rad, brake, in_corner=False):
        if bucket < 0 or bucket >= self.num_buckets:
            return
        b = self._bins[bucket]
        b.speed.observe(speed_kmh)
        b.steer.observe(abs(steer_rad))
        if abs(steer_rad) > b.peak_steer:
            b.peak_steer = abs(steer_rad)
        brake_thresh = self._thresh("BRAKE_ONSET_THRESH", 0.1)
        if brake > brake_thresh and not self._lap_had_brake[bucket]:
            self._lap_had_brake[bucket] = True
            b.brake_onset = brake

    def finish_lap(self, clean_fraction=None):
        observed = 0
        consistent = 0
        speed_tol = self._thresh("VOLATILITY_SPEED_STD_KMH", 3.0)
        steer_tol = self._thresh("VOLATILITY_STEER_STD_RAD", 0.04)
        for b in self._bins:
            if b.speed.n < 3:
                continue
            observed += 1
            if b.speed.std() < speed_tol and b.steer.std() < steer_tol:
                consistent += 1
                b.lap_count += 1

        threshold = 0.70 if clean_fraction is None else float(clean_fraction)
        self.total_laps += 1
        if observed > 0 and float(consistent) / float(observed) > threshold:
            self.clean_laps += 1
            self._last_lap_clean = True
        else:
            self._last_lap_clean = False
            if self._thresh("LEARNING_CLEAN_STREAK", False):
                self.clean_laps = max(0, self.clean_laps - 1)

        self._update_phase()
        return self._last_lap_clean

    def _update_phase(self):
        learning_target = int(self._thresh("LEARNING_LAPS", 3))
        total_cap = int(self._thresh("BASELINE_AFTER_TOTAL_LAPS", 8))

        if self.clean_laps >= learning_target:
            if self.phase == PHASE_LEARNING:
                self.phase = PHASE_BASELINE_READY
            elif self.phase == PHASE_BASELINE_READY:
                self.phase = PHASE_TWEAKING
            return

        if self.total_laps >= total_cap and self.clean_laps >= 1:
            if self.phase == PHASE_LEARNING:
                self.phase = PHASE_BASELINE_READY
            elif self.phase == PHASE_BASELINE_READY:
                self.phase = PHASE_TWEAKING
            return

        if self.clean_laps < learning_target:
            self.phase = PHASE_LEARNING

    def coaching_allowed(self):
        if self.phase != PHASE_LEARNING:
            return True
        return self.total_laps >= int(self._thresh("EARLY_COACHING_AFTER_LAPS", 2))

    def bucket_stats(self, bucket):
        b = self._bins[bucket]
        return {
            "speed_mean": b.speed.mean,
            "speed_std": b.speed.std(),
            "steer_mean": b.steer.mean,
            "steer_std": b.steer.std(),
            "peak_steer": b.peak_steer,
            "lap_count": b.lap_count,
        }

    def is_consistent_bucket(self, bucket):
        stats = self.bucket_stats(bucket)
        speed_tol = self._thresh("VOLATILITY_SPEED_STD_KMH", 3.0)
        steer_tol = self._thresh("VOLATILITY_STEER_STD_RAD", 0.04)
        return stats["speed_std"] < speed_tol and stats["steer_std"] < steer_tol

    def variance_status(self):
        if self.phase == PHASE_LEARNING:
            return "HIGH"
        return "LOW"

    def learning_progress(self):
        target = int(self._thresh("LEARNING_LAPS", 3))
        return self.clean_laps, target

    def lap_consistency_pct(self):
        """Share of observed buckets with low speed/steer variance this stint."""
        observed = 0
        consistent = 0
        speed_tol = self._thresh("VOLATILITY_SPEED_STD_KMH", 3.0)
        steer_tol = self._thresh("VOLATILITY_STEER_STD_RAD", 0.04)
        for b in self._bins:
            if b.speed.n < 3:
                continue
            observed += 1
            if b.speed.std() < speed_tol and b.steer.std() < steer_tol:
                consistent += 1
        if observed == 0:
            return 0
        return int(round(100.0 * float(consistent) / float(observed)))
