"""Footage pruning: superseded, no-longer-fastest, replaced-replay recordings go; foreign files stay."""

import json

from external.query_tools.video_store import prune


def test_prune_rules(tmp_path):
    b = tmp_path / "lab_x"
    b.mkdir()
    (b / "manifest.json").write_text(json.dumps({"drivers": [
        {"label": "You", "best_lap_index": 17, "rpy_file": "me.rpy"},
        {"label": "Erik", "best_lap_index": 4, "rpy_file": "erik_new.rpy"}]}))
    files = {}

    def vid(i, driver, lap, rec, **kw):
        f = tmp_path / ("%s.mp4" % i)
        f.write_bytes(b"x" * 10)
        files[i] = f
        v = {"id": i, "driver": driver, "file": str(f), "recorded": rec, "tool": "vre", "kind": "full",
             "camera": "Drivable/Dash", "rpy_file": "me.rpy" if driver == "You" else "erik_new.rpy",
             "laps": [{"lap_index": lap, "complete": True}]}
        v.update(kw)
        return v

    videos = [
        vid("old7", "You", 7, "2026-01-01T10:00"),                       # not fastest any more
        vid("a17", "You", 17, "2026-01-01T11:00"),                       # superseded by b17
        vid("b17", "You", 17, "2026-01-01T12:00"),                       # keep
        vid("e4old", "Erik", 4, "2026-01-01T09:00", rpy_file="erik_old.rpy"),   # reference replaced
        vid("chase", "You", 17, "2026-01-01T12:01", kind="angle", corner="T1", camera="Drivable/Chase",
            laps=[{"lap_index": 17, "complete": False}]),                # keep (angle clip of fastest lap)
        vid("foreign", "You", 7, "2026-01-01T08:00", tool=None),         # not ours: never deleted
    ]
    (b / "videos.json").write_text(json.dumps({"videos": videos}))
    out = prune("lab_x", exports=str(tmp_path))
    gone = {r["id"]: r["reason"] for r in out["removed"]}
    assert set(gone) == {"old7", "a17", "e4old"}
    assert gone["a17"].startswith("superseded")
    kept = [v["id"] for v in json.loads((b / "videos.json").read_text())["videos"]]
    assert sorted(kept) == ["b17", "chase", "foreign"]
    assert not files["old7"].exists() and files["b17"].exists() and files["foreign"].exists()
    assert out["freed_bytes"] == 30
