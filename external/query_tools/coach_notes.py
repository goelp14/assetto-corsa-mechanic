#!/usr/bin/env python3
"""Persist coach feedback as replay annotations (analysis/coach_notes.json)."""

from __future__ import print_function

import argparse
import json
import os
import re
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QT = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(REPO, "ac_app", "lib")
sys.path.insert(0, QT)
sys.path.insert(0, LIB)

from export_replay import attach_annotation_region, load_track_config, resolve_session_path  # noqa: E402
from spline_indexer import SplineIndexer  # noqa: E402

COACH_NOTES_REL = "analysis/coach_notes.json"
EXPORTS_ROOT = os.path.join(REPO, "exports")


def resolve_export_dir(bundle_arg, exports_root=None):
    """Resolve export bundle directory from name, session path, or export path."""
    exports_root = exports_root or EXPORTS_ROOT
    arg = (bundle_arg or "").strip().rstrip(os.sep)
    if not arg:
        raise ValueError("Missing session/export path")

    if os.path.isdir(arg) and os.path.isfile(os.path.join(arg, "manifest.json")):
        return os.path.abspath(arg)

    if os.path.isdir(arg) and os.path.isfile(os.path.join(arg, "session.jsonl")):
        session_id = os.path.basename(arg)
        export_dir = os.path.join(exports_root, session_id)
        if os.path.isfile(os.path.join(export_dir, "manifest.json")):
            return export_dir
        raise FileNotFoundError(
            "Session %s not exported yet. Run ./replay.sh or export_replay.py first." % session_id
        )

    session_id = os.path.basename(arg)
    export_dir = os.path.join(exports_root, session_id)
    if os.path.isfile(os.path.join(export_dir, "manifest.json")):
        return export_dir

    try:
        session_path = resolve_session_path(arg)
        session_id = os.path.basename(session_path)
        export_dir = os.path.join(exports_root, session_id)
        if os.path.isfile(os.path.join(export_dir, "manifest.json")):
            return export_dir
    except (ValueError, FileNotFoundError):
        pass

    raise FileNotFoundError("No export bundle for %r under %s" % (bundle_arg, exports_root))


def load_coach_notes(export_dir):
    path = os.path.join(export_dir, COACH_NOTES_REL)
    if not os.path.isfile(path):
        return {
            "version": 1,
            "session_id": os.path.basename(export_dir),
            "notes": [],
        }
    with open(path, "r") as fh:
        data = json.load(fh)
    if "notes" not in data:
        data["notes"] = []
    return data


def save_coach_notes(export_dir, data):
    analysis_dir = os.path.join(export_dir, "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    path = os.path.join(export_dir, COACH_NOTES_REL)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
    return path


def resolve_corner(spline_indexer, corner_query):
    if not corner_query:
        return None
    q = corner_query.strip().lower()
    for corner in spline_indexer.corners:
        name = (corner.get("name") or "").lower()
        display = (corner.get("display_name") or "").lower()
        if q == name or q == display or q in name or q in display:
            return corner
    return None


def _corner_mid_spline(spline_indexer, corner_name):
    cfg = spline_indexer.corner_config(corner_name)
    if not cfg:
        return 0.0
    return (float(cfg.get("spline_start", 0)) + float(cfg.get("spline_end", 0))) * 0.5


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:40]


def _make_id(lap, corner, existing_ids):
    base = "coach_L%d_%s" % (lap or 0, _slug(corner or "track"))
    note_id = base
    seq = 2
    while note_id in existing_ids:
        note_id = "%s_%d" % (base, seq)
        seq += 1
    return note_id


def track_id_from_manifest(export_dir):
    manifest_path = os.path.join(export_dir, "manifest.json")
    with open(manifest_path) as fh:
        manifest = json.load(fh)
    return manifest.get("track_id", "")


def build_coach_annotation(
    export_dir,
    lap=None,
    corner_query=None,
    spline=None,
    title="",
    what="",
    why="",
    action="",
    author="cursor",
    phase=None,
):
    track_id = track_id_from_manifest(export_dir)
    track_cfg = load_track_config(track_id)
    spline_indexer = SplineIndexer(track_cfg)

    corner_name = ""
    corner_display = ""
    sp = float(spline) if spline is not None else 0.0

    if corner_query:
        cfg = resolve_corner(spline_indexer, corner_query)
        if not cfg:
            raise ValueError("Unknown corner %r for track %s" % (corner_query, track_id))
        corner_name = cfg.get("name", "")
        corner_display = cfg.get("display_name") or corner_name
        if sp <= 0:
            sp = _corner_mid_spline(spline_indexer, corner_name)

    note = {
        "id": "",
        "lap": int(lap) if lap is not None else None,
        "spline": sp,
        "corner": corner_name or None,
        "corner_display": corner_display or None,
        "phase": phase,
        "category": "coach",
        "title": title or (what[:80] if what else "Coach note"),
        "what": what,
        "why": why,
        "action": action,
        "source": author,
        "author": author,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    attach_annotation_region(note, spline_indexer)
    return note


def add_note(export_dir, **kwargs):
    data = load_coach_notes(export_dir)
    existing_ids = {n.get("id") for n in data["notes"]}
    note = build_coach_annotation(export_dir, **kwargs)
    note["id"] = _make_id(note.get("lap"), note.get("corner"), existing_ids)
    data["notes"].append(note)
    path = save_coach_notes(export_dir, data)
    return note, path


def list_notes(export_dir, lap=None):
    data = load_coach_notes(export_dir)
    notes = data["notes"]
    if lap is not None:
        notes = [n for n in notes if n.get("lap") == lap]
    return notes


def remove_note(export_dir, note_id):
    data = load_coach_notes(export_dir)
    before = len(data["notes"])
    data["notes"] = [n for n in data["notes"] if n.get("id") != note_id]
    if len(data["notes"]) == before:
        raise ValueError("Note not found: %s" % note_id)
    save_coach_notes(export_dir, data)


def cmd_add(args):
    export_dir = resolve_export_dir(args.bundle)
    note, path = add_note(
        export_dir,
        lap=args.lap,
        corner_query=args.corner,
        spline=args.spline,
        title=args.title or "",
        what=args.what or "",
        why=args.why or "",
        action=args.action or "",
        author=args.author or "cursor",
        phase=args.phase,
    )
    print("Saved %s -> %s" % (note["id"], path))
    if note.get("corner_display"):
        print("  %s lap %s @ spline %.3f" % (note["corner_display"], note.get("lap"), note.get("spline")))
    return 0


def cmd_list(args):
    export_dir = resolve_export_dir(args.bundle)
    notes = list_notes(export_dir, lap=args.lap)
    if not notes:
        print("(no coach notes)")
        return 0
    for n in notes:
        loc = n.get("corner_display") or n.get("corner") or "track"
        print("%s  lap %-3s  %s  %s" % (n.get("id"), n.get("lap"), loc, n.get("title", "")))
    return 0


def cmd_remove(args):
    export_dir = resolve_export_dir(args.bundle)
    remove_note(export_dir, args.id)
    print("Removed %s" % args.id)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Persist coach feedback on replay bundles",
        epilog=(
            "Examples:\n"
            "  %(prog)s add -b exports/latest -l 17 -c \"Final Corner\" \\\n"
            "    -t \"Steer sawing\" --what \"...\" --why \"...\" --action \"...\"\n"
            "  %(prog)s list -b 2026-06-27_161650_968_monaco_2020"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="Add a coach note")
    p_add.add_argument("--bundle", "-b", required=True)
    p_add.add_argument("--lap", "-l", type=int)
    p_add.add_argument("--corner", "-c")
    p_add.add_argument("--spline", "-s", type=float)
    p_add.add_argument("--title", "-t")
    p_add.add_argument("--what")
    p_add.add_argument("--why")
    p_add.add_argument("--action")
    p_add.add_argument("--phase")
    p_add.add_argument("--author", default="cursor")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List coach notes")
    p_list.add_argument("--bundle", "-b", required=True)
    p_list.add_argument("--lap", "-l", type=int)
    p_list.set_defaults(func=cmd_list)

    p_rm = sub.add_parser("remove", help="Remove a coach note by id")
    p_rm.add_argument("--bundle", "-b", required=True)
    p_rm.add_argument("--id", required=True)
    p_rm.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main() or 0)
