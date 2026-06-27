# ac_app/lib/lap_time_analyzer.py
# Python 3.3 compatible — stdlib only

import math


class LapTimeAnalyzer(object):
    """Spatial delta per bucket, sector/corner deltas, theoretical best."""

    def __init__(self, num_buckets=360, track_length_m=5793.0, spline_indexer=None):
        self.num_buckets = num_buckets
        self.track_length_m = track_length_m
        self.spline_indexer = spline_indexer
        self.bucket_length_m = track_length_m / float(num_buckets)
        self._ref_speed = [0.0] * num_buckets
        self._curr_delta = [0.0] * num_buckets
        self._best_bucket_time = [None] * num_buckets
        self._lap_times_ms = []
        self._reference_lap_ms = None
        self._current_lap = 0
        self._lap_corner_deltas = {}
        self._lap_sector_deltas = {}
        self._lap_bucket_speed = [0.0] * num_buckets

    def set_reference_from_lap(self, bucket_speeds, lap_time_ms):
        self._ref_speed = list(bucket_speeds)
        self._reference_lap_ms = lap_time_ms

    def bucket_deltas(self):
        return list(self._curr_delta)

    def reset_lap(self, lap_number):
        self._current_lap = lap_number
        self._curr_delta = [0.0] * self.num_buckets
        self._lap_corner_deltas = {}
        self._lap_sector_deltas = {}
        self._lap_bucket_speed = [0.0] * self.num_buckets

    def observe(self, bucket, speed_kmh, dt):
        if bucket < 0 or bucket >= self.num_buckets:
            return
        if speed_kmh > self._lap_bucket_speed[bucket]:
            self._lap_bucket_speed[bucket] = speed_kmh
        speed_ms = max(speed_kmh / 3.6, 1.0)
        ref_kmh = self._ref_speed[bucket]
        ref_ms = ref_kmh / 3.6 if ref_kmh > 0 else speed_ms
        ref_ms = max(ref_ms, 1.0)
        dt_s = max(float(dt), 0.0)
        ds = min(speed_ms * dt_s, self.bucket_length_m)
        if ds <= 0.0:
            return
        delta_t = (1.0 / ref_ms - 1.0 / speed_ms) * ds
        self._curr_delta[bucket] += delta_t

        if self.spline_indexer is not None:
            corner = self.spline_indexer.corner_at_bin(bucket)
            if corner:
                self._lap_corner_deltas[corner] = (
                    self._lap_corner_deltas.get(corner, 0.0) + delta_t
                )
            sector = self.spline_indexer.sector_name(
                self.spline_indexer.spline_from_bin(bucket)
            )
            self._lap_sector_deltas[sector] = (
                self._lap_sector_deltas.get(sector, 0.0) + delta_t
            )

    def finish_lap(self, lap_time_ms, bucket_speeds, counted=True):
        if counted:
            self._lap_times_ms.append(lap_time_ms)
            for i in range(self.num_buckets):
                spd = bucket_speeds[i] if i < len(bucket_speeds) else 0.0
                if spd <= 0:
                    continue
                t_bin = self.bucket_length_m / (spd / 3.6)
                if self._best_bucket_time[i] is None or t_bin < self._best_bucket_time[i]:
                    self._best_bucket_time[i] = t_bin

            if self._reference_lap_ms is None or (
                lap_time_ms < self._reference_lap_ms and self._is_consistent_lap(lap_time_ms)
            ):
                self.set_reference_from_lap(bucket_speeds, lap_time_ms)

        return {
            "lap_time_ms": lap_time_ms,
            "corner_deltas": dict(self._lap_corner_deltas),
            "sector_deltas": dict(self._lap_sector_deltas),
            "total_delta_s": sum(self._curr_delta),
        }

    def _is_consistent_lap(self, lap_time_ms):
        if len(self._lap_times_ms) < 3:
            return True
        recent = self._lap_times_ms[-5:]
        mean = sum(recent) / float(len(recent))
        var = sum((t - mean) ** 2 for t in recent) / float(len(recent))
        sigma = math.sqrt(var)
        return sigma < 2000.0

    def theoretical_best_ms(self):
        total_s = 0.0
        for t in self._best_bucket_time:
            if t is not None:
                total_s += t
        return int(total_s * 1000.0)

    def consistency_sigma_ms(self):
        if len(self._lap_times_ms) < 2:
            return 0.0
        mean = sum(self._lap_times_ms) / float(len(self._lap_times_ms))
        var = sum((t - mean) ** 2 for t in self._lap_times_ms) / float(len(self._lap_times_ms))
        return math.sqrt(var)

    def corner_delta(self, corner):
        return self._lap_corner_deltas.get(corner, 0.0)

    def current_lap_delta_s(self):
        return sum(self._curr_delta)

    def reference_lap_ms(self):
        return self._reference_lap_ms

    def last_lap_ms(self):
        if not self._lap_times_ms:
            return None
        return self._lap_times_ms[-1]

    def potential_gap_s(self, lap_time_ms=None):
        ms = lap_time_ms if lap_time_ms is not None else self.last_lap_ms()
        pot = self.theoretical_best_ms()
        if not ms or not pot or pot <= 0:
            return 0.0
        return max(0.0, (ms - pot) / 1000.0)

    def worst_corners(self, min_delta_s=0.1, limit=5):
        items = [
            (name, delta)
            for name, delta in self._lap_corner_deltas.items()
            if delta >= min_delta_s
        ]
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:limit]
