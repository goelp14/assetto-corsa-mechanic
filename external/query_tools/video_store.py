"""Keep replay footage small: delete recordings that are superseded or no longer used by the bundle.

Only videos listed in a bundle's ``videos.json`` and recorded by this tool (``"tool": "vre"``) are ever
deleted. A recording is dropped when
  - a newer recording exists for the same driver / lap / kind / corner / camera, or
  - its lap is no longer that driver's fastest lap in the bundle (an improved lap was found), or
  - it came from a replay the bundle no longer uses (``rpy_file`` changed, e.g. reference replaced), or
  - its driver is gone from the bundle.
"""

from __future__ import annotations

import json
import os
from typing import List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXPORTS = os.path.join(ROOT, "exports")


def _keep_reason(v: dict, drivers: dict) -> str:
    d = drivers.get(v.get("driver"))
    if d is None:
        return "driver not in bundle"
    if v.get("rpy_file") and d.get("rpy_file") and v["rpy_file"] != d["rpy_file"]:
        return "replay replaced"
    laps = {l.get("lap_index") for l in v.get("laps", []) if l.get("lap_index") is not None and l.get("complete", True)}
    if v.get("kind") == "angle":
        laps = {l.get("lap_index") for l in v.get("laps", []) if l.get("lap_index") is not None}
    if d.get("best_lap_index") not in laps:
        return "not the fastest lap any more"
    return ""


def prune(bundle: str, dry_run: bool = False, exports: str = None, keep_corners=None) -> dict:
    """``keep_corners``: when given, angle clips of any other corner/segment are dropped (plan changed)."""
    bdir = os.path.join(exports or EXPORTS, bundle)
    vpath = os.path.join(bdir, "videos.json")
    try:
        with open(vpath, encoding="utf-8") as fh:
            doc = json.load(fh)
        with open(os.path.join(bdir, "manifest.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        return {"removed": [], "freed_bytes": 0}
    drivers = {d["label"]: d for d in manifest.get("drivers", [])}
    keep: List[dict] = []
    removed: List[dict] = []
    seen = set()
    for v in sorted(doc.get("videos", []), key=lambda x: x.get("recorded", ""), reverse=True):
        if v.get("tool") != "vre":
            keep.append(v)          # not ours (or recorded before tagging): never delete
            continue
        why = _keep_reason(v, drivers)
        key = (v.get("driver"), v.get("kind", "full"), v.get("corner"), v.get("camera"),
               tuple(sorted(l.get("lap_index") or -1 for l in v.get("laps", []))))
        if not why and keep_corners is not None and v.get("kind") == "angle" and v.get("corner") not in keep_corners:
            why = "no longer in the capture plan"
        if not why and key in seen:
            why = "superseded by a newer recording"
        if why:
            removed.append(dict(v, reason=why))
        else:
            seen.add(key)
            keep.append(v)
    freed = 0
    if not dry_run:
        for v in removed:
            for p in (v.get("file"), os.path.join(bdir, "video_%s_samples.json" % v.get("id"))):
                if p and os.path.isfile(p):
                    freed += os.path.getsize(p)
                    os.remove(p)
        doc["videos"] = sorted(keep, key=lambda x: x.get("recorded", ""))
        with open(vpath, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
    else:
        freed = sum(os.path.getsize(v["file"]) for v in removed if v.get("file") and os.path.isfile(v["file"]))
    return {"removed": [{"id": v["id"], "reason": v["reason"], "label": v.get("pass_label") or v.get("camera")}
                        for v in removed], "freed_bytes": freed}


if __name__ == "__main__":
    import sys

    print(json.dumps(prune(sys.argv[1], dry_run="--dry-run" in sys.argv), indent=1))
