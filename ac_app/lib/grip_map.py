# ac_app/lib/grip_map.py
# Personal grip map — self-referenced only, built from your telemetry.

import json
import os

NUM_BUCKETS = 360
GRIP_SEGMENTS = 36

ISSUE_KERB = "kerb"
ISSUE_BUMP = "bump"
ISSUE_SLIP = "slip"
ISSUE_PATCHY = "patchy"
ISSUE_SOLID = "solid"

ZONE_SOLID = "solid"
ZONE_OK = "ok"
ZONE_PATCHY = "patchy"
ZONE_TRAP = "trap"
ZONE_LEARNING = "learning"


class _BucketLapStats(object):
    __slots__ = (
        "n", "peak_ay", "ay_eff_sum", "max_slip", "min_load",
        "kerb_hits", "bump_hits", "load_drops",
    )

    def __init__(self):
        self.n = 0
        self.peak_ay = 0.0
        self.ay_eff_sum = 0.0
        self.max_slip = 0.0
        self.min_load = 999999.0
        self.kerb_hits = 0
        self.bump_hits = 0
        self.load_drops = 0


class _BucketRef(object):
    __slots__ = (
        "rating", "issue", "samples", "cost_delta_s",
        "best_ay_eff", "best_low_slip", "zone",
    )

    def __init__(self):
        self.rating = 0
        self.issue = ISSUE_SOLID
        self.samples = 0
        self.cost_delta_s = 0.0
        self.best_ay_eff = 0.0
        self.best_low_slip = 1.0
        self.zone = ZONE_LEARNING

    def to_dict(self):
        return {
            "rating": self.rating,
            "issue": self.issue,
            "samples": self.samples,
            "cost_delta_s": round(self.cost_delta_s, 4),
            "zone": self.zone,
        }

    @classmethod
    def from_dict(cls, data):
        ref = cls()
        ref.rating = int(data.get("rating", 0))
        ref.issue = data.get("issue", ISSUE_SOLID)
        ref.samples = int(data.get("samples", 0))
        ref.cost_delta_s = float(data.get("cost_delta_s", 0.0))
        ref.zone = data.get("zone", ZONE_LEARNING)
        ref.best_ay_eff = float(data.get("best_ay_eff", 0.0))
        ref.best_low_slip = float(data.get("best_low_slip", 1.0))
        return ref


class GripMapStore(object):
    """Spatial grip quality from your own laps — no reference laps."""

    def __init__(self, num_buckets=NUM_BUCKETS, data_dir=None, thresholds=None):
        self.num_buckets = num_buckets
        self.data_dir = data_dir
        self.thresholds = thresholds or {}
        self.track_id = ""
        self._map = [_BucketRef() for _ in range(num_buckets)]
        self._lap = [_BucketLapStats() for _ in range(num_buckets)]
        self._prev_load = None

    def _t(self, key, default):
        return float(self.thresholds.get(key, default))

    def _path(self):
        base = self.data_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "grip_map",
        )
        safe = self.track_id.replace(" ", "_").lower()
        return os.path.join(base, "%s.json" % safe)

    def load(self, track_id):
        self.track_id = track_id or ""
        self.reset_lap()
        path = self._path()
        if not track_id or not os.path.isfile(path):
            return False
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
            buckets = data.get("buckets", [])
            for i in range(min(len(buckets), self.num_buckets)):
                self._map[i] = _BucketRef.from_dict(buckets[i])
            return True
        except (IOError, ValueError):
            return False

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
                "buckets": [b.to_dict() for b in self._map],
            }, fh, indent=2)
            fh.write("\n")

    def reset_lap(self):
        self._lap = [_BucketLapStats() for _ in range(self.num_buckets)]
        self._prev_load = None

    def observe(self, bucket, frame, balance=None):
        if bucket < 0 or bucket >= self.num_buckets:
            return
        st = self._lap[bucket]
        st.n += 1
        ay = abs(frame.acc_g[1]) if frame.acc_g else 0.0
        if ay > st.peak_ay:
            st.peak_ay = ay
        if balance is not None and balance.valid:
            st.ay_eff_sum += balance.ay_efficiency
        slips = getattr(frame, "slip_ratio", getattr(frame, "slip", ())) or ()
        if slips:
            sm = max(slips)
            if sm > st.max_slip:
                st.max_slip = sm
        loads = getattr(frame, "wheel_load", None) or ()
        load_sum = sum(loads) if loads else 0.0
        if load_sum > 0 and load_sum < st.min_load:
            st.min_load = load_sum
        ratios = getattr(frame, "susp_ratio", None) or ()
        if ratios and max(ratios) >= self._t("KERB_SUSP_PCT", 0.85):
            st.kerb_hits += 1
        vert = abs(frame.acc_g[2]) if frame.acc_g and len(frame.acc_g) > 2 else 0.0
        if vert >= self._t("BUMP_VERT_G", 1.0):
            st.bump_hits += 1
        if self._prev_load is not None and load_sum > 100.0:
            drop = (self._prev_load - load_sum) / self._prev_load
            if drop >= self._t("SURFACE_LOAD_DROP_PCT", 0.12):
                st.load_drops += 1
        if load_sum > 0:
            self._prev_load = load_sum

    def finish_lap(self, bucket_deltas=None, lap_was_clean=True):
        if not lap_was_clean:
            self.reset_lap()
            return
        min_samples = int(self._t("GRIP_MAP_MIN_SAMPLES", 3))
        for i in range(self.num_buckets):
            st = self._lap[i]
            if st.n < min_samples:
                continue
            ref = self._map[i]
            ay_eff = st.ay_eff_sum / float(st.n) if st.n else 0.0
            cost = 0.0
            if bucket_deltas and i < len(bucket_deltas):
                cost = max(0.0, bucket_deltas[i])

            issue = self._classify_issue(st, ay_eff)
            rating = self._score_bucket(st, ay_eff, ref, cost)
            zone = zone_from_rating(rating, ref.samples)

            ref.rating = rating
            ref.issue = issue
            ref.zone = zone
            ref.samples += 1
            if cost > 0:
                ref.cost_delta_s = ref.cost_delta_s * 0.7 + cost * 0.3
            if ay_eff > ref.best_ay_eff:
                ref.best_ay_eff = ay_eff
            if st.max_slip < ref.best_low_slip:
                ref.best_low_slip = st.max_slip

        self.save()
        self.reset_lap()

    def _classify_issue(self, st, ay_eff):
        if st.kerb_hits >= 1 or st.load_drops >= 1:
            return ISSUE_KERB
        if st.bump_hits >= 2:
            return ISSUE_BUMP
        if st.max_slip > self._t("SURFACE_SLIP_SPIKE", 0.08):
            return ISSUE_SLIP
        if ay_eff < self._t("AY_EFFICIENCY_MIN", 0.92):
            return ISSUE_PATCHY
        return ISSUE_SOLID

    def _score_bucket(self, st, ay_eff, ref, cost):
        score = 88.0
        if st.kerb_hits >= 1:
            score -= 22.0
        if st.load_drops >= 1:
            score -= 12.0
        if st.bump_hits >= 1:
            score -= 10.0
        if st.max_slip > self._t("SURFACE_SLIP_SPIKE", 0.08):
            score -= 15.0
        if ref.best_ay_eff > 0.5 and ay_eff < ref.best_ay_eff * 0.88:
            score -= 12.0
        if cost >= self._t("CORNER_DELTA_SETUP_S", 0.03):
            score -= min(25.0, cost * 200.0)
        if ref.samples > 0:
            score = score * 0.65 + ref.rating * 0.35
        return int(max(5, min(100, round(score))))

    def segment_ratings(self, segments=GRIP_SEGMENTS):
        span = self.num_buckets // segments
        if span < 1:
            span = 1
        out = []
        for seg in range(segments):
            start = seg * span
            end = min(self.num_buckets, start + span)
            ratings = []
            issues = {}
            cost = 0.0
            samples = 0
            for i in range(start, end):
                ref = self._map[i]
                if ref.samples <= 0:
                    continue
                ratings.append(ref.rating)
                issues[ref.issue] = issues.get(ref.issue, 0) + 1
                cost = max(cost, ref.cost_delta_s)
                samples += ref.samples
            if ratings:
                avg = sum(ratings) / float(len(ratings))
                primary = max(issues.items(), key=lambda x: x[1])[0]
            else:
                avg = 0.0
                primary = ISSUE_SOLID
            out.append({
                "segment": seg,
                "spline": (seg + 0.5) / float(segments),
                "rating": int(round(avg)),
                "issue": primary,
                "zone": zone_from_rating(int(round(avg)), samples),
                "cost_delta_s": cost,
                "learned": samples > 0,
            })
        return out

    def at_bucket(self, bucket):
        if 0 <= bucket < self.num_buckets:
            return self._map[bucket]
        return _BucketRef()

    def at_spline(self, spline):
        bucket = int(spline * self.num_buckets)
        if bucket >= self.num_buckets:
            bucket = self.num_buckets - 1
        return self.at_bucket(bucket)

    def current_hint(self, spline, corner_display=""):
        ref = self.at_spline(spline)
        if ref.samples < 1:
            return ""
        return format_live_hint(ref, corner_display)

    def hotspots(self, limit=3, spline_indexer=None):
        items = []
        for i, ref in enumerate(self._map):
            if ref.samples < 1 or ref.zone not in (ZONE_PATCHY, ZONE_TRAP):
                continue
            if ref.cost_delta_s < self._t("GRIP_HOTSPOT_MIN_COST_S", 0.01) and ref.rating > 40:
                continue
            spline = (i + 0.5) / float(self.num_buckets)
            corner = ""
            if spline_indexer is not None:
                corner = spline_indexer.corner_display_name(
                    spline_indexer.corner_name(spline),
                )
            items.append({
                "bucket": i,
                "spline": spline,
                "corner": corner,
                "rating": ref.rating,
                "issue": ref.issue,
                "zone": ref.zone,
                "cost_delta_s": ref.cost_delta_s,
                "action": action_for_issue(ref.issue),
                "label": label_for_issue(ref.issue),
            })
        items.sort(key=lambda x: (-x["cost_delta_s"], x["rating"]))
        return items[:limit]

    def pit_summary(self, spline_indexer=None):
        spots = self.hotspots(limit=3, spline_indexer=spline_indexer)
        if not spots:
            learned = sum(1 for b in self._map if b.samples > 0)
            if learned < 20:
                return "Grip map learning — a few more clean laps to paint the track."
            return "Grip map: no major traps in your data — keep pushing your reference."
        lines = ["Your grip traps (from your laps only):"]
        for i, spot in enumerate(spots, 1):
            where = spot["corner"] or ("%.0f%% lap" % (spot["spline"] * 100.0))
            lines.append(
                "%d) %s — %s (%s)" % (
                    i, where, spot["label"], spot["action"],
                ),
            )
        return " | ".join(lines)

    def has_data(self):
        return any(b.samples > 0 for b in self._map)


def zone_from_rating(rating, samples=1):
    if samples < 1:
        return ZONE_LEARNING
    if rating >= 80:
        return ZONE_SOLID
    if rating >= 55:
        return ZONE_OK
    if rating >= 35:
        return ZONE_PATCHY
    return ZONE_TRAP


def zone_color(zone):
    if zone == ZONE_SOLID:
        return (0.15, 0.82, 0.38, 0.92)
    if zone == ZONE_OK:
        return (0.85, 0.72, 0.12, 0.88)
    if zone == ZONE_PATCHY:
        return (1.0, 0.48, 0.18, 0.92)
    if zone == ZONE_TRAP:
        return (0.95, 0.22, 0.22, 0.95)
    return (0.22, 0.22, 0.28, 0.55)


def label_for_issue(issue):
    return {
        ISSUE_KERB: "Kerb grip loss",
        ISSUE_BUMP: "Bump unsettled",
        ISSUE_SLIP: "Traction limit",
        ISSUE_PATCHY: "Line-sensitive",
        ISSUE_SOLID: "Solid grip",
    }.get(issue, "Patchy")


def action_for_issue(issue):
    return {
        ISSUE_KERB: "ease steering on kerb",
        ISSUE_BUMP: "soften inputs over bump",
        ISSUE_SLIP: "smoother throttle/brake",
        ISSUE_PATCHY: "match your reference line",
        ISSUE_SOLID: "push — grip available",
    }.get(issue, "match your reference line")


def format_live_hint(ref, corner_display=""):
    if ref.zone == ZONE_LEARNING:
        return ""
    if ref.zone in (ZONE_SOLID, ZONE_OK):
        return ""
    where = corner_display or "here"
    return "Grip %s @ %s — %s" % (
        ref.zone.upper(), where, action_for_issue(ref.issue),
    )


def format_grip_legend():
    return "Grip strip: green=solid · yellow=ok · orange=patchy · red=trap (your data)"
