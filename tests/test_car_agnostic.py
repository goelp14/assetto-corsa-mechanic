import os

from setup_catalog import SetupCatalog
from track_profile import TrackProfileStore
from tyre_window import TyreWindowTracker


def _ferrari_catalog(config_dir):
    return SetupCatalog(
        os.path.join(config_dir, "cars", "ks_ferrari_312_67.json"),
        os.path.join(config_dir, "setup_symptom_map.json"),
    )


def test_ferrari_has_no_aero_levers(config_dir):
    cat = _ferrari_catalog(config_dir)
    assert cat.lever("WING_0") is None
    assert cat.lever("ARB_FRONT") is not None


def test_ferrari_recommendations_only_use_existing_levers(config_dir):
    cat = _ferrari_catalog(config_dir)
    for symptom, phase in (("mid_understeer", "mid"), ("entry_oversteer", "entry"),
                           ("exit_oversteer", "exit")):
        for rec in cat.recommend(symptom, phase, tier_max="B"):
            assert cat.lever(rec["section"]) is not None


def test_steps_scale_by_lever_step(config_dir):
    cat = _ferrari_catalog(config_dir)
    assert cat.item_delta({"section": "ARB_FRONT", "steps": -1}) == -1
    spring = cat.lever("SPRING_RATE_LR")
    assert cat.item_delta({"section": "SPRING_RATE_LR", "steps": 1}) == spring.step


def test_ferrari_camber_in_tenths(config_dir):
    lever = _ferrari_catalog(config_dir).lever("CAMBER_LF")
    assert lever.min_val == -20 and lever.max_val >= 0


def test_sonoma_layout_resolves_profile():
    store = TrackProfileStore()
    assert store.resolve("rt_sonoma", "long").profile_id == "sonoma"
    assert store.resolve("rt_sonoma").profile_id == "sonoma"


def test_car_tyre_window_overrides_generic_table():
    tracker = TyreWindowTracker()
    window = {"core_temp_ideal_min_c": 40.0, "core_temp_ideal_max_c": 110.0,
              "core_temp_cold_c": 24.0, "core_temp_hot_c": 140.0}
    tracker.set_car_windows(window, {"gp67": window})
    tracker.set_compound("GP67")
    assert tracker.ideal_temp_range() == (40.0, 110.0)
