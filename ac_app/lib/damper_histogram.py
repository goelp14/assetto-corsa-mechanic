# ac_app/lib/damper_histogram.py
# Python 3.3 compatible — per-frame damper velocity histograms and wheel-unload timing.
#
# The archived lap samples are decimated to ~12 Hz, far too slow for damper velocity, so this
# accumulates at the app's frame rate and stores only the histograms in the lap file.

BIN_MM_S = 10.0
LIMIT_MM_S = 300.0
NBINS = int(2 * LIMIT_MM_S / BIN_MM_S)
PHASES = ("entry", "mid", "exit", "straight")
UNLOAD_N = 150.0
MAX_DT_S = 0.05


def _bin(v_mm_s):
    i = int((v_mm_s + LIMIT_MM_S) // BIN_MM_S)
    return 0 if i < 0 else (NBINS - 1 if i >= NBINS else i)


def bin_centre(i):
    return -LIMIT_MM_S + (i + 0.5) * BIN_MM_S


class DamperHistogram(object):
    """Suspension travel is compression-positive, so velocity > 0 is bump and < 0 is rebound."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._prev = None
        self.frames = 0
        self.time_s = 0.0
        self.hist = dict((p, [[0] * NBINS for _ in range(4)]) for p in PHASES)
        self.peak_mm_s = [0.0, 0.0, 0.0, 0.0]
        self.unload_s = {}

    def observe(self, frame, dt, corner="", phase=""):
        travel = getattr(frame, "susp_travel", None)
        if not travel or not any(travel) or getattr(frame, "in_pit", False) or frame.speed_kmh < 20.0:
            self._prev = None
            return
        prev, self._prev = self._prev, tuple(travel)
        if prev is None or dt <= 0.0 or dt > MAX_DT_S:
            return
        self.frames += 1
        self.time_s += dt
        rows = self.hist[phase if phase in self.hist else "straight"]
        for w in range(4):
            v = (travel[w] - prev[w]) * 1000.0 / dt
            rows[w][_bin(v)] += 1
            if abs(v) > abs(self.peak_mm_s[w]):
                self.peak_mm_s[w] = v
        loads = getattr(frame, "wheel_load", ())
        if corner and loads and any(loads):
            acc = self.unload_s.setdefault(corner, [0.0, 0.0, 0.0, 0.0])
            for w in range(4):
                if loads[w] < UNLOAD_N:
                    acc[w] += dt

    def to_dict(self):
        if not self.frames:
            return {}
        return {
            "bin_mm_s": BIN_MM_S, "limit_mm_s": LIMIT_MM_S,
            "frames": self.frames, "rate_hz": round(self.frames / self.time_s, 1) if self.time_s else 0.0,
            "hist": self.hist,
            "peak_mm_s": [round(v, 0) for v in self.peak_mm_s],
            "unload_s": dict((k, [round(x, 3) for x in v]) for k, v in self.unload_s.items()),
        }


def merge(dicts):
    """Sum several lap 'dampers' dicts into one histogram set."""
    out = None
    for d in dicts:
        if not d or "hist" not in d:
            continue
        if out is None:
            out = {"hist": dict((p, [[0] * NBINS for _ in range(4)]) for p in PHASES), "frames": 0, "unload_s": {}}
        out["frames"] += d.get("frames", 0)
        for p, rows in d["hist"].items():
            dst = out["hist"].setdefault(p, [[0] * NBINS for _ in range(4)])
            for w in range(4):
                for i, n in enumerate(rows[w]):
                    dst[w][i] += n
        for k, v in d.get("unload_s", {}).items():
            acc = out["unload_s"].setdefault(k, [0.0, 0.0, 0.0, 0.0])
            for w in range(4):
                acc[w] += v[w]
    return out or {}


def wheel_stats(counts, knee_bump=25.0, knee_rebound=25.0):
    """Shape of one wheel's histogram: bump/rebound balance, slow/fast split, spread, peakiness."""
    n = float(sum(counts))
    if not n:
        return {}
    vals = [(bin_centre(i), c) for i, c in enumerate(counts) if c]
    mean = sum(v * c for v, c in vals) / n
    var = sum((v - mean) ** 2 * c for v, c in vals) / n
    sd = var ** 0.5
    kurt = (sum((v - mean) ** 4 * c for v, c in vals) / n) / (var * var) if var else 0.0
    cum, median = 0.0, 0.0
    for v, c in vals:
        cum += c
        if cum >= n / 2.0:
            median = v
            break
    bump = sum(c for v, c in vals if v > 0) / n
    return {
        "n": int(n), "mean": round(mean, 1), "median": round(median, 1), "sd": round(sd, 1),
        "kurtosis": round(kurt, 2),
        "bump_pct": round(100.0 * bump, 1), "rebound_pct": round(100.0 * (1.0 - bump), 1),
        "slow_bump_pct": round(100.0 * sum(c for v, c in vals if 0 < v <= knee_bump) / n, 1),
        "fast_bump_pct": round(100.0 * sum(c for v, c in vals if v > knee_bump) / n, 1),
        "slow_rebound_pct": round(100.0 * sum(c for v, c in vals if -knee_rebound <= v <= 0) / n, 1),
        "fast_rebound_pct": round(100.0 * sum(c for v, c in vals if v < -knee_rebound) / n, 1),
        "within_10_pct": round(100.0 * sum(c for v, c in vals if abs(v) <= 10.0) / n, 1),
    }
