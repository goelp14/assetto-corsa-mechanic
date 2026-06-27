# ac_app/lib/line_reference.py
# Personal racing-line references per corner (no alien data).

import json
import os


class LineReference(object):
    """Best-known phase metrics for line quality at each corner."""

    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self.track_id = ""
        self.corners = {}

    def _path(self):
        if self.data_dir is None:
            base = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "data", "line_refs"
            )
        else:
            base = self.data_dir
        safe = self.track_id.replace(" ", "_").lower()
        return os.path.join(base, "%s.json" % safe)

    def load(self, track_id):
        self.track_id = track_id
        path = self._path()
        if not os.path.isfile(path):
            self.corners = {}
            return False
        with open(path, "r") as fh:
            data = json.load(fh)
        self.corners = data.get("corners", {})
        return True

    def save(self):
        if not self.track_id:
            return
        path = self._path()
        parent = os.path.dirname(path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w") as fh:
            json.dump({"track_id": self.track_id, "corners": self.corners}, fh, indent=2)
            fh.write("\n")

    def get(self, corner):
        return self.corners.get(corner, {})

    def update_corner(self, corner, summary, corner_delta_s):
        if not summary or not summary.get("phases"):
            return
        prev = self.corners.get(corner, {})
        prev_delta = prev.get("corner_delta_s", 999.0)
        if corner_delta_s >= prev_delta and prev.get("phases"):
            return
        record = {
            "corner_delta_s": corner_delta_s,
            "phases": summary["phases"],
        }
        self.corners[corner] = record
        self.save()
