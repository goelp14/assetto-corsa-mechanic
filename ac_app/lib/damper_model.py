# ac_app/lib/damper_model.py
# Python 3.3 compatible — damper physics from Assetto Corsa car data.
#
# AC gives SPRING_RATE, ARB and DAMP_* as wheel rates (N/m, N*s/m at the contact patch), so damping
# ratios come straight from zeta = c / (2 * sqrt(k * m)) with no motion ratios.

import math

try:
    from acd_reader import parse_ini
except ImportError:
    from .acd_reader import parse_ini

FUEL_KG_PER_L = 0.75
AXLES = (("FRONT", ("LF", "RF")), ("REAR", ("LR", "RR")))

# Rule-of-thumb windows (slow-speed, body control). Starting points to test, not targets to hit.
ZETA_WINDOWS = {
    "mechanical": {"bump": (0.30, 0.70), "rebound": (0.50, 0.90), "hop": (0.15, 0.45)},
    "aero": {"bump": (0.50, 0.90), "rebound": (0.70, 1.30), "hop": (0.15, 0.45)},
}


def _f(d, key, default=0.0):
    try:
        return float(str(d.get(key, default)).split(",")[0])
    except (TypeError, ValueError):
        return default


def _series(a, b):
    return a * b / (a + b) if a > 0 and b > 0 else (a or b)


def is_aero_car(files):
    """Wing setup levers, or wings whose CL*area at their set angle adds up to real downforce."""
    try:
        from acd_reader import parse_lut
    except ImportError:
        from .acd_reader import parse_lut
    if any(name.startswith("WING_") for name in parse_ini(files.get("setup.ini", ""))):
        return True
    downforce = 0.0
    for name, w in parse_ini(files.get("aero.ini", "")).items():
        if not name.startswith("WING_") or _f(w, "CL_GAIN") <= 0:
            continue
        lut = parse_lut(files.get(w.get("LUT_AOA_CL", ""), ""))
        if not lut:
            continue
        angle = _f(w, "ANGLE")
        cl = min(lut, key=lambda p: abs(p[0] - angle))[1]
        downforce += max(0.0, cl * _f(w, "CHORD") * _f(w, "SPAN") * _f(w, "CL_GAIN"))
    return downforce >= 0.3


def setup_physical(setup_ini, section, saved, default):
    """Physical value of a setup item from the VALUE saved in a setup .ini (None -> car default)."""
    props = setup_ini.get(section)
    if props is None or saved is None:
        return default
    try:
        saved = float(saved)
    except (TypeError, ValueError):
        return default
    if str(props.get("SHOW_CLICKS", "0")).strip() == "2":
        value = _f(props, "MIN") + saved * (_f(props, "STEP", 1.0) or 1.0)
    else:
        value = saved
    # Some cars show rates in kN in the setup screen while suspensions.ini is in N.
    if default and value and default / value > 100.0:
        value *= 1000.0
    return value


def click_table(setup_ini, section, k_ride, k_roll, m_sprung):
    props = setup_ini.get(section)
    if not props or str(props.get("SHOW_CLICKS", "0")).strip() != "2":
        return []
    lo, hi, step = _f(props, "MIN"), _f(props, "MAX"), _f(props, "STEP", 1.0) or 1.0
    rows = []
    n = int(round((hi - lo) / step))
    for click in range(n + 1):
        c = lo + click * step
        rows.append({
            "click": click, "c": round(c, 0),
            "zeta_ride": round(c / (2.0 * math.sqrt(k_ride * m_sprung)), 2),
            "zeta_roll": round(c / (2.0 * math.sqrt(k_roll * m_sprung)), 2),
        })
    return rows


def damper_report(files, saved=None, has_aero=False):
    """files: {name: text} from read_car_data(); saved: {SECTION: VALUE} from a setup .ini."""
    saved = saved or {}
    susp = parse_ini(files.get("suspensions.ini", ""))
    car = parse_ini(files.get("car.ini", ""))
    tyres = parse_ini(files.get("tyres.ini", ""))
    setup = parse_ini(files.get("setup.ini", ""))

    basic = susp.get("BASIC", {})
    wb = _f(basic, "WHEELBASE", 2.5)
    front_frac = _f(basic, "CG_LOCATION", 0.5)
    mass = _f(car.get("BASIC", {}), "TOTALMASS", 1000.0)
    fuel_l = float(saved.get("FUEL", _f(car.get("FUEL", {}), "FUEL", 0.0)))
    tank = str(car.get("FUELTANK", {}).get("POSITION", "0,0,0")).split(",")
    try:
        tank_z = float(tank[2])
    except (IndexError, ValueError):
        tank_z = 0.0
    fuel_front = min(1.0, max(0.0, front_frac + tank_z / wb))
    fuel_kg = fuel_l * FUEL_KG_PER_L

    report = {"mass_kg": mass, "fuel_kg": round(fuel_kg, 1), "axles": {}}
    roll_k, roll_c = {}, {}
    for axle, (left, right) in AXLES:
        a = susp.get(axle, {})
        share = front_frac if axle == "FRONT" else 1.0 - front_frac
        fshare = fuel_front if axle == "FRONT" else 1.0 - fuel_front
        corner = (mass * share + fuel_kg * fshare) / 2.0
        m_u = _f(a, "HUB_MASS", 0.0)
        m_s = max(1.0, corner - m_u)

        def pick(prefix, default):
            vals = [setup_physical(setup, "%s_%s" % (prefix, side), saved.get("%s_%s" % (prefix, side)), default)
                    for side in (left, right)]
            return sum(vals) / 2.0

        k = pick("SPRING_RATE", _f(a, "SPRING_RATE"))
        arb = setup_physical(setup, "ARB_" + axle, saved.get("ARB_" + axle), _f(susp.get("ARB", {}), axle))
        kt = _f(tyres.get(axle, {}), "RATE", 0.0)
        bump = pick("DAMP_BUMP", _f(a, "DAMP_BUMP"))
        reb = pick("DAMP_REBOUND", _f(a, "DAMP_REBOUND"))
        k_ride = _series(k, kt)
        k_roll = _series(k + 2.0 * arb, kt)
        cc_ride = 2.0 * math.sqrt(k_ride * m_s)
        cc_roll = 2.0 * math.sqrt(k_roll * m_s)
        cc_hop = 2.0 * math.sqrt((k + kt) * m_u) if m_u > 0 and kt > 0 else 0.0
        track = _f(a, "TRACK", 1.5)
        roll_k[axle] = k_roll * track * track
        roll_c[axle] = (bump + reb) * track * track
        report["axles"][axle] = {
            "sprung_corner_kg": round(m_s, 1), "unsprung_kg": m_u,
            "wheel_rate": round(k, 0), "arb": round(arb, 0), "tyre_rate": round(kt, 0),
            "ride_hz": round(math.sqrt(k_ride / m_s) / (2.0 * math.pi), 2),
            "roll_hz": round(math.sqrt(k_roll / m_s) / (2.0 * math.pi), 2),
            "hop_hz": round(math.sqrt((k + kt) / m_u) / (2.0 * math.pi), 1) if m_u > 0 and kt > 0 else 0.0,
            "bump": round(bump, 0), "rebound": round(reb, 0),
            "rebound_to_bump": round(reb / bump, 2) if bump else 0.0,
            "zeta_ride_bump": round(bump / cc_ride, 2), "zeta_ride_rebound": round(reb / cc_ride, 2),
            "zeta_roll_bump": round(bump / cc_roll, 2), "zeta_roll_rebound": round(reb / cc_roll, 2),
            "zeta_hop_fast_bump": round(_f(a, "DAMP_FAST_BUMP", bump) / cc_hop, 2) if cc_hop else 0.0,
            "fast_bump": _f(a, "DAMP_FAST_BUMP"), "fast_rebound": _f(a, "DAMP_FAST_REBOUND"),
            "fast_bump_knee_mm_s": round(1000.0 * _f(a, "DAMP_FAST_BUMPTHRESHOLD"), 0),
            "fast_rebound_knee_mm_s": round(1000.0 * _f(a, "DAMP_FAST_REBOUNDTHRESHOLD"), 0),
            "clicks_bump": click_table(setup, "DAMP_BUMP_" + left, k_ride, k_roll, m_s),
            "clicks_rebound": click_table(setup, "DAMP_REBOUND_" + left, k_ride, k_roll, m_s),
        }
    tot_k = sum(roll_k.values()) or 1.0
    tot_c = sum(roll_c.values()) or 1.0
    report["roll_stiffness_front"] = round(roll_k.get("FRONT", 0.0) / tot_k, 3)
    report["roll_damping_front"] = round(roll_c.get("FRONT", 0.0) / tot_c, 3)
    report["flags"] = damper_flags(report, has_aero)
    return report


def damper_flags(report, has_aero=False):
    win = ZETA_WINDOWS["aero" if has_aero else "mechanical"]
    out = []
    for axle, a in sorted(report["axles"].items()):
        name = axle.lower()
        lo, hi = win["bump"]
        if a["zeta_ride_bump"] < lo:
            out.append("%s bump underdamped (zeta %.2f < %.2f): floaty, slow to settle after crests" % (name, a["zeta_ride_bump"], lo))
        elif a["zeta_ride_bump"] > hi:
            out.append("%s bump overdamped (zeta %.2f > %.2f): wheel can't rise over bumps/kerbs; harsh, skips" % (name, a["zeta_ride_bump"], hi))
        lo, hi = win["rebound"]
        if a["zeta_ride_rebound"] > hi:
            out.append("%s rebound overdamped (zeta %.2f > %.2f): wheel slow to drop into dips and over crests; "
                       "unloads, can pack down over repeated bumps" % (name, a["zeta_ride_rebound"], hi))
        elif a["zeta_ride_rebound"] < lo:
            out.append("%s rebound underdamped (zeta %.2f < %.2f): body bounces/oscillates after load changes" % (name, a["zeta_ride_rebound"], lo))
        if a["rebound_to_bump"] and a["rebound_to_bump"] < 1.0:
            out.append("%s rebound softer than bump (ratio %.2f): unusual; expect the body to jack up over bumps" % (name, a["rebound_to_bump"]))
    gap = report["roll_damping_front"] - report["roll_stiffness_front"]
    if gap < -0.08:
        out.append("transient load transfer is rear-biased (roll damping %.0f%% front vs roll stiffness %.0f%% front): "
                   "turn-in and direction changes load the rear tyres first -> rear steps out in transients, "
                   "settles mid-corner" % (100 * report["roll_damping_front"], 100 * report["roll_stiffness_front"]))
    elif gap > 0.08:
        out.append("transient load transfer is front-biased (roll damping %.0f%% front vs roll stiffness %.0f%% front): "
                   "lazy turn-in / transient understeer, better rear security" % (100 * report["roll_damping_front"], 100 * report["roll_stiffness_front"]))
    return out
