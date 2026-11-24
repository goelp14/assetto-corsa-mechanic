"""Which replay is ACC showing right now? (no input, no injection: logs + file metadata + broadcasting)

- ACC's Unreal log (``%LOCALAPPDATA%/AC2/Saved/Logs/AC2.log``) records each load:
  ``LogKsReplay: Replay loaded successfully`` (UTC timestamp), ``replay loading, playercarModel N``,
  the replay screen widget ``WDG_ReplayInGame``, and the track in ``RequestHotlapData(trackname=…)``.
- Windows updates a file's last-access time when ACC opens it (``fsutil behavior query
  disablelastaccess`` = system managed/enabled on this machine), so the .rpy whose last access equals
  the load time is the one loaded. The menu touches the whole list a few seconds earlier, so the
  closest match within a second wins.
- The broadcasting API confirms a replay is on screen right now (and gives its clock).
- Bundles record ``rpy_file`` per driver, which maps the replay to a Lap Studio bundle + driver.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sys
from typing import Optional

from external.acc_mechanic.acc_setup import acc_documents

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXPORTS = os.path.join(ROOT, "exports")
LOAD_RE = re.compile(r"^\[(\d{4})\.(\d\d)\.(\d\d)-(\d\d)\.(\d\d)\.(\d\d):(\d{3})\]\[\s*\d+\]LogKsReplay: Replay loaded successfully")
CAR_RE = re.compile(r"replay loading, playercarModel (\d+)")
TRACK_RE = re.compile(r"RequestHotlapData\(trackname=([^,]+),")
LEAVE_MARKERS = ("Remove WDG_ReplayInGame", "LogKsReplay: Replay unloaded", "Create WDG_MainMenu")


def ue_log_path() -> Optional[str]:
    cands = []
    if sys.platform == "win32":
        cands.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "AC2", "Saved", "Logs", "AC2.log"))
    else:
        cands += glob.glob("/mnt/c/Users/*/AppData/Local/AC2/Saved/Logs/AC2.log")
    cands = [c for c in cands if os.path.isfile(c)]
    return max(cands, key=os.path.getmtime) if cands else None


def last_load(log_path: str) -> Optional[dict]:
    """Most recent replay load in the log: {utc, car_model, track, still_in_replay}."""
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return None
    for i in range(len(lines) - 1, -1, -1):
        m = LOAD_RE.match(lines[i])
        if not m:
            continue
        y, mo, d, h, mi, s, ms = (int(x) for x in m.groups())
        when = dt.datetime(y, mo, d, h, mi, s, ms * 1000, tzinfo=dt.timezone.utc)
        car = track = None
        for j in range(max(0, i - 200), i + 1):
            cm = CAR_RE.search(lines[j])
            if cm:
                car = int(cm.group(1))
            tm = TRACK_RE.search(lines[j])
            if tm:
                track = tm.group(1)
        left = any(mk in ln for ln in lines[i + 1:] for mk in LEAVE_MARKERS)
        return {"utc": when.isoformat(), "ts": when.timestamp(), "car_model": car, "track": track,
                "still_in_replay": not left}
    return None


def loaded_file(load_ts: float, tol_s: float = 1.5) -> Optional[str]:
    docs = acc_documents()
    if not docs:
        return None
    best, best_dt = None, tol_s
    for p in glob.glob(os.path.join(docs, "Replay", "Saved", "*.rpy")):
        try:
            d = abs(os.stat(p).st_atime - load_ts)
        except OSError:
            continue
        if d <= best_dt:
            best, best_dt = p, d
    return best


def bundle_for(rpy_name: str) -> Optional[dict]:
    for mf in glob.glob(os.path.join(EXPORTS, "*", "manifest.json")):
        try:
            with open(mf, encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        for d in m.get("drivers", []):
            if (d.get("rpy_file") or "").lower() == rpy_name.lower():
                return {"bundle": os.path.basename(os.path.dirname(mf)), "driver": d["label"],
                        "best_lap_index": d.get("best_lap_index")}
    return None


def detect(broadcast=None) -> dict:
    """{in_replay, file, bundle, driver, best_lap_index, track, car_model, loaded_utc, replay_remaining_s}."""
    out = {"in_replay": False, "file": None, "bundle": None, "driver": None}
    log = ue_log_path()
    ld = last_load(log) if log else None
    if ld:
        out.update({"loaded_utc": ld["utc"], "track": ld["track"], "car_model": ld["car_model"]})
        rpy = loaded_file(ld["ts"])
        if rpy:
            out["file"] = os.path.basename(rpy)
            try:
                from .acc_capture_session import staged_map
                original = staged_map().get(out["file"], out["file"])
            except Exception:
                original = out["file"]
            b = bundle_for(original)
            if b:
                out.update(b)
        out["in_replay"] = ld["still_in_replay"]
    if broadcast is not None:
        rt = broadcast.snapshot().realtime
        out["acc_connected"] = rt is not None
        if rt is not None:                      # live truth beats the log
            out["in_replay"] = bool(rt.replay)
            out["replay_remaining_s"] = rt.replay_remaining_s
    return out


if __name__ == "__main__":
    print(json.dumps(detect(), indent=1))
