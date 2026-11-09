#!/usr/bin/env python3
"""Build ac_app/config/cars/<car_id>.json from an Assetto Corsa car folder.

    python tools/extract_car_profile.py ks_ferrari_312_67
    python tools/extract_car_profile.py rss_formula_hybrid_x_2026 --keep-physics
"""

from __future__ import print_function

import argparse
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "ac_app", "lib"))

from acd_reader import read_car_data  # noqa: E402
from car_profile import build_car_profile  # noqa: E402

PHYSICS_KEYS = (
    "wheelbase_m", "cg_to_front_axle_m", "cg_to_rear_axle_m",
    "understeer_gradient_K", "max_yaw_rate_rad_s",
)


def default_ac_root():
    for path in (os.environ.get("AC_ROOT", ""),
                 "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa"):
        if path and os.path.isdir(path):
            return path
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("car_id")
    ap.add_argument("--ac-root", default=default_ac_root())
    ap.add_argument("--out", default="")
    ap.add_argument("--keep-physics", action="store_true",
                    help="Keep hand-tuned physics values from an existing profile")
    args = ap.parse_args()

    car_dir = os.path.join(args.ac_root, "content", "cars", args.car_id)
    files = read_car_data(car_dir)
    if "setup.ini" not in files:
        print("No setup.ini found for %s in %s" % (args.car_id, car_dir), file=sys.stderr)
        return 1

    profile = build_car_profile(args.car_id, files)
    out = args.out or os.path.join(REPO, "ac_app", "config", "cars", "%s.json" % args.car_id)
    if args.keep_physics and os.path.isfile(out):
        with open(out) as fh:
            old = json.load(fh)
        for key in PHYSICS_KEYS:
            if key in old:
                profile[key] = old[key]

    with open(out, "w") as fh:
        json.dump(profile, fh, indent=2)
        fh.write("\n")
    print("Wrote %s (%d levers)" % (out, len(profile["levers"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
