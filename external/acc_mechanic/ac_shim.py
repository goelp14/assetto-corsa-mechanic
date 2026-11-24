"""Stand-ins for AC's in-game ``ac`` / ``acsys`` modules so ac_app runs headless on ACC data.

Labels the app creates are recorded (text + colour) so the dashboard and overlay can show them.
GL drawing calls are no-ops.
"""

from __future__ import annotations

import types


class _CS:
    NormalizedSplinePosition = 0
    LapTime = 1


class AcShim:
    def __init__(self, info):
        self._info = info
        self._next_id = 100
        self.labels = {}       # id -> {"text", "color", "size"}
        self.window_size = (0, 0)

    def _new(self):
        self._next_id += 1
        return self._next_id

    # --- app window ---
    def newApp(self, name):
        return self._new()

    def setTitle(self, *a):
        pass

    def setSize(self, window, w, h):
        self.window_size = (w, h)

    def setPosition(self, *a):
        pass

    def drawBorder(self, *a):
        pass

    def setBackgroundOpacity(self, *a):
        pass

    def addRenderCallback(self, *a):
        pass

    def ext_setStrictMode(self):
        pass

    # --- labels ---
    def addLabel(self, window, text):
        lid = self._new()
        self.labels[lid] = {"text": text or "", "color": [1.0, 1.0, 1.0, 1.0], "size": 12}
        return lid

    def setText(self, label, text):
        if label in self.labels:
            self.labels[label]["text"] = text

    def setFontSize(self, label, size):
        if label in self.labels:
            self.labels[label]["size"] = size

    def setFontColor(self, label, r, g, b, a):
        if label in self.labels:
            self.labels[label]["color"] = [r, g, b, a]

    def setFontAlignment(self, *a):
        pass

    def setFontOutline(self, *a):
        pass

    # --- GL (HUD bars): not drawn headless ---
    def glColor4f(self, *a):
        pass

    def glColor3f(self, *a):
        pass

    def glQuad(self, *a):
        pass

    def glBegin(self, *a):
        pass

    def glEnd(self, *a):
        pass

    def glVertex2f(self, *a):
        pass

    # --- car state ---
    def getCarState(self, car_id, state):
        g = self._info.graphics
        if state == _CS.NormalizedSplinePosition:
            return float(g.normalizedCarPosition)
        if state == _CS.LapTime:
            return int(g.iCurrentTime)
        return 0

    def getTrackConfiguration(self, car_id=0):
        return ""

    def getTrackLength(self, car_id=0):
        return 0.0

    def log(self, *a):
        pass

    def console(self, *a):
        pass


def install(info):
    """Register fake ``ac`` / ``acsys`` / ``sim_info`` modules. Returns the AcShim."""
    import sys

    shim = AcShim(info)
    ac_mod = types.ModuleType("ac")
    for name in dir(shim):
        if not name.startswith("_"):
            setattr(ac_mod, name, getattr(shim, name))
    ac_mod.shim = shim
    acsys_mod = types.ModuleType("acsys")
    acsys_mod.CS = _CS
    sim_mod = types.ModuleType("sim_info")
    sim_mod.info = info
    sys.modules["ac"] = ac_mod
    sys.modules["acsys"] = acsys_mod
    sys.modules["sim_info"] = sim_mod
    return shim
