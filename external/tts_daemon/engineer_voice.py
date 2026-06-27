#!/usr/bin/env python3
"""Monitor engineer_voice.txt and speak new lines via pyttsx3."""

from __future__ import print_function

import argparse
import os
import re
import sys
import time

try:
    import pyttsx3
except ImportError:
    print("Install pyttsx3: pip install pyttsx3", file=sys.stderr)
    sys.exit(1)


LINE_RE = re.compile(r"^(\d+)\|([^|]+)\|(.+)$")


def read_pending(path):
    if not os.path.isfile(path):
        return [], []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = [ln.rstrip("\n") for ln in fh.readlines()]
    pending = []
    kept = []
    for line in lines:
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if m:
            pending.append((int(m.group(1)), m.group(3)))
        else:
            pending.append((0, line))
    return pending, lines


def rewrite_without_spoken(path, spoken_seqs, all_lines):
    if not all_lines:
        return
    kept = []
    for line in all_lines:
        m = LINE_RE.match(line)
        if m and int(m.group(1)) in spoken_seqs:
            continue
        kept.append(line)
    with open(path, "w", encoding="utf-8") as fh:
        for line in kept:
            fh.write(line + "\n")


def main():
    parser = argparse.ArgumentParser(description="VRE voice daemon")
    parser.add_argument(
        "--voice-file",
        default=os.path.expanduser(
            "~/Documents/Assetto Corsa/apps/python/VirtualRaceEngineer/data/engineer_voice.txt"
        ),
        help="Path to engineer_voice.txt",
    )
    parser.add_argument("--poll-ms", type=int, default=200)
    args = parser.parse_args()

    engine = pyttsx3.init()
    last_spoken = set()

    print("Watching %s" % args.voice_file)
    while True:
        pending, raw = read_pending(args.voice_file)
        spoken_now = set()
        for seq, message in pending:
            if seq in last_spoken:
                continue
            print("Speaking: %s" % message)
            engine.say(message)
            engine.runAndWait()
            last_spoken.add(seq)
            spoken_now.add(seq)
        if spoken_now:
            rewrite_without_spoken(args.voice_file, spoken_now, raw)
        time.sleep(args.poll_ms / 1000.0)


if __name__ == "__main__":
    main()
