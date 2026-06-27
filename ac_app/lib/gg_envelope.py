# ac_app/lib/gg_envelope.py
# Personal GG envelope — your peak lateral G vs speed (no alien refs).

import math


class GgEnvelope(object):
    """Track driver's own peak |ay| per speed bin from clean running."""

    def __init__(self, num_bins=12, bin_width_kmh=30.0):
        self.num_bins = num_bins
        self.bin_width_kmh = bin_width_kmh
        self._peak_ay = [0.0] * num_bins
        self._samples = [0] * num_bins

    def _bin(self, speed_kmh):
        idx = int(speed_kmh / self.bin_width_kmh)
        if idx < 0:
            idx = 0
        if idx >= self.num_bins:
            idx = self.num_bins - 1
        return idx

    def observe(self, speed_kmh, ay_g):
        if speed_kmh < 40.0:
            return
        idx = self._bin(speed_kmh)
        mag = abs(ay_g)
        self._samples[idx] += 1
        if mag > self._peak_ay[idx]:
            self._peak_ay[idx] = mag

    def peak_ay_at(self, speed_kmh):
        idx = self._bin(speed_kmh)
        return self._peak_ay[idx]

    def grip_usage(self, speed_kmh, ay_g):
        """0–1+ fraction of personal peak G used at this speed."""
        peak = self.peak_ay_at(speed_kmh)
        if peak < 0.25:
            return 1.0
        return min(1.5, abs(ay_g) / peak)

    def grip_left_pct(self, speed_kmh, ay_g):
        usage = self.grip_usage(speed_kmh, ay_g)
        if usage >= 0.92:
            return 0
        return int(round((0.92 - usage) * 100.0))

    def has_baseline(self):
        return any(p > 0.3 for p in self._peak_ay)

    def reset(self):
        self._peak_ay = [0.0] * self.num_bins
        self._samples = [0] * self.num_bins

    def to_dict(self):
        return {
            "peak_ay": [round(v, 3) for v in self._peak_ay],
            "samples": list(self._samples),
        }

    def load_dict(self, data):
        peaks = data.get("peak_ay", [])
        for i in range(min(len(peaks), self.num_bins)):
            self._peak_ay[i] = peaks[i]
