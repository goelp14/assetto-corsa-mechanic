import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AC_APP = os.path.join(ROOT, "ac_app")
if AC_APP not in sys.path:
    sys.path.insert(0, AC_APP)

from ac_paths import (
    reset_path_cache,
    resolve_ac_userdata_dir,
    resolve_car_setups_root,
    resolve_track_setup_folder,
)


def _layout(tmp, rel):
    path = os.path.join(tmp, rel)
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    if rel.endswith(".ini"):
        with open(path, "w") as fh:
            fh.write("[WING_0]\nVALUE=29\n")
    else:
        os.makedirs(path)
    return path


def test_prefers_onedrive_when_only_setups_live_there(tmp_path, monkeypatch):
    reset_path_cache()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("AC_USERDATA", raising=False)
    monkeypatch.delenv("ONEDRIVE", raising=False)

    _layout(str(home), "Documents/Assetto Corsa/logs")
    _layout(
        str(home),
        "OneDrive/Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/monaco_2020/base.ini",
    )

    userdata = resolve_ac_userdata_dir(refresh=True)
    assert userdata is not None
    assert "OneDrive" in userdata.replace("\\", "/")
    assert resolve_track_setup_folder(
        "monaco_2020", track_cfg={"setup_folder": "monaco_2020"},
    ) == "monaco_2020"


def test_env_override_wins(tmp_path, monkeypatch):
    reset_path_cache()
    custom = tmp_path / "custom_ac"
    _layout(str(custom), "setups/rss_formula_hybrid_x_2026/generic/last.ini")
    monkeypatch.setenv("AC_USERDATA", str(custom))

    assert resolve_ac_userdata_dir(refresh=True) == str(custom)
    assert resolve_track_setup_folder("monaco_2020") == "generic"


def test_onedrive_env_variable(tmp_path, monkeypatch):
    reset_path_cache()
    home = tmp_path / "home"
    home.mkdir()
    od = tmp_path / "cloud"
    _layout(str(od), "Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/monaco_2020/base.ini")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ONEDRIVE", str(od))

    userdata = resolve_ac_userdata_dir(refresh=True)
    assert userdata == os.path.join(str(od), "Documents", "Assetto Corsa")


def test_standard_documents_still_works(tmp_path, monkeypatch):
    reset_path_cache()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _layout(str(home), "Documents/Assetto Corsa/setups/rss_formula_hybrid_x_2026/monaco_2020/base.ini")

    userdata = resolve_ac_userdata_dir(refresh=True)
    assert userdata == os.path.join(str(home), "Documents", "Assetto Corsa")
