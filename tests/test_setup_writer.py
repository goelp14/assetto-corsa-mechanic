import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AC_APP = os.path.join(ROOT, "ac_app")
if AC_APP not in sys.path:
    sys.path.insert(0, AC_APP)

from ac_paths import reset_path_cache
from setup_catalog import SetupCatalog
from setup_detector import SetupDelta
from setup_writer import SetupWriter


def test_apply_deltas(car_catalog):
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "generic_last.ini")
    tmpdir = tempfile.mkdtemp()
    try:
        out = os.path.join(tmpdir, "Auto_Tweak.ini")
        shutil.copy(fixture, out)
        writer = SetupWriter(car_catalog)
        deltas = [SetupDelta("WING_0", 1, "test", old_value=29, new_value=30)]
        writer.apply_deltas(out, deltas, lap=1, reason="test")
        values = car_catalog.read_current_values(out)
        assert values["WING_0"] == 30
    finally:
        shutil.rmtree(tmpdir)


def test_ensure_auto_tweak_creates_file(car_catalog, tmp_path, monkeypatch):
    reset_path_cache()
    custom = tmp_path / "ac"
    folder = custom / "setups" / "rss_formula_hybrid_x_2026" / "monaco_2020"
    folder.mkdir(parents=True)
    base = folder / "base.ini"
    base.write_text("[WING_0]\nVALUE=29\n")
    monkeypatch.setenv("AC_USERDATA", str(custom))

    writer = SetupWriter(car_catalog)
    out, err = writer.ensure_auto_tweak("monaco_2020")
    assert err == ""
    assert os.path.isfile(out)
    assert out.endswith("Auto_Tweak.ini")
    values = car_catalog.read_current_values(out)
    assert values["WING_0"] == 29


def test_find_base_ini_uses_onedrive_root(car_catalog, tmp_path, monkeypatch):
    reset_path_cache()
    home = tmp_path / "home"
    home.mkdir()
    od = home / "OneDrive" / "Documents" / "Assetto Corsa"
    folder = od / "setups" / "rss_formula_hybrid_x_2026" / "monaco_2020"
    folder.mkdir(parents=True)
    (folder / "monaco 2026.ini").write_text("[WING_0]\nVALUE=30\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    writer = SetupWriter(car_catalog)
    base = writer.find_base_ini("monaco_2020")
    assert base is not None
    assert base.endswith("monaco 2026.ini")


def test_find_base_ini_prefers_named_setup_over_last(car_catalog, tmp_path, monkeypatch):
    reset_path_cache()
    custom = tmp_path / "ac"
    folder = custom / "setups" / "rss_formula_hybrid_x_2026" / "monaco_2020"
    folder.mkdir(parents=True)
    (folder / "monaco 2026.ini").write_text("[WING_0]\nVALUE=30\n")
    (folder / "last.ini").write_text("[WING_0]\nVALUE=31\n")
    monkeypatch.setenv("AC_USERDATA", str(custom))

    writer = SetupWriter(car_catalog)
    base = writer.find_base_ini("monaco_2020")
    assert base.endswith("monaco 2026.ini")


def test_ensure_auto_tweak_does_not_reseed_existing(car_catalog, tmp_path, monkeypatch):
    reset_path_cache()
    custom = tmp_path / "ac"
    folder = custom / "setups" / "rss_formula_hybrid_x_2026" / "monaco_2020"
    folder.mkdir(parents=True)
    base = folder / "monaco 2026.ini"
    out = folder / "Auto_Tweak.ini"
    base.write_text("[WING_0]\nVALUE=30\n")
    out.write_text("[WING_0]\nVALUE=10\n")
    monkeypatch.setenv("AC_USERDATA", str(custom))

    import time
    time.sleep(0.02)
    base.write_text("[WING_0]\nVALUE=32\n")

    writer = SetupWriter(car_catalog)
    path, err = writer.ensure_auto_tweak("monaco_2020")
    assert err == ""
    values = car_catalog.read_current_values(path)
    assert values["WING_0"] == 10
