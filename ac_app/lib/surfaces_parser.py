# ac_app/lib/surfaces_parser.py
# Optional surfaces.ini → approximate kerb/grass bands along spline (visual hint).

import re


def parse_surfaces_ini(path):
    """Return list of {name, grip, spline_start, spline_end} bands if file exists."""
    if not path or not __import__("os").path.isfile(path):
        return []
    zones = []
    current = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                if current:
                    zones.append(current)
                current = {"name": line[1:-1], "grip": 1.0}
            elif current and "=" in line:
                key, val = line.split("=", 1)
                key = key.strip().upper()
                val = val.strip()
                if key == "WAV":
                    try:
                        current["grip"] = float(val)
                    except ValueError:
                        pass
    if current:
        zones.append(current)
    # Without spline mapping in surfaces.ini, return type list for viewer legend
    return [{"name": z["name"], "grip": z.get("grip", 1.0), "hint": True} for z in zones]
