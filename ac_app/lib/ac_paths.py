# ac_app/lib/ac_paths.py
# Python 3.3 compatible — resolve Assetto Corsa user folders across Documents layouts.

import os

DEFAULT_CAR_ID = "rss_formula_hybrid_x_2026"
_AC_USERDATA = None
_CAR_SETUPS_ROOT = {}


def _unique_paths(paths):
    seen = set()
    out = []
    for path in paths:
        if not path:
            continue
        norm = os.path.normpath(path)
        key = norm.lower() if os.name == "nt" else norm
        if key in seen:
            continue
        seen.add(key)
        out.append(norm)
    return out


def candidate_ac_userdata_dirs():
    """Ordered search paths for the Assetto Corsa user data folder."""
    home = os.path.expanduser("~")
    paths = []

    for key in ("AC_USERDATA", "ASSETTOCORSA_USERDATA", "VRE_AC_USERDATA"):
        val = os.environ.get(key, "").strip()
        if val:
            paths.append(val)

    for key in ("ONEDRIVE", "ONEDRIVECOMMERCIAL"):
        root = os.environ.get(key, "").strip()
        if root:
            paths.append(os.path.join(root, "Documents", "Assetto Corsa"))
            paths.append(os.path.join(root, "Assetto Corsa"))

    if home:
        paths.append(os.path.join(home, "Documents", "Assetto Corsa"))
        paths.append(os.path.join(home, "OneDrive", "Documents", "Assetto Corsa"))
        paths.append(os.path.join(home, "OneDrive", "Assetto Corsa"))
        try:
            for name in os.listdir(home):
                low = name.lower()
                if low.startswith("onedrive") and low != "onedrive":
                    paths.append(os.path.join(
                        home, name, "Documents", "Assetto Corsa",
                    ))
        except OSError:
            pass

    return _unique_paths(paths)


def _looks_like_ac_userdata(path):
    if not path or not os.path.isdir(path):
        return False
    setups = os.path.join(path, "setups")
    if os.path.isdir(setups):
        return True
    for marker in ("cfg", "logs", "templates"):
        if os.path.isdir(os.path.join(path, marker)):
            return True
    return False


def resolve_ac_userdata_dir(refresh=False):
    global _AC_USERDATA
    if _AC_USERDATA and not refresh and os.path.isdir(_AC_USERDATA):
        return _AC_USERDATA

    best = None
    best_score = -1
    for path in candidate_ac_userdata_dirs():
        if not _looks_like_ac_userdata(path):
            continue
        score = 0
        setups = os.path.join(path, "setups")
        if os.path.isdir(setups):
            score += 10
            car_root = os.path.join(setups, DEFAULT_CAR_ID)
            if os.path.isdir(car_root):
                score += 20
                try:
                    score += min(len(os.listdir(car_root)), 5)
                except OSError:
                    pass
        if score > best_score:
            best_score = score
            best = path

    _AC_USERDATA = best
    return best


def enumerate_car_setups_roots(car_id=None):
    """All existing car setup roots, best match first."""
    car_id = car_id or DEFAULT_CAR_ID
    roots = []
    seen = set()

    def add(root, score):
        if not root:
            return
        norm = os.path.normpath(root)
        key = norm.lower() if os.name == "nt" else norm
        if key in seen or not os.path.isdir(norm):
            return
        seen.add(key)
        roots.append((score, norm))

    userdata = resolve_ac_userdata_dir(refresh=True)
    if userdata:
        add(os.path.join(userdata, "setups", car_id), 100)

    for userdata_path in candidate_ac_userdata_dirs():
        add(os.path.join(userdata_path, "setups", car_id), 50)

    home = os.path.expanduser("~")
    add(os.path.join(home, "Documents", "Assetto Corsa", "setups", car_id), 10)
    add(os.path.join(home, "OneDrive", "Documents", "Assetto Corsa", "setups", car_id), 20)

    roots.sort(key=lambda item: item[0], reverse=True)
    return [root for score, root in roots]


def resolve_car_setups_root(car_id=None, refresh=False):
    car_id = car_id or DEFAULT_CAR_ID
    if not refresh:
        cached = _CAR_SETUPS_ROOT.get(car_id)
        if cached and os.path.isdir(cached):
            return cached

    roots = enumerate_car_setups_roots(car_id)
    root = roots[0] if roots else os.path.join(
        os.path.expanduser("~"), "Documents", "Assetto Corsa", "setups", car_id,
    )
    _CAR_SETUPS_ROOT[car_id] = root
    return root


def resolve_track_setup_folder(track_name, track_cfg=None, car_id=None):
    """Return track setup subfolder name (e.g. monaco_2020) under car setups."""
    car_id = car_id or DEFAULT_CAR_ID
    preferred = track_cfg.get("setup_folder", "") if track_cfg else ""

    for setups_root in enumerate_car_setups_roots(car_id):
        if preferred and os.path.isdir(os.path.join(setups_root, preferred)):
            _CAR_SETUPS_ROOT[car_id] = setups_root
            return preferred
        tn = (track_name or "").lower()
        try:
            names = os.listdir(setups_root)
        except OSError:
            continue
        for name in names:
            folder = os.path.join(setups_root, name)
            if not os.path.isdir(folder):
                continue
            low = name.lower()
            if low == tn or tn in low or low in tn:
                _CAR_SETUPS_ROOT[car_id] = setups_root
                return name
        generic = os.path.join(setups_root, "generic")
        if os.path.isdir(generic):
            _CAR_SETUPS_ROOT[car_id] = setups_root
            return "generic"

    return "generic"


def probe_setup_paths(track_folder, car_id=None):
    """Diagnostic snapshot for archive logging."""
    car_id = car_id or DEFAULT_CAR_ID
    roots = enumerate_car_setups_roots(car_id)
    userdata = resolve_ac_userdata_dir(refresh=True)
    out = {
        "userdata_dir": userdata or "",
        "car_id": car_id,
        "track_folder": track_folder,
        "setups_roots": roots,
        "candidates": candidate_ac_userdata_dirs()[:8],
    }
    for root in roots:
        folder = os.path.join(root, track_folder)
        generic = os.path.join(root, "generic")
        target = folder if os.path.isdir(folder) else (
            generic if os.path.isdir(generic) else ""
        )
        entry = {"root": root, "folder": target, "exists": bool(target)}
        if target:
            try:
                entry["ini_files"] = [
                    name for name in os.listdir(target)
                    if name.lower().endswith(".ini")
                ]
            except OSError as exc:
                entry["listdir_error"] = str(exc)
        out.setdefault("track_dirs", []).append(entry)
    return out


def reset_path_cache():
    global _AC_USERDATA
    _AC_USERDATA = None
    _CAR_SETUPS_ROOT.clear()
