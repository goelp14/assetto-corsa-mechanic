# ac_app/lib/baseline_store.py
# Python 3.3 compatible — stdlib only

import json
import os
import threading


class BaselineBucket(object):
    __slots__ = ("mean_brake", "mean_speed", "mean_steer", "sample_count", "peak_speed")

    def __init__(self):
        self.mean_brake = 0.0
        self.mean_speed = 0.0
        self.mean_steer = 0.0
        self.sample_count = 0
        self.peak_speed = 0.0

    def observe(self, brake, speed_kmh, steer):
        n = self.sample_count
        self.sample_count = n + 1
        self.mean_brake += (brake - self.mean_brake) / float(self.sample_count)
        self.mean_speed += (speed_kmh - self.mean_speed) / float(self.sample_count)
        self.mean_steer += (steer - self.mean_steer) / float(self.sample_count)
        if speed_kmh > self.peak_speed:
            self.peak_speed = speed_kmh

    def to_dict(self):
        return {
            "mean_brake": self.mean_brake,
            "mean_speed": self.mean_speed,
            "mean_steer": self.mean_steer,
            "sample_count": self.sample_count,
            "peak_speed": self.peak_speed,
        }

    @classmethod
    def from_dict(cls, data):
        b = cls()
        b.mean_brake = data.get("mean_brake", 0.0)
        b.mean_speed = data.get("mean_speed", 0.0)
        b.mean_steer = data.get("mean_steer", 0.0)
        b.sample_count = data.get("sample_count", 0)
        b.peak_speed = data.get("peak_speed", b.mean_speed)
        return b


class BaselineStore(object):
    """Per-bucket mean driver inputs; JSON persistence."""

    def __init__(self, num_buckets=360, data_dir=None):
        self.num_buckets = num_buckets
        self.data_dir = data_dir
        self.track_id = ""
        self._baselines = [BaselineBucket() for _ in range(num_buckets)]

    def observe(self, bucket, brake, speed_kmh, steer):
        if 0 <= bucket < self.num_buckets:
            self._baselines[bucket].observe(brake, speed_kmh, steer)

    def get(self, bucket):
        if 0 <= bucket < self.num_buckets:
            return self._baselines[bucket]
        return None

    def input_deviation(self, bucket, brake, speed_kmh, steer):
        b = self.get(bucket)
        if b is None or b.sample_count < 3:
            return None
        return {
            "brake": abs(brake - b.mean_brake),
            "speed": abs(speed_kmh - b.mean_speed),
            "steer": abs(steer - b.mean_steer),
        }

    def _path_for_track(self, track_id):
        if self.data_dir is None:
            base = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "baselines"
            )
        else:
            base = self.data_dir
        safe = track_id.replace(" ", "_").lower()
        return os.path.join(base, "%s.json" % safe)

    def _payload_for_track(self, track_id):
        return {
            "track_id": track_id,
            "num_buckets": self.num_buckets,
            "buckets": [b.to_dict() for b in self._baselines],
        }

    def _write_payload(self, path, payload):
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w") as fh:
            json.dump(payload, fh, separators=(",", ":"))
            fh.write("\n")

    def save(self, track_id=None, async_write=False):
        tid = track_id or self.track_id
        if not tid:
            return
        path = self._path_for_track(tid)
        payload = self._payload_for_track(tid)
        if async_write:
            thread = threading.Thread(
                target=self._write_payload,
                args=(path, payload),
            )
            thread.daemon = True
            thread.start()
        else:
            self._write_payload(path, payload)

    def load(self, track_id):
        self.track_id = track_id
        self._baselines = [BaselineBucket() for _ in range(self.num_buckets)]
        path = self._path_for_track(track_id)
        if not os.path.isfile(path):
            return False
        with open(path, "r") as fh:
            payload = json.load(fh)
        buckets = payload.get("buckets", [])
        for i, data in enumerate(buckets):
            if i < self.num_buckets:
                self._baselines[i] = BaselineBucket.from_dict(data)
        return True

    def sample_total(self):
        total = 0
        for b in self._baselines:
            total += b.sample_count
        return total
