# ac_app/lib/car_profile.py
# Python 3.3 compatible — derive a VRE car profile (setup levers, physics, tyre window)
# from Assetto Corsa car data files.

try:
    from acd_reader import parse_ini, parse_lut
except ImportError:
    from .acd_reader import parse_ini, parse_lut

SKIP_SECTIONS = frozenset(("CAR", "ABOUT", "DISPLAY_METHOD", "GEARS", "HEADER"))

TIER_BY_ID = {
    "DIFF_ENTRY": "A", "DIFF_MID": "A", "DIFF_EXIT": "A",
    "BRAKE_MIGRATION": "D", "BMIG_RAMP": "D", "DIFF_HISPD_SWITCH": "D",
}

TIER_PREFIXES = (
    (("AEROMAP", "STEER_ASSIST", "FUEL", "TYRES", "ENGINE_LIMITER"), None),
    (("WING_", "ARB_", "FRONT_BIAS", "DIFF_"), "A"),
    (("SPRING_", "ROD_LENGTH", "DAMP_", "PACKER_", "BUMPSTOP", "BRAKE_POWER"), "B"),
    (("CAMBER_", "TOE_", "PRESSURE_"), "C"),
    (("MGUK_", "MGUH_", "ENGINE_", "BRAKE_ENGINE", "CUSTOM_SCRIPT"), "D"),
)

DEFAULT_PHYSICS = {
    "understeer_gradient_K": 0.005,
    "max_yaw_rate_rad_s": 1.2,
}


def _num(text):
    text = str(text).strip()
    try:
        return int(text)
    except ValueError:
        return float(text)


_NON_WING_LABELS = ("body", "lift", "null", "anim", "throttle", "brake", "halo", "style")


def has_downforce(aero):
    """True when aero.ini has an active lifting surface other than the body."""
    for name, props in aero.items():
        if not name.startswith("WING_"):
            continue
        label = props.get("NAME", "").lower()
        if any(word in label for word in _NON_WING_LABELS):
            continue
        try:
            gain = float(props.get("CL_GAIN", "0"))
        except ValueError:
            gain = 0.0
        if gain > 0:
            return True
    return False


def lever_tier(section, lever_id=None):
    if lever_id in TIER_BY_ID:
        return TIER_BY_ID[lever_id]
    if section.startswith("WING_") and len(section) > 6:
        return None
    for prefixes, tier in TIER_PREFIXES:
        for p in prefixes:
            if section == p or section.startswith(p):
                return tier
    return "B"


def section_to_lever(name, props, lut_sizes=None):
    """Express a setup.ini item in the units AC writes to setup .ini VALUE= lines.

    SHOW_CLICKS=2 items are saved as click indexes, camber as tenths of a degree,
    LUT items as a row index, everything else as the physical value.
    """
    if name.startswith("__") or name in SKIP_SECTIONS:
        return None
    lever_id = props.get("ID", "").strip() or None
    if "EXT_CONTROLLER" in props and "MIN" not in props:
        return {
            "section": name, "name": props.get("EXT_CONTROLLER", name),
            "tab": "DRIVETRAIN", "tier": lever_tier(name, lever_id),
            "ext_controller": props["EXT_CONTROLLER"],
        }
    if "MIN" not in props:
        if "LUT" not in props:
            return None
        lever = {
            "section": name, "name": props.get("NAME", name),
            "tab": props.get("TAB", ""), "tier": lever_tier(name, lever_id),
            "encoding": "index", "lut": props["LUT"],
        }
        rows = (lut_sizes or {}).get(props["LUT"])
        if rows:
            lever.update({"min": 0, "max": rows - 1, "step": 1})
        if lever_id:
            lever["id"] = lever_id
        if "DEFAULT" in props:
            lever["default"] = props["DEFAULT"]
        return lever

    lo, hi = _num(props["MIN"]), _num(props.get("MAX", props["MIN"]))
    step = _num(props.get("STEP", 1)) or 1
    lever = {
        "section": name, "name": props.get("NAME", name),
        "tab": props.get("TAB", ""), "tier": lever_tier(name, lever_id),
    }
    if lever_id:
        lever["id"] = lever_id
    if props.get("SHOW_CLICKS", "0").strip() == "2":
        lever.update({
            "encoding": "clicks", "min": 0, "max": int(round((hi - lo) / float(step))), "step": 1,
            "phys_min": lo, "phys_step": step,
        })
    elif name.startswith("CAMBER_"):
        lever.update({
            "encoding": "tenths", "min": int(round(lo * 10)), "max": int(round(hi * 10)),
            "step": step,
        })
    else:
        lever.update({"encoding": "raw", "min": lo, "max": hi, "step": step})
    if "DEFAULT" in props:
        lever["default"] = props["DEFAULT"]
    return lever


def tyre_window_from_curve(points, ideal_level=0.995, edge_level=0.98):
    """Ideal band = temps with grip >= ideal_level; cold/hot = where grip falls below edge_level."""
    if len(points) < 2:
        return {}
    ideal = [x for x, y in points if y >= ideal_level]
    if not ideal:
        return {}
    lo, hi = min(ideal), max(ideal)

    def crossing(seq):
        prev = None
        for x, y in seq:
            if prev is not None and y < edge_level <= prev[1]:
                x0, y0 = prev
                return x0 + (edge_level - y0) * (x - x0) / (y - y0)
            prev = (x, y)
        return None

    cold = crossing([p for p in reversed(points) if p[0] <= lo])
    hot = crossing([p for p in points if p[0] >= hi])
    return {
        "core_temp_ideal_min_c": float(lo),
        "core_temp_ideal_max_c": float(hi),
        "core_temp_cold_c": round(cold if cold is not None else lo - 10.0, 1),
        "core_temp_hot_c": round(hot if hot is not None else hi + 10.0, 1),
    }


def build_car_profile(car_id, files):
    """files: {filename: text} from read_car_data()."""
    car_ini = parse_ini(files.get("car.ini", ""))
    susp = parse_ini(files.get("suspensions.ini", ""))
    tyres = parse_ini(files.get("tyres.ini", ""))
    setup = parse_ini(files.get("setup.ini", ""))

    profile = {
        "car_id": car_id,
        "display_name": car_ini.get("INFO", {}).get("SCREEN_NAME", car_id),
    }
    profile.update(DEFAULT_PHYSICS)
    basic = susp.get("BASIC", {})
    if "WHEELBASE" in basic:
        wb = float(basic["WHEELBASE"])
        front = float(basic.get("CG_LOCATION", 0.5))
        profile["wheelbase_m"] = round(wb, 3)
        profile["front_weight_frac"] = round(front, 3)
        profile["cg_to_front_axle_m"] = round((1.0 - front) * wb, 3)
        profile["cg_to_rear_axle_m"] = round(front * wb, 3)
    if "TOTALMASS" in car_ini.get("BASIC", {}):
        profile["mass_kg"] = float(car_ini["BASIC"]["TOTALMASS"])
    controls = car_ini.get("CONTROLS", {})
    try:
        lock = float(controls["STEER_LOCK"])
        ratio = float(controls["STEER_RATIO"])
        if ratio > 0:
            profile["max_road_wheel_deg"] = round(lock / ratio, 2)
    except (KeyError, ValueError):
        pass
    profile["lat_g_base"] = 1.5
    profile["lat_g_per_ms"] = round(1.0 / 30.0, 4) if has_downforce(
        parse_ini(files.get("aero.ini", ""))) else 0.0

    by_compound = {}
    for suffix in [""] + ["_%d" % i for i in range(1, 10)]:
        front = tyres.get("FRONT" + suffix)
        curve_name = tyres.get("THERMAL_FRONT" + suffix, {}).get("PERFORMANCE_CURVE", "")
        if front is None or curve_name not in files:
            continue
        window = tyre_window_from_curve(parse_lut(files[curve_name]))
        if not window:
            continue
        if not suffix:
            profile["tyre_window"] = window
        for key in (front.get("NAME", ""), front.get("SHORT_NAME", "")):
            if key:
                by_compound[key.strip().lower()] = window
    if by_compound:
        profile["tyre_windows_by_compound"] = by_compound
    pressures = {}
    for axle in ("FRONT", "REAR"):
        if "PRESSURE_IDEAL" in tyres.get(axle, {}):
            pressures[axle.lower()] = float(tyres[axle]["PRESSURE_IDEAL"])
    if pressures:
        profile["pressure_ideal_psi"] = pressures

    lut_sizes = {}
    for fname, text in files.items():
        if fname.lower().endswith(".lut"):
            lut_sizes[fname] = len([ln for ln in text.splitlines() if "|" in ln.split(";", 1)[0]])
    levers = []
    id_map = {}
    for name in sorted(setup):
        lever = section_to_lever(name, setup[name], lut_sizes)
        if lever:
            levers.append(lever)
            if "id" in lever:
                id_map[lever["id"]] = name
    profile["custom_script_id_map"] = id_map
    profile["levers"] = levers
    return profile
