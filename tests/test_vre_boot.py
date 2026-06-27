# Boot smoke tests — catch import/syntax/init failures that hide the VRE HUD in AC.
# Python 3.3 compatible — stdlib only

import importlib
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
def vre():
    return _load_vre_module()


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
