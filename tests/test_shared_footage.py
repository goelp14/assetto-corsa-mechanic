"""Reference footage reused across bundles: coverage matching, adoption, and pruning that never deletes shared files."""

import json

from external.query_tools import acc_capture_session as cs
from external.query_tools.video_store import prune


def test_longer_clip_covers_shorter_pass_same_camera_only():
    have = [("angle", "Drivable/Chase", 210.0, 1364.0), ("full", "Drivable/Dash", None, None)]
    assert cs._has(have, {"kind": "angle", "camera": "Drivable/Chase", "s0_m": 210.0, "s1_m": 544.0})
    assert not cs._has(have, {"kind": "angle", "camera": "Helicam/Helicam", "s0_m": 210.0, "s1_m": 544.0})
    assert not cs._has(have, {"kind": "angle", "camera": "Drivable/Chase", "s0_m": 2836.0, "s1_m": 3216.0})
    assert cs._has(have, {"kind": "full", "camera": "Drivable/Dash"})
    # TV clips are matched as one camera family whatever TV set ACC picked
    assert cs._has([("angle", "set1", 0.0, 900.0)], {"kind": "angle", "camera": "set1/CameraTV7a", "s0_m": 10, "s1_m": 500})


def _bundle(root, name, drivers, videos):
    b = root / name
    b.mkdir(parents=True)
    (b / "manifest.json").write_text(json.dumps({"drivers": drivers}))
    (b / "videos.json").write_text(json.dumps({"videos": videos}))
    return b


def test_adopt_reference_clips_and_prune_keeps_shared_file(tmp_path):
    clip = tmp_path / "erik_chase.mp4"
    clip.write_bytes(b"x" * 10)
    erik = {"label": "Erik", "rpy_file": "ERIK.rpy", "best_lap_index": 4}
    v = {"id": "v1", "driver": "Erik", "tool": "vre", "rpy_file": "ERIK.rpy", "kind": "angle", "corner": "La Source → Eau Rouge",
         "camera": "Drivable/Chase", "file": str(clip), "s0_m": 210.0, "s1_m": 1364.0, "recorded": "2026-11-23",
         "laps": [{"lap_index": 4}]}
    old = _bundle(tmp_path, "old", [erik], [v])
    (old / "video_v1_samples.json").write_text("{}")
    new = _bundle(tmp_path, "new", [{"label": "You", "rpy_file": "ME2.rpy", "best_lap_index": 12}, erik], [])
    assert cs.adopt_shared("new", exports=str(tmp_path)) == 1
    assert cs.adopt_shared("new", exports=str(tmp_path)) == 0          # idempotent
    assert (new / "video_v1_samples.json").exists()
    # the new plan names the corner differently: the clip still covers it, so it is kept
    pr = prune("new", exports=str(tmp_path), keep_corners={"La Source"}, keep_spans=[(210.0, 544.0)])
    assert pr["removed"] == []
    # a plan that no longer needs it drops the entry, but the file stays: the old bundle still uses it
    pr = prune("new", exports=str(tmp_path), keep_corners={"Bruxelles"}, keep_spans=[(2836.0, 3216.0)])
    assert len(pr["removed"]) == 1 and clip.exists()


def test_adopt_skips_other_laps_and_other_replays(tmp_path):
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    base = {"driver": "Erik", "tool": "vre", "kind": "full", "camera": "Drivable/Dash", "file": str(clip)}
    _bundle(tmp_path, "old", [], [dict(base, id="a", rpy_file="ERIK.rpy", laps=[{"lap_index": 2}]),
                                  dict(base, id="b", rpy_file="OTHER.rpy", laps=[{"lap_index": 4}])])
    _bundle(tmp_path, "new", [{"label": "Erik", "rpy_file": "ERIK.rpy", "best_lap_index": 4}], [])
    assert cs.adopt_shared("new", exports=str(tmp_path)) == 0
