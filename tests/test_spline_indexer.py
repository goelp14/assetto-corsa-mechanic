def test_monza_corners(monza_indexer):
    assert monza_indexer.corner_name(0.15) == "Turn 4"
    assert monza_indexer.bin(0.0) == 0
    assert monza_indexer.bin(0.999) == 359


def test_monaco_landmarks():
    import json
    import os
    from spline_indexer import SplineIndexer
    path = os.path.join(
        os.path.dirname(__file__), "..", "ac_app", "config", "tracks", "monaco_2020.json",
    )
    with open(path) as fh:
        idx = SplineIndexer(json.load(fh))
    assert idx.corner_name(0.70) == "Rascasse"
    assert idx.corner_display_name("Rascasse") == "Rascasse"
    lm = idx.corner_landmarks("Rascasse")
    assert "pool" in lm["brake_cue"].lower()
    assert idx.corner_name(0.78) == "Final Corner"


def test_upcoming_corner_before_rascasse():
    import json
    import os
    from spline_indexer import SplineIndexer
    path = os.path.join(
        os.path.dirname(__file__), "..", "ac_app", "config", "tracks", "monaco_2020.json",
    )
    with open(path) as fh:
        idx = SplineIndexer(json.load(fh))
    upcoming = idx.upcoming_corner(0.66)
    assert upcoming is not None
    assert upcoming.get("name") in ("Tabac", "Rascasse", "Swimming Pool")


def test_spline_offset():
    from spline_indexer import SplineIndexer
    idx = SplineIndexer({
        "track_id": "test",
        "spline_offset": 0.1,
        "corners": [],
    })
    plain = SplineIndexer({"track_id": "test", "spline_offset": 0.0, "corners": []})
    assert idx.bin(0.0) == plain.bin(0.1)
