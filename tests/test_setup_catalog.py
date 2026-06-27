import os

from setup_catalog import SetupCatalog


def test_catalog_loads_levers(car_catalog):
    levers = car_catalog.all_levers()
    assert len(levers) > 50
    assert car_catalog.lever("WING_0") is not None
    assert car_catalog.lever("CUSTOM_SCRIPT_ITEM_4") is not None


def test_recommend_entry_understeer(car_catalog):
    recs = car_catalog.recommend("entry_understeer", "entry", tier_max="A")
    sections = [r["section"] for r in recs]
    assert "WING_0" in sections
    assert "CUSTOM_SCRIPT_ITEM_4" in sections


def test_validate_delta_clamps(car_catalog):
    delta, new = car_catalog.validate_delta("WING_0", 29, 5)
    lever = car_catalog.lever("WING_0")
    assert new <= lever.max_val


def test_read_fixture_ini(car_catalog):
    fixture = os.path.join(
        os.path.dirname(__file__), "fixtures", "generic_last.ini"
    )
    values = car_catalog.read_current_values(fixture)
    assert values["WING_0"] == 29
    assert values["CUSTOM_SCRIPT_ITEM_4"] == 3
