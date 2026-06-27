import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AC_APP = os.path.join(ROOT, "ac_app")
LIB = os.path.join(AC_APP, "lib")

if AC_APP not in sys.path:
    sys.path.insert(0, AC_APP)
if LIB not in sys.path:
    sys.path.insert(0, LIB)


@pytest.fixture
def config_dir():
    return os.path.join(AC_APP, "config")


@pytest.fixture
def thresholds(config_dir):
    import json
    with open(os.path.join(config_dir, "thresholds.json"), "r") as fh:
        return json.load(fh)


@pytest.fixture
def car_catalog(config_dir):
    from setup_catalog import SetupCatalog
    car = os.path.join(config_dir, "car_rss_fh_x_2026.json")
    sym = os.path.join(config_dir, "setup_symptom_map.json")
    return SetupCatalog(car, sym)


@pytest.fixture
def monza_indexer(config_dir):
    from spline_indexer import SplineIndexer
    return SplineIndexer.from_track_file(
        os.path.join(config_dir, "tracks", "monza.json")
    )
