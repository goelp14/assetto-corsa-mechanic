#!/usr/bin/env python3
"""Generate ac_app/config/tracks/<track>[-<layout>].json from the layout's AI line.

Corners are found where the AI slows down (speed minima), with direction from the
line's heading change. Names default to "Turn N"; pass --names to use real turn names.

    python tools/build_track_config.py rt_sonoma --layout long --dry-run
    python tools/build_track_config.py rt_sonoma --layout long \\
        --names "Turn 2,Turn 3,Turn 3a,Turn 4,Turn 6,Turn 7,Turn 8,Turn 8a,Turn 10,Turn 11"
"""

from __future__ import print_function

import argparse
import json
import math
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "ac_app", "lib"))

from fast_lane_parser import parse_fast_lane  # noqa: E402

DEFAULT_AC_ROOT = "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa"


def _wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def _smooth(values, half_window):
    n = len(values)
    out = []
    for i in range(n):
        acc = 0.0
        for k in range(-half_window, half_window + 1):
            acc += values[(i + k) % n]
        out.append(acc / (2 * half_window + 1))
    return out


def _heading_changes(centerline):
    n = len(centerline)
    headings = []
    for i in range(n):
        a = centerline[i - 1]
        b = centerline[(i + 1) % n]
        headings.append(math.atan2(b[1] - a[1], b[0] - a[0]))
    return [_wrap(headings[(i + 1) % n] - headings[i]) for i in range(n)]


def _index_at(distance, target):
    lo, hi = 0, len(distance) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if distance[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _turn_segments(curv, spacing, min_radius_m, merge_gap_m):
    """Runs of same-sign curvature tighter than min_radius_m, as (start, end, sign) index ranges."""
    n = len(curv)
    limit = 1.0 / min_radius_m
    sign = [0] * n
    for i in range(n):
        if curv[i] > limit:
            sign[i] = 1
        elif curv[i] < -limit:
            sign[i] = -1
    first = next((i for i in range(n) if sign[i] == 0), 0)
    segs = []
    i = 0
    while i < n:
        idx = (first + i) % n
        if sign[idx] == 0:
            i += 1
            continue
        s = sign[idx]
        j = i
        while j + 1 < n and sign[(first + j + 1) % n] == s:
            j += 1
        segs.append([first + i, first + j, s])
        i = j + 1
    gap = int(merge_gap_m / spacing)
    merged = []
    for seg in segs:
        if merged and merged[-1][2] == seg[2] and seg[0] - merged[-1][1] <= gap:
            merged[-1][1] = seg[1]
        else:
            merged.append(seg)
    return merged


def find_corners(fast_lane, min_radius_m=180.0, min_drop_kmh=8.0, tight_radius_m=90.0):
    dist = fast_lane["distance_m"]
    total = fast_lane["cumulative_length_m"]
    n = len(dist)
    spacing = total / float(n)
    speed = [v * 3.6 for v in _smooth(fast_lane["ai_speed"], max(1, int(10.0 / spacing)))]
    dh = _heading_changes(fast_lane["centerline"])
    right_sign = 1.0 if sum(dh) > 0 else -1.0
    curv = [c * right_sign / spacing for c in _smooth(dh, max(1, int(15.0 / spacing)))]
    elev = fast_lane["elevation_m"]
    segs = _turn_segments(curv, spacing, min_radius_m, merge_gap_m=25.0)

    corners = []
    prev_end = None
    for k, (s, e, sgn) in enumerate(segs):
        apex = min(range(s, e + 1), key=lambda i: speed[i % n])
        # A shallow kink braked through all the way is the next corner's braking zone.
        still_braking = apex >= e - 1 and speed[(e + 1) % n] < speed[e % n]
        shallow = abs(math.degrees(sum(dh[i % n] for i in range(s, e + 1)))) < 40.0
        if still_braking and shallow and k + 1 < len(segs) and segs[k + 1][0] - e <= int(40 / spacing):
            continue
        start = s
        floor = prev_end if prev_end is not None else s - int(400 / spacing)
        while start - 1 > floor and speed[(start - 1) % n] >= speed[start % n]:
            start -= 1
        next_start = segs[k + 1][0] if k + 1 < len(segs) else e + int(250 / spacing)
        end = e
        while end + 1 < next_start and speed[(end + 1) % n] < speed[apex % n] + 0.7 * (
                speed[(e + int(150 / spacing)) % n] - speed[apex % n]) and end - e < int(150 / spacing):
            end += 1
        min_radius = 1.0 / max(abs(curv[i % n]) for i in range(s, e + 1))
        entry_kmh = speed[start % n]
        if entry_kmh - speed[apex % n] < min_drop_kmh and min_radius > tight_radius_m:
            continue
        corners.append({
            "start": start % n, "apex": apex % n, "end": end % n,
            "entry_kmh": entry_kmh, "apex_kmh": speed[apex % n],
            "direction": "right" if sgn > 0 else "left",
            "turn_deg": abs(math.degrees(sum(dh[i % n] for i in range(s, e + 1)))),
            "min_radius_m": min_radius,
            "elev_change_m": elev[apex % n] - elev[start % n],
        })
        prev_end = end
    return corners, total


def _speed_class(kmh):
    if kmh < 100:
        return "slow"
    if kmh < 160:
        return "medium"
    return "fast"


def _approach_text(c):
    slope = c["elev_change_m"]
    if slope > 3:
        hill = "uphill"
    elif slope < -3:
        hill = "downhill"
    else:
        hill = "level"
    return "%s braking zone" % hill.capitalize()


def build_config(track, layout, fast_lane, names=None, display_names=None, ui=None):
    corners, total = find_corners(fast_lane)
    dist = fast_lane["distance_m"]
    names = names or []
    display_names = display_names or []
    out = []
    for i, c in enumerate(corners):
        name = names[i] if i < len(names) and names[i] else "Turn %d" % (i + 1)
        entry = {
            "name": name,
            "display_name": display_names[i] if i < len(display_names) and display_names[i] else name,
            "direction": c["direction"],
            "speed_class": _speed_class(c["apex_kmh"]),
            "spline_start": round(dist[c["start"]] / total, 3),
            "spline_end": round(dist[c["end"]] / total, 3),
            "apex_spline": round(dist[c["apex"]] / total, 3),
            "phases": {"entry_end_ay_pct": 0.5, "mid_end_throttle_pct": 0.5},
            "landmarks": {
                "approach": _approach_text(c),
                "apex_cue": "%s-hander, ~%d deg" % (
                    c["direction"].capitalize(), round(c["turn_deg"], -1),
                ),
            },
        }
        out.append(entry)
    out.sort(key=lambda e: e["spline_start"])
    ui = ui or {}
    return {
        "track_id": "%s-%s" % (track, layout) if layout else track,
        "display_name": ui.get("name") or track,
        "length_m": round(total),
        "spline_offset": 0.0,
        "setup_folder": track,
        "layout": layout,
        "direction": ui.get("run", ""),
        "generated_from": "fast_lane.ai",
        "sectors": [
            {"name": "S1", "spline_end": 0.33},
            {"name": "S2", "spline_end": 0.66},
            {"name": "S3", "spline_end": 1.0},
        ],
        "corners": out,
    }


def merge_existing(cfg, old):
    """Keep hand-authored data from a previous config: extra top-level keys,
    extra per-corner keys and landmark text, matched by corner name."""
    for key, value in old.items():
        cfg.setdefault(key, value)
    old_corners = {c.get("name"): c for c in old.get("corners", [])}
    for corner in cfg["corners"]:
        prev = old_corners.get(corner["name"])
        if not prev:
            continue
        for key, value in prev.items():
            if key == "landmarks":
                corner["landmarks"].update(value)
            else:
                corner.setdefault(key, value)
    return cfg


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("track", help="AC track folder, e.g. rt_sonoma")
    ap.add_argument("--layout", default="", help="Layout folder, e.g. long")
    ap.add_argument("--names", default="", help="Comma-separated corner names in driving order")
    ap.add_argument("--display-names", default="", help="Comma-separated display names")
    ap.add_argument("--ac-root", default=os.environ.get("AC_ROOT", DEFAULT_AC_ROOT))
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true", help="Print detected corners only")
    args = ap.parse_args()

    base = os.path.join(args.ac_root, "content", "tracks", args.track)
    ai = os.path.join(base, args.layout, "ai", "fast_lane.ai")
    ui_path = os.path.join(base, "ui", args.layout, "ui_track.json")
    if not os.path.isfile(ai):
        print("fast_lane.ai not found: %s" % ai, file=sys.stderr)
        return 1
    ui = {}
    if os.path.isfile(ui_path):
        with open(ui_path, "rb") as fh:
            ui = json.loads(fh.read().decode("utf-8", "replace"))

    cfg = build_config(
        args.track, args.layout, parse_fast_lane(ai),
        names=[s.strip() for s in args.names.split(",")] if args.names else None,
        display_names=[s.strip() for s in args.display_names.split(",")] if args.display_names else None,
        ui=ui,
    )
    if args.dry_run:
        for c in cfg["corners"]:
            print("%-10s %-5s %-6s %.3f-%.3f apex %.3f  %s | %s" % (
                c["name"], c["direction"], c["speed_class"], c["spline_start"], c["spline_end"],
                c["apex_spline"], c["landmarks"]["approach"], c["landmarks"]["apex_cue"],
            ))
        return 0
    out = args.out or os.path.join(REPO, "ac_app", "config", "tracks", cfg["track_id"] + ".json")
    if os.path.isfile(out):
        with open(out) as fh:
            cfg = merge_existing(cfg, json.load(fh))
    with open(out, "w") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")
    print("Wrote %s (%d corners)" % (out, len(cfg["corners"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
