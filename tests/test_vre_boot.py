# Boot smoke tests — catch import/syntax/init failures that hide the VRE HUD in AC.
# Python 3.3 compatible — stdlib only

import importlib
import math
import os
import sys
import types

import pytest

from vre_ac_compat import AC_APP_ROOT, check_python33_compat, iter_ac_app_sources

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AC_APP = os.path.join(ROOT, "ac_app")


class _FakeCS(object):
    NormalizedSplinePosition = 0
    LapTime = 1


class _FakeAcSys(object):
    CS = _FakeCS


class _FakeAc(object):
    def newApp(self, name):
        return 42

    def setTitle(self, window, title):
        pass

    def setSize(self, window, w, h):
        pass

    def setPosition(self, window, x, y):
        pass

    def drawBorder(self, window, flag):
        pass

    def setBackgroundOpacity(self, window, opacity):
        pass

    def addRenderCallback(self, window, callback):
        pass

    def addLabel(self, window, text):
        return 1

    def setText(self, label, text):
        pass

    def setFontSize(self, label, size):
        pass

    def setFontAlignment(self, label, align):
        pass

    def setFontColor(self, label, *rgba):
        pass

    def setFontOutline(self, label, flag):
        pass

    def getCarState(self, car_id, state):
        return 0

    def ext_setStrictMode(self):
        pass

    def ext_getAngleSpeed(self, car_id=0):
        return 0.0


class _FakeGraphics(object):
    normalizedCarPosition = 0.0
    tyreCompound = ""
    iCurrentTime = 0
    status = 2
    completedLaps = 0
    currentSectorIndex = 0
    isInPit = 0
    carCoordinates = (0.0, 0.0, 0.0)


class _FakePhysics(object):
    speedKmh = 0.0
    gas = 0.0
    brake = 0.0
    steerAngle = 0.0
    gear = 4
    rpms = 8500
    velocity = (0.0, 0.0, 0.0)
    accG = (0.0, 0.0, 0.0)
    heading = 0.0
    roll = 0.0
    yawRate = 0.0
    wheelSlip = (0.0, 0.0, 0.0, 0.0)
    wheelLoad = (0.0, 0.0, 0.0, 0.0)
    wheelsPressure = (0.0, 0.0, 0.0, 0.0)
    tyreCoreTemperature = (0.0, 0.0, 0.0, 0.0)
    camberRAD = (0.0, 0.0, 0.0, 0.0)
    suspensionTravel = (0.0, 0.0, 0.0, 0.0)


class _FakeStatic(object):
    acTrack = "monza"
    carModel = "rss_formula_hybrid_x_2026"
    track = "monza"
    suspensionMaxTravel = (0.1, 0.1, 0.1, 0.1)


class _FakeInfo(object):
    graphics = _FakeGraphics()
    physics = _FakePhysics()
    static = _FakeStatic()


def _install_ac_mocks():
    sys.modules["ac"] = _FakeAc()
    sys.modules["acsys"] = _FakeAcSys()
    sim_info = types.ModuleType("sim_info")
    sim_info.info = _FakeInfo()
    sys.modules["sim_info"] = sim_info


def _load_vre_module():
    _install_ac_mocks()
    if AC_APP not in sys.path:
        sys.path.insert(0, AC_APP)
    sys.modules.pop("VirtualRaceEngineer", None)
    return importlib.import_module("VirtualRaceEngineer")


@pytest.fixture(scope="module")
def vre(tmp_path_factory):
    module = _load_vre_module()
    data_root = str(tmp_path_factory.mktemp("vre_data"))
    module._data_path = lambda *parts: os.path.join(data_root, *parts)
    return module


def test_ac_app_sources_compile_and_are_python33_compatible():
    errors = []
    for path in iter_ac_app_sources():
        rel = os.path.relpath(path, AC_APP_ROOT)
        try:
            errors.extend(check_python33_compat(path))
        except SyntaxError as exc:
            errors.append("%s: SyntaxError: %s" % (rel, exc))
    assert not errors, "AC app uses Python >3.3 syntax:\n" + "\n".join(errors)


def test_vre_import_block_resolves_all_symbols():
    """Regression: missing imports (e.g. SessionPhaseStore) kill acMain before HUD."""
    import ast

    entry = os.path.join(AC_APP, "VirtualRaceEngineer.py")
    with open(entry, "r") as fh:
        tree = ast.parse(fh.read(), filename=entry)
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.Try):
            for stmt in node.body:
                if isinstance(stmt, ast.ImportFrom) and stmt.module:
                    for alias in stmt.names:
                        name = alias.asname or alias.name
                        imported.add(name)
    vre = _load_vre_module()
    missing = sorted(name for name in imported if not hasattr(vre, name))
    assert not missing, "VirtualRaceEngineer import block names not defined: %s" % missing


def test_vre_init_modules_boots(vre):
    vre._initialized = False
    vre._init_modules()
    assert vre._initialized is True
    assert vre._session_phase is not None
    assert vre._archive is not None
    assert vre._volatility is not None


def test_vre_acmain_creates_app_window(vre):
    vre._initialized = False
    name = vre.acMain(1)
    assert name == "Virtual Race Engineer"
    assert vre._app_window == 42


def test_vre_acupdate_one_tick_without_crash(vre):
    vre._initialized = False
    vre.acMain(1)
    vre.acUpdate(0.016)
    assert vre._ingest is not None


def test_vre_switches_car_and_layout(vre, monkeypatch):
    static = sys.modules["sim_info"].info.static
    vre._initialized = False
    vre.acMain(1)
    vre.acUpdate(0.016)
    assert vre._store_key == "monza"
    monkeypatch.setattr(static, "carModel", "ks_ferrari_312_67", raising=False)
    monkeypatch.setattr(static, "track", "rt_sonoma", raising=False)
    monkeypatch.setattr(static, "trackConfiguration", "long", raising=False)
    vre.acUpdate(0.016)
    assert vre._store_key == "rt_sonoma-long__ks_ferrari_312_67"
    assert vre._track_profile.profile_id == "sonoma"
    assert vre._catalog.lever("WING_0") is None
    assert abs(vre._balance.wheelbase - 2.40) < 0.05
    assert vre._balance.lat_g_per_ms == 0.0
    assert abs(vre._ingest._max_road_wheel_rad - math.radians(22.5)) < 1e-9
    assert vre._tyre_tracker.ideal_temp_range() == (40, 110)


def test_track_config_falls_back_when_ac_reports_no_layout(vre):
    cfg = vre._load_track_config("rt_sonoma", "")
    assert not cfg.get("generic") and len(cfg["corners"]) == 10
    assert vre._load_track_config("rt_sonoma", "", 3974.0)["corners"] == cfg["corners"]
    assert vre._load_track_config("no_such_track", "").get("generic")


def test_pit_entry_applies_queued_tweak_once(vre, tmp_path, monkeypatch):
    from lib.setup_detector import SetupDelta
    info = sys.modules["sim_info"].info
    monkeypatch.setattr(info.static, "carModel", "ks_ferrari_312_67", raising=False)
    monkeypatch.setattr(info.static, "track", "rt_sonoma", raising=False)
    monkeypatch.setattr(info.static, "trackConfiguration", "long", raising=False)
    vre._initialized = False
    vre.acMain(1)
    vre.acUpdate(0.016)
    folder = tmp_path / vre._track_folder
    folder.mkdir(parents=True)
    for name in ("Base.ini", "Auto_Tweak.ini"):
        (folder / name).write_text("[DIFF_PRELOAD]\nVALUE=10\n\n[CAR]\nMODEL=ks_ferrari_312_67\n")
    monkeypatch.setattr(vre._setup_writer, "_documents_setups_dir", lambda: str(tmp_path))
    frame = vre._ingest.sample(0.016)
    vre._queue_pit_tweak(SetupDelta("DIFF_PRELOAD", 10.0, "exit wheelspin", old_value=10.0, new_value=20.0),
                         frame, corner="Turn 6", phase="exit", symptom="exit_wheelspin", notify=False)
    pending = len(vre._setup_memory.tweaks)
    entries = []
    monkeypatch.setattr(vre._archive, "record_pit_transition", lambda kind, lap, spline=0.0: entries.append(kind))
    monkeypatch.setattr(info.graphics, "isInPit", 1)
    for _ in range(5):
        vre.acUpdate(0.016)
    assert entries == ["entry"]
    assert len(vre._setup_memory.tweaks) == pending + 1
    assert vre._pit_tweak_queue == []


def test_stint_counter_boxes_after_target_and_resets_on_pit_exit(vre, monkeypatch):
    info = sys.modules["sim_info"].info
    monkeypatch.setattr(info.static, "carModel", "ks_ferrari_312_67", raising=False)
    monkeypatch.setattr(info.static, "track", "rt_sonoma", raising=False)
    monkeypatch.setattr(info.static, "trackConfiguration", "long", raising=False)
    vre._initialized = False
    vre.acMain(1)
    vre.acUpdate(0.016)
    monkeypatch.setattr(vre, "_completed_lap_time_ms", lambda frame: 95000)
    frame = vre._ingest.sample(0.016)
    for lap in range(1, 8):
        vre._on_lap_complete(lap, frame, vre.LAP_FLYING)
    assert vre._stint.done and vre._box_alert.remaining == 3
    vre._update_stint_label()
    assert vre._ui_text_cache["stint_line"] == "BOX BOX - 5/5 DONE"
    vre._on_pit_exit(8, frame)
    assert vre._stint.block == 2 and vre._stint.hud_text() == "SETTLE LAP 1/2"
