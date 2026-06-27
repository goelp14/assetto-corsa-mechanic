from spline_indexer import SplineIndexer


def test_corner_speed_class():
    idx = SplineIndexer({
        "track_id": "test",
        "corners": [
            {"name": "Tabac", "speed_class": "high", "spline_start": 0.1, "spline_end": 0.2},
        ],
    })
    assert idx.corner_speed_class("Tabac") == "high"
    assert idx.corner_speed_class("Unknown") == "medium"
