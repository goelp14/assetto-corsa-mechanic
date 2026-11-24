"""Live ACC mechanic: ac_app's engineer running on (synthetic) ACC shared-memory pages."""

import ctypes
import json
import math
import os

import pytest

from external.acc_mechanic import acc_setup
from external.acc_mechanic.shm import STATUS_LIVE, AccInfo, Graphics, Physics, Static

BASE_SETUP = {
    "carName": "ferrari_296_gt3",
    "basicSetup": {
        "tyres": {"tyreCompound": 0, "tyrePressure": [59, 60, 55, 56]},
        "alignment": {"camber": [0, 0, 0, 0], "toe": [5, 5, 30, 30], "casterLF": 30, "casterRF": 30},
        "electronics": {"tC1": 7, "tC2": 1, "abs": 2, "eCUMap": 0},
    },
    "advancedSetup": {
        "mechanicalBalance": {"aRBFront": 5, "aRBRear": 0, "wheelRate": [0, 0, 0, 0], "brakeBias": 44},
        "dampers": {"bumpSlow": [0, 0, 0, 0], "bumpFast": [0, 0, 0, 0], "reboundSlow": [11, 11, 11, 11]},
        "aeroBalance": {"rideHeight": [0, 6, 0, 18], "splitter": 0, "rearWing": 5},
        "drivetrain": {"preload": 0},
    },
}


def _wset(struct, name, text):
    arr = getattr(struct, name)
    for i, ch in enumerate(text[: len(arr) - 1]):
        arr[i] = ord(ch)


class FakeSource:
    """Serves one car lapping Spa: pages built from ctypes structs, mutated per tick."""

    def __init__(self):
        self.p, self.g, self.s = Physics(), Graphics(), Static()
        _wset(self.s, "smVersion", "1.9")
        _wset(self.s, "carModel", "ferrari_296_gt3")
        _wset(self.s, "track", "Spa")
        _wset(self.g, "tyreCompound", "dry_compound")
        self.g.status = STATUS_LIVE
        self.g.activeCars = 1
        self.g.playerCarID = 1001
        self.g.carID[0] = 1001
        self.t = 0.0

    def step(self, dt=0.02):
        self.t += dt
        p, g = self.p, self.g
        p.packetId += 1
        p.speedKmh = 180.0 + 40.0 * math.sin(self.t / 3.0)
        p.gas, p.brake, p.gear, p.rpms = 0.9, 0.0, 4, 7000
        p.steerAngle = 0.1 * math.sin(self.t)
        p.heading = (self.t * 0.05) % (2 * math.pi) - math.pi
        for i in range(4):
            p.tyreCoreTemperature[i] = 82.0 + i
            p.wheelsPressure[i] = 26.4
            p.wheelLoad[i] = 4000.0
            p.brakeTemp[i] = 450.0
        g.normalizedCarPosition = (self.t / 140.0) % 1.0
        g.iCurrentTime = int((self.t % 140.0) * 1000)
        g.carCoordinates[0][0], g.carCoordinates[0][2] = 100.0 * math.cos(self.t / 20), 100.0 * math.sin(self.t / 20)

    def read(self):
        return bytes(self.p), bytes(self.g), bytes(self.s)

    def close(self):
        pass


@pytest.fixture
def acc_docs(tmp_path, monkeypatch):
    docs = tmp_path / "ACC"
    folder = docs / "Setups" / "ferrari_296_gt3" / "Spa"
    folder.mkdir(parents=True)
    (folder / "My quali.json").write_text(json.dumps(BASE_SETUP))
    monkeypatch.setenv("VRE_ACC_DOCUMENTS", str(docs))
    return folder


def test_pages_parse_like_sim_info():
    src = FakeSource()
    src.step()
    info = AccInfo(src)
    assert info.update() and info.status == STATUS_LIVE
    assert info.static.carModel == "ferrari_296_gt3" and info.static.track == "Spa"
    assert info.graphics.tyreCompound == "dry_compound"
    assert info.graphics.carCoordinates == pytest.approx((100.0 * math.cos(0.001), 0.0, 100.0 * math.sin(0.001)), abs=1e-3)
    assert ctypes.sizeof(Physics) == 800


def test_setup_values_and_writer(acc_docs):
    vals = acc_setup.read_values(str(acc_docs / "My quali.json"))
    assert vals["PRESSURE_LF"] == pytest.approx(26.2) and vals["ARB_FRONT"] == 5 and vals["DIFF_PRELOAD"] == 20.0
    w = acc_setup.AccSetupWriter("ferrari_296_gt3")
    out, err = w.ensure_auto_tweak("spa")           # case-insensitive track folder
    assert not err and out.endswith(os.path.join("Spa", "Auto_Tweak.json"))
    assert os.path.basename(w.last_base) == "My quali.json"

    class D:
        def __init__(self, section, new_value):
            self.section, self.new_value = section, new_value

    w.apply_deltas(out, [D("ARB_FRONT", 4), D("PRESSURE_RR", 25.8), D("DIFF_PRELOAD", 30.0)])
    doc = json.load(open(out))
    assert doc["advancedSetup"]["mechanicalBalance"]["aRBFront"] == 4
    assert doc["basicSetup"]["tyres"]["tyrePressure"] == [59, 60, 55, 55]
    assert doc["advancedSetup"]["drivetrain"]["preload"] == 1
    assert doc["basicSetup"]["electronics"] == BASE_SETUP["basicSetup"]["electronics"]   # untouched
    assert w.find_base_ini("Spa").endswith("My quali.json")                              # never bases on own output


def test_profile_and_symptom_map():
    prof = acc_setup.build_profile("ferrari_296_gt3")
    assert prof["tyre_window"]["core_temp_ideal_min_c"] == 70.0
    assert {lv["section"] for lv in prof["levers"]} >= {"ARB_FRONT", "PRESSURE_LF", "WING_1"}
    m = acc_setup.acc_symptom_map({"x": {"entry": [{"section": "DIFF_PRELOAD", "delta": 10}]}})
    assert m["x"]["entry"][0] == {"section": "DIFF_PRELOAD", "steps": 1}


def test_mechanic_runs_engineer_on_acc(acc_docs, tmp_path):
    from external.acc_mechanic.runner import Mechanic

    src = FakeSource()
    mech = Mechanic(AccInfo(src), data_dir=str(tmp_path / "live"))
    for _ in range(300):
        src.step()
        assert mech.tick()
    vre = mech.vre
    assert vre._car_id == "ferrari_296_gt3"
    assert vre._spline.load_config is not None and not vre._load_track_config("Spa", "").get("generic")
    assert vre._catalog.lever("ARB_FRONT") is not None and vre._catalog.lever("DIFF_COAST") is None
    assert isinstance(vre._setup_writer, acc_setup.AccSetupWriter)
    st = mech.state()
    json.dumps(st, default=str)
    assert st["status"] == "live" and st["car"] == "ferrari_296_gt3"
    assert st["tyres"]["psi"][0] == pytest.approx(26.4)
    assert st["hud"]["tyre_ideal_lo"] == 70
    assert mech.tick() is False            # no new physics packet → engineer not re-run
    src.g.status = 3                        # paused
    src.step()
    assert mech.tick() is False
    mech.shutdown()


def test_voice_lines_name_the_acc_file():
    from external.acc_mechanic.runner import _say_text

    assert _say_text("Load Auto_Tweak.ini in the setup screen.") == "Load the Auto Tweak setup in the setup screen."
