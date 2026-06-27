import json
import os
import sys
import tempfile

qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
if qt not in sys.path:
    sys.path.insert(0, qt)

from coach_notes import (  # noqa: E402
    add_note,
    build_coach_annotation,
    list_notes,
    load_coach_notes,
    remove_note,
    resolve_corner,
    resolve_export_dir,
)
from spline_indexer import SplineIndexer  # noqa: E402
from export_replay import load_track_config  # noqa: E402


def _fake_export(tmp):
    export_dir = os.path.join(tmp, "test_monaco")
    os.makedirs(os.path.join(export_dir, "analysis"), exist_ok=True)
    with open(os.path.join(export_dir, "manifest.json"), "w") as fh:
        json.dump({"session_id": "test_monaco", "track_id": "monaco_2020"}, fh)
    return export_dir


def test_resolve_corner_by_display_name():
    cfg = load_track_config("monaco_2020")
    spline = SplineIndexer(cfg)
    corner = resolve_corner(spline, "Anthony Noghes")
    assert corner is not None
    assert corner.get("name") == "Final Corner"


def test_build_coach_annotation_has_region():
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = _fake_export(tmp)
        note = build_coach_annotation(
            export_dir,
            lap=17,
            corner_query="Final Corner",
            title="Steer sawing",
            what="Multiple steering corrections on exit.",
            why="Car unsettled after throttle application.",
            action="Hold one steering input through the exit curb.",
        )
        assert note["category"] == "coach"
        assert note["lap"] == 17
        assert note["corner"] == "Final Corner"
        assert note["corner_display"] == "Anthony Noghes"
        assert note["spline"] > 0
        assert note["spline_start"] is not None
        assert note["spline_end"] is not None


def test_add_list_remove_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = _fake_export(tmp)
        note, path = add_note(
            export_dir,
            lap=17,
            corner_query="Tabac",
            title="Brake release",
            what="Late trail-off.",
            action="Release 5m earlier.",
        )
        assert os.path.isfile(path)
        assert note["id"].startswith("coach_L17_")

        notes = list_notes(export_dir, lap=17)
        assert len(notes) == 1
        assert notes[0]["title"] == "Brake release"

        remove_note(export_dir, note["id"])
        assert list_notes(export_dir) == []


def test_resolve_export_dir_from_manifest_path():
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = _fake_export(tmp)
        resolved = resolve_export_dir(export_dir, exports_root=tmp)
        assert resolved == export_dir


def test_load_coach_notes_empty():
    with tempfile.TemporaryDirectory() as tmp:
        export_dir = _fake_export(tmp)
        data = load_coach_notes(export_dir)
        assert data["notes"] == []
