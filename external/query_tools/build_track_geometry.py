#!/usr/bin/env python3
"""Build track_geometry.json from AC fast_lane.ai + VRE track config."""

from __future__ import print_function

import argparse
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIB = os.path.join(REPO, "ac_app", "lib")
CFG = os.path.join(REPO, "ac_app", "config")
sys.path.insert(0, LIB)

from fast_lane_parser import parse_fast_lane
from track_geometry import build_track_geometry, load_track_config, write_track_geometry


def default_ac_root():
    candidates = [
        os.environ.get("AC_ROOT", ""),
        "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa",
    ]
    for path in candidates:
        if path and os.path.isdir(path):
            return path
    return ""


def resolve_fast_lane(ac_root, track_config):
    folder = track_config.get("setup_folder", track_config.get("track_id", ""))
    layout = track_config.get("layout", "")
    path = os.path.join(ac_root, "content", "tracks", folder, layout, "ai", "fast_lane.ai")
    if os.path.isfile(path):
        return path
    raise FileNotFoundError("fast_lane.ai not found at %s" % path)


def main():
    parser = argparse.ArgumentParser(description="Build VRE track geometry from AC AI line")
    parser.add_argument("--track", default="monaco_2020", help="VRE track_id")
    parser.add_argument("--ac-root", default=default_ac_root(), help="Assetto Corsa install root")
    parser.add_argument(
        "--output",
        default="",
        help="Output path (default: ac_app/data/track_geometry/{track}.json)",
    )
    args = parser.parse_args()

    if not args.ac_root:
        print("Set --ac-root or AC_ROOT env to your Assetto Corsa folder", file=sys.stderr)
        return 1

    track_config = load_track_config(CFG, args.track)
    ai_path = resolve_fast_lane(args.ac_root, track_config)
    print("Parsing %s" % ai_path)
    fast_lane = parse_fast_lane(ai_path)

    geometry = build_track_geometry(fast_lane, track_config, source_path=ai_path)
    out = args.output or os.path.join(
        REPO, "ac_app", "data", "track_geometry", "%s.json" % args.track,
    )
    write_track_geometry(out, geometry)
    print("Wrote %s (%d centerline points, %d corners)" % (
        out, len(geometry["centerline"]), len(geometry["corners"]),
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
