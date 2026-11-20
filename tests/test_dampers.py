import os
import sys

LIB = os.path.join(os.path.dirname(__file__), "..", "ac_app", "lib")
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from damper_histogram import DamperHistogram, merge, wheel_stats, NBINS  # noqa: E402
from damper_model import damper_report, setup_physical  # noqa: E402

SUSP = """
[BASIC]
WHEELBASE=2.4
CG_LOCATION=0.35
[ARB]
FRONT=12000
REAR=4500
[FRONT]
TRACK=1.551
HUB_MASS=27
SPRING_RATE=20000
DAMP_BUMP=1216
DAMP_REBOUND=1836
DAMP_FAST_BUMP=634
DAMP_FAST_BUMPTHRESHOLD=0.050
DAMP_FAST_REBOUND=1000
DAMP_FAST_REBOUNDTHRESHOLD=0.110
[REAR]
TRACK=1.536
HUB_MASS=42
SPRING_RATE=30000
DAMP_BUMP=2200
DAMP_REBOUND=4840
DAMP_FAST_BUMP=1200
DAMP_FAST_BUMPTHRESHOLD=0.050
DAMP_FAST_REBOUND=3000
DAMP_FAST_REBOUNDTHRESHOLD=0.110
"""
CAR = "[BASIC]\nTOTALMASS=605\n[FUEL]\nFUEL=30\n[FUELTANK]\nPOSITION=0,0.00,0.300\n"
TYRES = "[FRONT]\nRATE=254810\n[REAR]\nRATE=329767\n"
SETUP = """
[SPRING_RATE_LF]
MIN=14
MAX=22
STEP=2
[SPRING_RATE_RF]
MIN=14
MAX=22
STEP=2
[DAMP_REBOUND_LR]
SHOW_CLICKS=2
MIN=2320
MAX=8200
STEP=840
[DAMP_REBOUND_RR]
SHOW_CLICKS=2
MIN=2320
MAX=8200
STEP=840
"""
FILES = {"suspensions.ini": SUSP, "car.ini": CAR, "tyres.ini": TYRES, "setup.ini": SETUP}


def test_setup_physical_clicks_and_kilo_units():
    from acd_reader import parse_ini
    setup = parse_ini(SETUP)
    assert setup_physical(setup, "DAMP_REBOUND_LR", "3", 4840) == 4840
    assert setup_physical(setup, "SPRING_RATE_LF", "20", 20000) == 20000
    assert setup_physical(setup, "SPRING_RATE_LF", None, 20000) == 20000


def test_damping_ratios_match_hand_calculation():
    r = damper_report(FILES, {"FUEL": "30", "DAMP_REBOUND_LR": "3", "DAMP_REBOUND_RR": "3"})
    front, rear = r["axles"]["FRONT"], r["axles"]["REAR"]
    assert abs(front["sprung_corner_kg"] - 84.2) < 0.2
    assert abs(front["zeta_ride_bump"] - 0.49) < 0.01
    assert abs(rear["zeta_ride_rebound"] - 1.15) < 0.01
    assert abs(r["roll_damping_front"] - 0.307) < 0.005
    assert any("rear rebound overdamped" in f for f in r["flags"])
    assert any("rear-biased" in f for f in r["flags"])


def test_softer_rear_rebound_clears_overdamped_flag():
    r = damper_report(FILES, {"FUEL": "30", "DAMP_REBOUND_LR": "1", "DAMP_REBOUND_RR": "1"})
    assert r["axles"]["REAR"]["zeta_ride_rebound"] < 0.8
    assert not any("rear rebound overdamped" in f for f in r["flags"])
    assert r["roll_damping_front"] > 0.35


def test_aero_detection_ignores_body_lift_but_sees_wings():
    from damper_model import is_aero_car
    lift = "[WING_1]\nNAME=FRONT\nCHORD=1\nSPAN=1.75\nCL_GAIN=1\nANGLE=1\nLUT_AOA_CL=f.lut\n"
    assert not is_aero_car({"aero.ini": lift, "f.lut": "0|0.04\n2|0.05\n"})
    assert is_aero_car({"aero.ini": lift, "f.lut": "0|0.40\n2|0.45\n"})
    assert is_aero_car({"setup.ini": "[WING_1]\nMIN=0\nMAX=10\n"})
    assert not is_aero_car(FILES)


class _F(object):
    def __init__(self, travel, load=(1000, 1000, 1000, 1000), speed=150.0):
        self.susp_travel = travel
        self.wheel_load = load
        self.speed_kmh = speed
        self.in_pit = False


def test_histogram_bins_bump_positive_and_skips_hitches():
    h = DamperHistogram()
    h.observe(_F((0.010, 0.010, 0.010, 0.010)), 0.01, "T1", "entry")
    h.observe(_F((0.011, 0.009, 0.010, 0.010), load=(0, 1000, 1000, 1000)), 0.01, "T1", "entry")
    h.observe(_F((0.050, 0.009, 0.010, 0.010)), 0.5, "T1", "entry")
    d = h.to_dict()
    assert d["frames"] == 1
    fl = wheel_stats(d["hist"]["entry"][0])
    fr = wheel_stats(d["hist"]["entry"][1])
    assert fl["bump_pct"] == 100.0 and fl["median"] > 0
    assert fr["rebound_pct"] == 100.0 and fr["median"] < 0
    assert d["unload_s"]["T1"][0] == 0.01


def test_merge_sums_laps():
    h = DamperHistogram()
    h.observe(_F((0.0, 0.0, 0.0, 0.0001)), 0.01, "", "mid")
    h.observe(_F((0.0, 0.0, 0.0, 0.0002)), 0.01, "", "mid")
    m = merge([h.to_dict(), h.to_dict(), {}])
    assert m["frames"] == 2
    assert sum(m["hist"]["mid"][3]) == 2 and len(m["hist"]["mid"][3]) == NBINS
