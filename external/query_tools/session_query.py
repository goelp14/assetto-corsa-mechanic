#!/usr/bin/env python3
"""Query Virtual Race Engineer session archives for AI-friendly summaries."""

from __future__ import print_function

import argparse
import json
import os
import sys


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def find_latest_session(sessions_dir):
    if not os.path.isdir(sessions_dir):
        return None
    dirs = [
        os.path.join(sessions_dir, d)
        for d in os.listdir(sessions_dir)
        if os.path.isdir(os.path.join(sessions_dir, d))
    ]
    if not dirs:
        return None
    return max(dirs, key=os.path.getmtime)


def summarize_session(session_dir):
    jsonl = os.path.join(session_dir, "session.jsonl")
    if not os.path.isfile(jsonl):
        print("No session.jsonl in %s" % session_dir)
        return 1

    records = load_jsonl(jsonl)
    laps = [r for r in records if r.get("record_type") == "lap_summary"]
    corners = [r for r in records if r.get("record_type") == "corner_event"]
    setups = [r for r in records if r.get("record_type") == "setup_change"]

    print("# VRE Session Summary")
    print("Path: %s" % session_dir)
    print("Laps recorded: %d" % len(laps))
    if laps:
        best = min(laps, key=lambda r: r.get("lap_time_ms", 999999999))
        print("Best lap: %d ms (lap %s)" % (
            best.get("lap_time_ms", 0), best.get("lap", "?"),
        ))
        for lap in laps[-5:]:
            style = lap.get("driving_style", {})
            print("- Lap %s: %d ms | aggression %.2f | consistency %.2f" % (
                lap.get("lap"), lap.get("lap_time_ms", 0),
                style.get("aggression", 0), style.get("consistency", 0),
            ))
            cd = lap.get("corner_deltas_s", {})
            if cd:
                worst = max(cd.items(), key=lambda kv: kv[1])
                print("  Worst corner: %s (+%.3fs)" % (worst[0], worst[1]))

    if corners:
        print("\n## Recent corner verdicts")
        for c in corners[-10:]:
            print("- %s %s %s: %s (in %.2f out %.2f)" % (
                c.get("corner"), c.get("phase"), c.get("lap"),
                c.get("verdict"), c.get("input_score", 0), c.get("output_score", 0),
            ))

    if setups:
        print("\n## Setup changes")
        for s in setups:
            print("- %s: %s %s -> %s (%s)" % (
                s.get("tweak_id"), s.get("parameter"),
                s.get("old_value"), s.get("new_value"), s.get("reason"),
            ))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Query VRE session logs")
    parser.add_argument(
        "--sessions-dir",
        default=os.path.join(
            os.path.dirname(__file__), "..", "..", "ac_app", "data", "sessions",
        ),
    )
    parser.add_argument("--session", help="Specific session folder name")
    args = parser.parse_args()

    sessions_dir = os.path.abspath(args.sessions_dir)
    if args.session:
        session_dir = os.path.join(sessions_dir, args.session)
    else:
        session_dir = find_latest_session(sessions_dir)

    if not session_dir or not os.path.isdir(session_dir):
        print("No sessions found in %s" % sessions_dir, file=sys.stderr)
        return 1
    return summarize_session(session_dir)


if __name__ == "__main__":
    sys.exit(main())
