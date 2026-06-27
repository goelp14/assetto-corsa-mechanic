"""CLI entry point for the telemetry coach agent."""

from __future__ import print_function

import argparse
import json
import os
import sys

COACH_DIR = os.path.dirname(os.path.abspath(__file__))
QT = os.path.dirname(COACH_DIR)
if QT not in sys.path:
    sys.path.insert(0, QT)
if COACH_DIR not in sys.path:
    sys.path.insert(0, COACH_DIR)

from coach_service import ask_coach  # noqa: E402
from evidence_pack import build_evidence_pack  # noqa: E402


def cmd_ask(args):
    result = ask_coach(
        args.bundle,
        args.question,
        corner=args.corner or None,
        spline=float(args.spline) if args.spline is not None else None,
        lap=int(args.lap) if args.lap is not None else None,
    )
    print(json.dumps(result, indent=2))
    return 0


def cmd_pack(args):
    pack = build_evidence_pack(
        args.bundle,
        corner=args.corner or None,
        spline=float(args.spline) if args.spline is not None else None,
        lap=int(args.lap) if args.lap is not None else None,
    )
    print(json.dumps(pack, indent=2, default=str))
    return 0


def main():
    parser = argparse.ArgumentParser(description="VRE telemetry coach agent")
    sub = parser.add_subparsers(dest="command")

    ask_p = sub.add_parser("ask", help="Ask a coaching question")
    ask_p.add_argument("--bundle", required=True, help="Exported replay bundle directory")
    ask_p.add_argument("--question", "-q", required=True, help="Coaching question")
    ask_p.add_argument("--corner", default="", help="Corner id filter")
    ask_p.add_argument("--lap", type=int, default=None, help="Lap number")
    ask_p.add_argument("--spline", type=float, default=None, help="Playhead spline")
    ask_p.set_defaults(func=cmd_ask)

    pack_p = sub.add_parser("pack", help="Dump evidence pack JSON")
    pack_p.add_argument("--bundle", required=True)
    pack_p.add_argument("--corner", default="")
    pack_p.add_argument("--lap", type=int, default=None)
    pack_p.add_argument("--spline", type=float, default=None)
    pack_p.set_defaults(func=cmd_pack)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
