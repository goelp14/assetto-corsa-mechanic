# Session archive must restart after VRE reload on the same track.

import importlib
import os
import sys
import types

import pytest

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
    iLastTime = 0
    status = 2
    completedLaps = 0
    currentSectorIndex = 0
    isInPit = 0
    carCoordinates = (0.0, 0.0, 0.0)


class _FakePhysics(object):
    speedKmh = 120.0
    gas = 0.5
    brake = 0.0
    steerAngle = 0.0
    gear = 4
    rpms = 8500
    velocity = (30.0, 0.0, 0.0)
    accG = (0.0, 1.0, 0.0)
    heading = 0.0
    roll = 0.0
    yawRate = 0.0
    wheelSlip = (0.0, 0.0, 0.0, 0.0)
    wheelLoad = (0.0, 0.0, 0.0, 0.0)
    wheelsPressure = (0.0, 0.0, 0.0, 0.0)
    tyreCoreTemperature = (80.0, 80.0, 80.0, 80.0)
    camberRAD = (0.0, 0.0, 0.0, 0.0)
    suspensionTravel = (0.0, 0.0, 0.0, 0.0)


class _FakeStatic(object):
    acTrack = "monaco_2020"
    carModel = "rss_formula_hybrid_x_2026"
    track = "monaco_2020"
    suspensionMaxTravel = (0.1, 0.1, 0.1, 0.1)


class _FakeInfo(object):
    graphics = _FakeGraphics()
    physics = _FakePhysics()
    static = _FakeStatic()


def _load_vre(tmp_path):
    sys.modules["ac"] = _FakeAc()
    sys.modules["acsys"] = _FakeAcSys()
    sim_info = types.ModuleType("sim_info")
    sim_info.info = _FakeInfo()
    sys.modules["sim_info"] = sim_info
    if AC_APP not in sys.path:
        sys.path.insert(0, AC_APP)
    sys.modules.pop("VirtualRaceEngineer", None)
    vre = importlib.import_module("VirtualRaceEngineer")
    sessions = os.path.join(tmp_path, "sessions")
    os.makedirs(sessions, exist_ok=True)
    vre._data_path = lambda *parts: os.path.join(tmp_path, *parts)
    return vre


def test_session_restarts_after_shutdown_on_same_track(tmp_path):
    vre = _load_vre(tmp_path)
    vre.acMain(0)
    vre.acUpdate(0.016)
    first_dir = vre._archive.session_dir
    assert first_dir is not None

    vre.ext_acReload()
    vre.acUpdate(0.016)
    second_dir = vre._archive.session_dir
    assert second_dir is not None
    assert second_dir != first_dir
