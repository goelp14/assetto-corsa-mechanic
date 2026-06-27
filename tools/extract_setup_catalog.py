#!/usr/bin/env python3
"""Extract RSS FH X 2026 setup lever catalog from data.acd setup.ini."""

from __future__ import print_function

import json
import os
import re
import sys

TIER_MAP = {
    "WING_0": "A", "WING_1": "A", "FRONT_BIAS": "A", "DIFF_PRELOAD": "A",
    "ARB_FRONT": "A", "ARB_REAR": "A",
    "CUSTOM_SCRIPT_ITEM_4": "A", "CUSTOM_SCRIPT_ITEM_5": "A",
    "CUSTOM_SCRIPT_ITEM_6": "A",
    "BRAKE_POWER_MULT": "B", "SPRING_RATE_LF": "B", "SPRING_RATE_RF": "B",
    "SPRING_RATE_LR": "B", "SPRING_RATE_RR": "B", "SPRING_RATE_HF": "B",
    "SPRING_RATE_HR": "B", "ROD_LENGTH_LF": "B", "ROD_LENGTH_RF": "B",
    "ROD_LENGTH_LR": "B", "ROD_LENGTH_RR": "B", "PACKER_RANGE_LF": "B",
    "PACKER_RANGE_RF": "B", "PACKER_RANGE_LR": "B", "PACKER_RANGE_RR": "B",
    "PACKER_RANGE_HF": "B", "PACKER_RANGE_HR": "B", "BUMPSTOP_HF": "B",
    "BUMPSTOP_HR": "B",
    "CAMBER_LF": "C", "CAMBER_RF": "C", "CAMBER_LR": "C", "CAMBER_RR": "C",
    "TOE_OUT_LF": "C", "TOE_OUT_RF": "C", "TOE_OUT_LR": "C", "TOE_OUT_RR": "C",
    "PRESSURE_LF": "C", "PRESSURE_RF": "C", "PRESSURE_LR": "C", "PRESSURE_RR": "C",
    "MGUK_DELIVERY": "D", "MGUK_RECOVERY": "D", "BRAKE_ENGINE": "D",
    "ENGINE_MAPS": "D",
    "CUSTOM_SCRIPT_ITEM_1": "D", "CUSTOM_SCRIPT_ITEM_2": "D",
    "CUSTOM_SCRIPT_ITEM_7": "D",
    "WING_11": None, "WING_12": None, "WING_13": None, "AEROMAP": None,
    "STEER_ASSIST": None, "FUEL": None, "TYRES": None,
}


def parse_setup_ini(text):
    sections = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith(";"):
            continue
        m = re.match(r"\[([^\]]+)\]", line)
        if m:
            current = m.group(1)
            sections[current] = {}
            continue
        if current and "=" in line:
            k, v = line.split("=", 1)
            sections[current][k.strip()] = v.strip()
    return sections


def section_to_lever(name, props):
    if name.startswith("__") or name in ("CAR", "ABOUT", "DISPLAY_METHOD", "GEARS"):
        return None
    if "EXT_CONTROLLER" in props and "MIN" not in props:
        return {
            "section": name,
            "name": props.get("EXT_CONTROLLER", name),
            "tab": "DRIVETRAIN",
            "tier": TIER_MAP.get(name, "B"),
            "ext_controller": props["EXT_CONTROLLER"],
        }
    if "MIN" not in props and "LUT" not in props:
        return None
    lever = {
        "section": name,
        "name": props.get("NAME", name),
        "tab": props.get("TAB", ""),
        "tier": TIER_MAP.get(name, "B"),
    }
    if "ID" in props:
        lever["id"] = props["ID"].strip()
    if "MIN" in props:
        lever["min"] = float(props["MIN"]) if "." in props["MIN"] else int(props["MIN"])
    if "MAX" in props:
        lever["max"] = float(props["MAX"]) if "." in props["MAX"] else int(props["MAX"])
    if "STEP" in props:
        lever["step"] = float(props["STEP"]) if "." in props["STEP"] else int(props["STEP"])
    if "DEFAULT" in props:
        lever["default"] = props["DEFAULT"]
    if "LUT" in props:
        lever["lut"] = props["LUT"]
    return lever


def main():
    acd_path = sys.argv[1] if len(sys.argv) > 1 else (
        "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa"
        "/content/cars/rss_formula_hybrid_x_2026/data.acd"
    )
    out_path = sys.argv[2] if len(sys.argv) > 2 else (
        os.path.join(os.path.dirname(__file__), "..", "ac_app", "config", "car_rss_fh_x_2026.json")
    )

    try:
        from acd import read_file
        setup_text = read_file(acd_path)["setup.ini"]
    except ImportError:
        tmp = os.path.join(os.path.dirname(__file__), "..", ".tmp_setup.ini")
        with open(tmp, "r", encoding="utf-8", errors="replace") as f:
            setup_text = f.read()

    parsed = parse_setup_ini(setup_text)
    levers = []
    id_map = {}
    for name, props in sorted(parsed.items()):
        lever = section_to_lever(name, props)
        if lever:
            levers.append(lever)
            if "id" in lever:
                id_map[lever["id"]] = name

    catalog = {
        "car_id": "rss_formula_hybrid_x_2026",
        "display_name": "RSS Formula Hybrid X 2026",
        "wheelbase_m": 3.65,
        "cg_to_front_axle_m": 1.65,
        "cg_to_rear_axle_m": 2.00,
        "understeer_gradient_K": 0.005,
        "max_yaw_rate_rad_s": 1.2,
        "custom_script_id_map": id_map,
        "levers": levers,
    }

    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)
        f.write("\n")
    print("Wrote %d levers to %s" % (len(levers), out_path))


if __name__ == "__main__":
    main()
