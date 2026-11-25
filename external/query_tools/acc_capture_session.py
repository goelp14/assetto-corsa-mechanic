"""One-button capture session: both replays of a bundle, full lap + trouble spots from several angles.

Flow (everything after the button is automatic except loading each replay in ACC):
  1. Stage: copy each driver's .rpy into ACC's Replay/Saved as "00 VRE <n> - <label> - <track>.rpy" so it
     sits at the top of ACC's replay list (originals are never touched; copies are deleted at the end).
  2. Plan: trouble spots = corners from the coaching fixes, then the biggest time losses (up to ``max_spots``),
     each from ~70 m before the braking point to 230 m past the apex.
  3. For each driver: wait until ACC shows that replay (ACC log + file access time), then record
     - the full fastest lap from the Dash camera,
     - every trouble spot from each angle in ``angles`` (ACC jumps there itself via UE4SS).
  4. Clean up the staged copies, put the camera back on Dash.

Videos land in the bundle's videos.json with ``kind`` = "full" | "angle", ``corner``, ``camera``.
"""

from __future__ import annotations

import bisect
import json
import os
import shutil
import threading
import time
from typing import Dict, List, Optional

from external.acc_mechanic.acc_setup import acc_documents

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXPORTS = os.path.join(ROOT, "exports")
STAGING = os.path.join(ROOT, "data", "acc_session_staging.json")
DEFAULT_ANGLES = ["Drivable/Chase", "Helicam/Helicam", "set1", "Drivable/Bonnet"]
ANGLE_NAMES = {"Drivable/Chase": "Chase", "Helicam/Helicam": "Helicam", "set1": "TV", "Drivable/Bonnet": "Bonnet",
               "Drivable/Dash": "Dash", "Drivable/FarChase": "Far chase", "Onboard/Onboard0": "Onboard"}


# ------------------------------------------------------------------ staging (copies at the top of ACC's list)

def staged_map() -> Dict[str, str]:
    """staged copy name -> original .rpy name."""
    try:
        with open(STAGING, encoding="utf-8") as fh:
            return json.load(fh).get("copies", {})
    except (OSError, ValueError):
        return {}


def stage(bundle: str) -> List[dict]:
    docs = acc_documents()
    if not docs:
        raise FileNotFoundError("ACC documents folder not found")
    saved = os.path.join(docs, "Replay", "Saved")
    with open(os.path.join(EXPORTS, bundle, "manifest.json"), encoding="utf-8") as fh:
        m = json.load(fh)
    copies, out = staged_map(), []
    for n, d in enumerate(m["drivers"], 1):
        src = os.path.join(saved, d.get("rpy_file") or "")
        if not d.get("rpy_file") or not os.path.isfile(src):
            raise FileNotFoundError("%s's replay %s is not in ACC's Replay/Saved" % (d["label"], d.get("rpy_file")))
        name = "00 VRE %d - %s - %s.rpy" % (n, d["label"], m.get("track_id", "track"))
        dst = os.path.join(saved, name)
        shutil.copyfile(src, dst)          # new modified time too, so it also sorts first by date
        copies[name] = d["rpy_file"]
        out.append({"driver": d["label"], "staged": name[:-4], "original": d["rpy_file"]})
    os.makedirs(os.path.dirname(STAGING), exist_ok=True)
    with open(STAGING, "w", encoding="utf-8") as fh:
        json.dump({"copies": copies, "saved": saved}, fh, indent=1)
    return out


def unstage() -> int:
    try:
        with open(STAGING, encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        return 0
    n = 0
    for name in st.get("copies", {}):
        p = os.path.join(st.get("saved", ""), name)
        if os.path.basename(p).startswith("00 VRE ") and os.path.isfile(p):
            os.remove(p)
            n += 1
    os.remove(STAGING)
    return n


def _cam_key(v: dict) -> str:
    cam = v.get("camera") or ""
    return "set1" if v.get("kind") == "angle" and cam.startswith("set") else cam


def _existing(bundle: str, d: dict) -> list:
    """Recordings usable for this driver's current fastest lap from the same replay:
    [(kind, camera, s0_m, s1_m)] (track span covered; full laps cover everything)."""
    try:
        with open(os.path.join(EXPORTS, bundle, "videos.json"), encoding="utf-8") as fh:
            vids = json.load(fh).get("videos", [])
    except (OSError, ValueError):
        return []
    out = []
    for v in vids:
        if v.get("tool") != "vre" or v.get("driver") != d["label"] or v.get("rpy_file") != d.get("rpy_file"):
            continue
        if not v.get("file") or not os.path.isfile(v["file"]):
            continue
        lap = next((l for l in v.get("laps", []) if l.get("lap_index") == d.get("best_lap_index")), None)
        if lap is None or (v.get("kind", "full") == "full" and not lap.get("complete")):
            continue
        out.append((v.get("kind", "full"), _cam_key(v), v.get("s0_m"), v.get("s1_m")))
    return out


def _has(have: list, p: dict, tol_m: float = 5.0) -> bool:
    """True when an existing recording covers this pass: same kind and camera, and (for corner clips) a track
    span that contains the planned one — so a longer 'La Source → Eau Rouge' clip covers a 'La Source' pass."""
    cam = _cam_key(p)
    for kind, c, s0, s1 in have:
        if kind != p["kind"] or c != cam:
            continue
        if kind == "full":
            return True
        if None not in (s0, s1, p.get("s0_m"), p.get("s1_m")) and s0 <= p["s0_m"] + tol_m and s1 >= p["s1_m"] - tol_m:
            return True
    return False


def adopt_shared(bundle: str, exports: Optional[str] = None) -> int:
    """Copy into this bundle any recording another bundle made of the *same replay lap* (same rpy file, same lap,
    still each driver's fastest here) — e.g. the reference driver's footage when only your replay changed.
    Files are shared, not duplicated; the pruner never deletes a file another bundle still lists."""
    root = exports or EXPORTS
    bdir = os.path.join(root, bundle)
    try:
        with open(os.path.join(bdir, "manifest.json"), encoding="utf-8") as fh:
            drivers = {d["label"]: d for d in json.load(fh).get("drivers", [])}
    except (OSError, ValueError):
        return 0
    vpath = os.path.join(bdir, "videos.json")
    try:
        with open(vpath, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        doc = {"videos": []}
    have_ids = {v.get("id") for v in doc.get("videos", [])}
    have_files = {v.get("file") for v in doc.get("videos", [])}
    added = 0
    for other in sorted(os.listdir(root)):
        if other == bundle:
            continue
        try:
            with open(os.path.join(root, other, "videos.json"), encoding="utf-8") as fh:
                vids = json.load(fh).get("videos", [])
        except (OSError, ValueError):
            continue
        for v in vids:
            d = drivers.get(v.get("driver"))
            if (d is None or v.get("tool") != "vre" or v.get("rpy_file") != d.get("rpy_file")
                    or v.get("id") in have_ids or v.get("file") in have_files
                    or not v.get("file") or not os.path.isfile(v["file"])
                    or not any(l.get("lap_index") == d.get("best_lap_index") for l in v.get("laps", []))):
                continue
            doc.setdefault("videos", []).append(dict(v, shared_from=other))
            have_ids.add(v.get("id"))
            have_files.add(v.get("file"))
            src = os.path.join(root, other, "video_%s_samples.json" % v.get("id"))
            if os.path.isfile(src):
                import shutil
                shutil.copyfile(src, os.path.join(bdir, os.path.basename(src)))
            added += 1
    if added:
        doc["videos"] = sorted(doc["videos"], key=lambda x: x.get("recorded", ""))
        with open(vpath, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
    return added


def _describe(d: dict) -> str:
    import re as _re
    m = _re.search(r"_(\d{2})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})_", d.get("rpy_file") or "")
    when = "20%s-%s-%s %s:%s" % (m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)) if m else "?"
    ident = d.get("identity") or {}
    return "%s · %s · recorded %s" % (ident.get("track", "?"), ident.get("car", "?"), when)


# ------------------------------------------------------------------ plan

MIN_LOSS_S = 0.15          # ignore corners losing less than this to the reference
MAX_CORNERS = 4            # at most this many corners get extra angles
PASS_OVERHEAD_S = 7.5      # measured cost of a separate clip (seek, run-in, OBS start/stop, checks)


def _corner_extent(an: dict, w: dict) -> tuple:
    """The whole corner for both drivers: 50 m before the first brake / turn-in point to 150 m after the later
    of the slowest point and full throttle (exit + traction, where exit-speed problems show)."""
    starts, ends = [], []
    for drv in an.get("drivers", {}).values():
        ev = (drv.get("corners", {}).get("%s#%s" % (w["corner"], w["index"])) or {}).get("best_lap") or {}
        for k in ("brake_on_m", "turn_in_m"):
            if ev.get(k) is not None:
                starts.append(ev[k])
        for k in ("vmin_m", "full_throttle_m"):
            if ev.get(k) is not None:
                ends.append(ev[k])
    s0 = (min(starts) if starts else w["apex_m"] - 150) - 50
    s1 = (max(ends) if ends else w["apex_m"]) + 150
    return round(max(0.0, s0), 1), round(max(s1, s0 + 120), 1)


def trouble_spots(bundle: str, max_spots: int = MAX_CORNERS, min_loss_s: float = MIN_LOSS_S) -> List[dict]:
    """Where to record extra angles — decided from the telemetry alone, before ACC is touched.

    1. Corners ranked by time lost to the reference on the fastest laps (analysis ``corner_loss_best_vs_ref``,
       from the lap-time delta); keep those losing ≥ ``min_loss_s``, at most ``max_spots``.
    2. Each clip is the whole corner for both drivers (``_corner_extent``): approach/braking, turn-in, apex
       and exit/traction — the cause of a loss is often before or after where the time is lost.
    3. Clips are merged when the lap time between them is shorter than a separate pass costs
       (``PASS_OVERHEAD_S``): recording straight through is then cheaper than seeking again.
    """
    bdir = os.path.join(EXPORTS, bundle)
    with open(os.path.join(bdir, "analysis.json"), encoding="utf-8") as fh:
        an = json.load(fh)
    with open(os.path.join(bdir, "manifest.json"), encoding="utf-8") as fh:
        m = json.load(fh)
    losses = sorted((c for c in an.get("corner_loss_best_vs_ref", []) if (c.get("loss_s") or 0) >= min_loss_s),
                    key=lambda c: -c["loss_s"])[:max_spots]
    picks = []
    for c in losses:
        w = next((x for x in an["windows"] if x["corner"] == c["corner"]), None)
        if w is None:
            continue
        s0, s1 = _corner_extent(an, w)
        picks.append({"corners": [c["corner"]], "s0_m": s0, "s1_m": s1, "loss_s": round(c["loss_s"], 3)})
    if not picks:
        return []
    # lap time along the first driver's fastest lap decides whether two clips are "close"
    me = m["drivers"][0]
    lap = next(l for l in me["laps"] if l["lap_index"] == me["best_lap_index"])
    with open(os.path.join(bdir, lap["frames"]), encoding="utf-8") as fh:
        fr = json.load(fh)
    picks.sort(key=lambda p: p["s0_m"])
    merged = [dict(picks[0])]
    for p in picks[1:]:
        cur = merged[-1]
        gap_s = _lap_time_at(fr, p["s0_m"]) - _lap_time_at(fr, cur["s1_m"])
        if gap_s < PASS_OVERHEAD_S:
            cur["corners"] = cur["corners"] + p["corners"]
            cur["s1_m"] = max(cur["s1_m"], p["s1_m"])
            cur["loss_s"] = round(cur["loss_s"] + p["loss_s"], 3)
        else:
            merged.append(dict(p))
    for sp in merged:
        sp["corner"] = " → ".join(sp["corners"])
        sp["lap_s"] = [round(_lap_time_at(fr, sp["s0_m"]), 1), round(_lap_time_at(fr, sp["s1_m"]), 1)]
    return merged


def capture_plan(bundle: str, angles: Optional[List[str]] = None) -> dict:
    """What a capture run will record and why (shown in Lap Studio before starting)."""
    angles = angles or list(DEFAULT_ANGLES)
    an_path = os.path.join(EXPORTS, bundle, "analysis.json")
    with open(an_path, encoding="utf-8") as fh:
        an = json.load(fh)
    spots = trouble_spots(bundle)
    gap = None
    with open(os.path.join(EXPORTS, bundle, "manifest.json"), encoding="utf-8") as fh:
        m = json.load(fh)
    if len(m["drivers"]) > 1:
        bl = [next(l["lap_ms"] for l in d["laps"] if l["lap_index"] == d["best_lap_index"]) for d in m["drivers"][:2]]
        gap = round((bl[0] - bl[1]) / 1000.0, 3)
    return {
        "drivers": [{"label": d["label"], "lap": d["best_lap_index"]} for d in m["drivers"]],
        "segments": [{"label": sp["corner"], "corners": sp["corners"], "loss_s": sp["loss_s"], "lap_s": sp["lap_s"]}
                     for sp in spots],
        "cameras": [ANGLE_NAMES.get(c, c) for c in angles],
        "loss_covered_s": round(sum(sp["loss_s"] for sp in spots), 3),
        "gap_s": gap,
        "passes": len(m["drivers"]) * (1 + len(spots) * len(angles)),
        "rule": "corners losing ≥ %.2f s (max %d), merged when closer than a separate pass costs (%.1f s)"
                % (MIN_LOSS_S, MAX_CORNERS, PASS_OVERHEAD_S),
    }


def _lap_time_at(frames: dict, s: float) -> float:
    ss, tt = frames["s_m"], frames["t"]
    i = max(1, min(len(ss) - 1, bisect.bisect_left(ss, s)))
    a, b = ss[i - 1], ss[i]
    return tt[i - 1] + (s - a) * (tt[i] - tt[i - 1]) / (b - a) if b != a else tt[i]


def driver_plan(bundle: str, driver: dict, spots: List[dict], angles: List[str]) -> List[dict]:
    """Passes for one driver's replay, on that replay's clock."""
    bdir = os.path.join(EXPORTS, bundle)
    lap = next(l for l in driver["laps"] if l["lap_index"] == driver["best_lap_index"])
    with open(os.path.join(bdir, lap["frames"]), encoding="utf-8") as fh:
        fr = json.load(fh)
    passes = [{"kind": "full", "lap": lap["lap_index"], "camera": "Drivable/Dash", "label": "Full lap · Dash"}]
    for sp in spots:
        t0 = lap["start_s"] + _lap_time_at(fr, sp["s0_m"])
        t1 = lap["start_s"] + _lap_time_at(fr, sp["s1_m"])
        for cam in angles:
            passes.append({"kind": "angle", "lap": lap["lap_index"], "corner": sp["corner"], "camera": cam,
                           "window": [round(t0, 2), round(t1, 2)], "s0_m": sp["s0_m"], "s1_m": sp["s1_m"],
                           "label": "%s · %s" % (sp["corner"], ANGLE_NAMES.get(cam, cam))})
    return passes


# ------------------------------------------------------------------ runner

class Session:
    def __init__(self, bundle: str, angles: Optional[List[str]] = None, max_spots: int = MAX_CORNERS, log=print,
                 force: bool = False):
        self.bundle = bundle
        self.angles = angles or list(DEFAULT_ANGLES)
        self.max_spots = max_spots
        self.log_fn = log
        self.state = "idle"
        self.prompt = ""
        self.steps: List[dict] = []
        self.error = ""
        self.logs: List[str] = []
        self._stop = threading.Event()
        self._cap = None
        self.force = force          # re-record everything (older copies are pruned afterwards)

    def log(self, msg):
        self.logs.append(msg)
        del self.logs[:-30]
        self.log_fn(msg)

    # measured on a full Spa run (26 passes): full lap = lap + run-in + ~12 s (OBS + seek + checks),
    # corner clip = window + run-in + ~6 s, replay load ≈ 12 s, ACC start ≈ 60 s
    EST_FULL_OVERHEAD_S, EST_CLIP_OVERHEAD_S, EST_LOAD_S, EST_START_ACC_S = 8.0, 5.0, 12.0, 30.0
    LEAD_FULL_S, LEAD_CLIP_S = 1.5, 1.5
    # Recording at 2× replay speed (ACC SetTimeMultiplier, OBS at 60 fps) halves the time, but measured on dash
    # speed vs telemetry the picture and ACC's replay clock drift apart by up to ±1 s at 2× (2–3 ms at 1×).
    # Sync accuracy matters more, so record at 1×.
    SPEED = 1.0
    OBS_FPS = 30

    def plan(self):
        """(order, drivers): full laps first, then per driver one camera at a time through the corners."""
        with open(os.path.join(EXPORTS, self.bundle, "manifest.json"), encoding="utf-8") as fh:
            m = json.load(fh)
        try:
            if not self.force:
                adopt_shared(self.bundle)
        except Exception:
            pass
        spots = trouble_spots(self.bundle, self.max_spots)
        plans = {d["label"]: driver_plan(self.bundle, d, spots, self.angles) for d in m["drivers"]}
        drivers = {d["label"]: d for d in m["drivers"]}
        order = []
        for lbl in drivers:                    # one replay load per driver: full lap, then its corner clips
            order += [(lbl, p) for p in plans[lbl] if p["kind"] == "full"]
            clips = [p for p in plans[lbl] if p["kind"] != "full"]
            for cam in self.angles:            # set each camera once, then run through the corners
                order += [(lbl, p) for p in sorted((c for c in clips if c["camera"] == cam),
                                                    key=lambda c: c["window"][0])]
        self._spots = spots
        return order, drivers

    def pass_estimate(self, d: dict, p: dict) -> float:
        if p["kind"] == "full":
            lap = next((l for l in d["laps"] if l["lap_index"] == p["lap"]), {"lap_ms": 140000})
            return (lap["lap_ms"] / 1000.0 + self.LEAD_FULL_S + 1.0) / self.SPEED + self.EST_FULL_OVERHEAD_S
        return (p["window"][1] - p["window"][0] + self.LEAD_CLIP_S + 1.0) / self.SPEED + self.EST_CLIP_OVERHEAD_S

    def estimate(self, acc_up: bool = True, loaded: Optional[str] = None, fresh: bool = False) -> float:
        """Seconds for a run (skipping passes already recorded unless ``fresh``); 0 when nothing is missing."""
        order, drivers = self.plan()
        have = {lbl: [] if fresh else _existing(self.bundle, drivers[lbl]) for lbl in drivers}
        if all(_has(have[lbl], p) for lbl, p in order):
            return 0.0
        total, current = (0.0 if acc_up else self.EST_START_ACC_S), loaded
        for lbl, p in order:
            if _has(have[lbl], p):
                continue
            if lbl != current:
                total += self.EST_LOAD_S
                current = lbl
            total += self.pass_estimate(drivers[lbl], p)
        return total

    def eta(self) -> Optional[float]:
        if not self.steps:
            return None
        left, current = 0.0, getattr(self, "_current_driver", None)
        for st in self.steps:
            if st["state"] in ("pending", "recording"):
                if st["driver"] != current:
                    left += self.EST_LOAD_S
                    current = st["driver"]
                left += st.get("est_s", 20.0) * (0.5 if st["state"] == "recording" else 1.0)
        if self.state == "starting_acc":
            left += self.EST_START_ACC_S
        return round(left)

    def status(self) -> dict:
        return {"state": self.state, "prompt": self.prompt, "steps": self.steps, "error": self.error,
                "log": self.logs[-8:], "expect": getattr(self, "expect", None), "acc_now": getattr(self, "acc_now", None),
                "eta_s": self.eta() if self.state not in ("done", "error", "cancelled", "idle") else None,
                "elapsed_s": round(time.time() - self._t0) if getattr(self, "_t0", None) else None}

    def stop(self):
        self._stop.set()
        if self._cap is not None:
            self._cap.stop()

    @staticmethod
    def _record_compact(obs) -> dict:
        """Simple output 'Small' quality ignores bitrate (~30 Mbit/s here); for the run record at the stream
        bitrate instead (≈6 Mbit/s → ~5× smaller). Returns profile values to restore."""
        restore = {}
        try:
            mode = obs.request("GetProfileParameter", {"parameterCategory": "Output", "parameterName": "Mode"})
            if mode.get("parameterValue") != "Simple":
                return restore
            q = obs.request("GetProfileParameter", {"parameterCategory": "SimpleOutput", "parameterName": "RecQuality"})
            if q.get("parameterValue") and q["parameterValue"] != "Stream":
                restore["RecQuality"] = q["parameterValue"]
                obs.request("SetProfileParameter", {"parameterCategory": "SimpleOutput", "parameterName": "RecQuality",
                                                    "parameterValue": "Stream"})
        except Exception:
            pass
        return restore

    @staticmethod
    def _record_1080p(obs) -> dict:
        """Record at most 1080p for the session (≈¼ of 4K); returns the settings to restore."""
        cur = obs.request("GetVideoSettings")
        if cur.get("outputHeight", 0) <= 1080:
            return {}
        w = int(round(cur["outputWidth"] * 1080 / cur["outputHeight"] / 2) * 2)
        obs.request("SetVideoSettings", {"outputWidth": w, "outputHeight": 1080})
        return {"outputWidth": cur["outputWidth"], "outputHeight": cur["outputHeight"]}

    def _verified(self, d, detect, ReplayControl) -> bool:
        """Both checks: ACC loaded this driver's file (log + access time) and its replay ends where ours does."""
        det = detect()
        try:
            st_ = ReplayControl().status() if det.get("in_replay") else {}
            end = (st_.get("start_s") or 0) + st_["total_s"] if st_.get("total_s") else None
        except (TimeoutError, OSError):
            end = None
        # Match on the replay file itself: the same .rpy can belong to several bundles (e.g. the reference replay is
        # shared), so "which bundle does this file map to" is not a valid check.
        loaded = det.get("file")
        try:
            loaded = staged_map().get(loaded, loaded)
        except Exception:
            pass
        file_ok = bool(det.get("in_replay") and loaded and loaded == d.get("rpy_file"))
        len_ok = end is not None and abs(end - (d.get("replay_end_s") or 0)) <= 2.0
        self.acc_now = {"in_replay": bool(det.get("in_replay")), "file": det.get("file"), "driver": det.get("driver"),
                        "length_s": end, "file_ok": file_ok, "length_ok": len_ok}
        if file_ok and len_ok:
            self.log("Verified: ACC shows %s (%s, ends %.0f s)" % (d["label"], det.get("file"), end))
        return file_ok and len_ok

    # ---- OBS: a scene that can only ever show ACC ----
    SCENE = "VRE · ACC replay"
    SOURCE = "VRE · ACC game"

    def _obs_scene(self, obs) -> Optional[str]:
        """Switch OBS to a scene with only a Game Capture of ACC; return the scene to restore."""
        prev = obs.request("GetCurrentProgramScene").get("currentProgramSceneName")
        scenes = [x["sceneName"] for x in obs.request("GetSceneList").get("scenes", [])]
        if self.SCENE not in scenes:
            obs.request("CreateScene", {"sceneName": self.SCENE})
            obs.request("CreateInput", {
                "sceneName": self.SCENE, "inputName": self.SOURCE, "inputKind": "game_capture",
                "inputSettings": {"capture_mode": "window", "window": "AC2:UnrealWindow:AC2-Win64-Shipping.exe",
                                  "priority": 2, "capture_cursor": False, "allow_transparency": False},
                "sceneItemEnabled": True})
        obs.request("SetCurrentProgramScene", {"sceneName": self.SCENE})
        return prev if prev != self.SCENE else None

    def _acc_visible(self, obs, tries: int = 20) -> bool:
        """ACC in front and OBS actually receiving its frames (non-black image from the game source)."""
        import base64
        import io

        from .acc_input import AccWindow

        for i in range(tries):
            if i % 5 == 0:
                w = AccWindow()
                try:
                    w.focus()
                finally:
                    w.close()
            try:
                d = obs.request("GetSourceScreenshot", {"sourceName": self.SOURCE, "imageFormat": "png",
                                                        "imageWidth": 160})
                raw = base64.b64decode(d["imageData"].split(",", 1)[1])
                try:
                    from PIL import Image
                    im = Image.open(io.BytesIO(raw)).convert("L")
                    lo, hi = im.getextrema()
                    if hi - lo > 20:
                        return True
                except ImportError:
                    return True
            except Exception:
                pass
            time.sleep(1.0)
        return False

    def _ensure_acc(self, ReplayControl):
        from .acc_bindings import acc_running

        if not acc_running():
            self.state = "starting_acc"
            self.log("Starting ACC…")
            import subprocess
            # ACC's own launcher exe (= Steam's normal "Play" option) — avoids Steam's launch-option dialog
            exe = r"C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa Competizione\acc.exe"
            subprocess.Popen(["cmd.exe", "/c", "start", "", exe], cwd="/mnt/c",
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            end = time.time() + 240
            while time.time() < end and not self._stop.is_set():
                time.sleep(3.0)
                if acc_running():
                    try:
                        if ReplayControl().where() in ("menu", "race"):
                            time.sleep(5.0)
                            return
                    except Exception:
                        pass
            raise RuntimeError("ACC didn't start")

    @staticmethod
    def _remember_foreground() -> Optional[int]:
        try:
            from .acc_input import AccWindow
            w = AccWindow()
            try:
                return w.foreground()
            finally:
                w.close()
        except Exception:
            return None

    def _return_to_browser(self):
        if not getattr(self, "_browser", None):
            return
        try:
            from .acc_input import AccWindow
            w = AccWindow()
            try:
                w.activate(self._browser)
            finally:
                w.close()
        except Exception:
            pass

    def run(self):
        from .acc_broadcast import BroadcastClient
        from .acc_replay_capture import Capture
        from .acc_replay_detect import detect
        from .acc_ue4ss import ReplayControl
        from .obs_ws import ObsClient

        obs = bc = None
        restore_scene = None
        try:
            if not ReplayControl.available():
                raise RuntimeError("Needs the UE4SS replay control installed in ACC (see docs/USAGE.md)")
            self._t0 = time.time()
            order, drivers = self.plan()
            self.steps = [{"driver": lbl, "label": p["label"], "state": "pending",
                           "est_s": round(self.pass_estimate(drivers[lbl], p), 1)} for lbl, p in order]
            self.log("Trouble spots: %s" % ", ".join(s["corner"] for s in self._spots))
            have0 = {lbl: [] if self.force else _existing(self.bundle, drivers[lbl]) for lbl in drivers}
            if all(_has(have0[lbl], p) for lbl, p in order):
                for st in self.steps:
                    st["state"], st["est_s"] = "done", 0
                self.log("Everything is already recorded")
                self.state = "done"
                return
            self._browser = self._remember_foreground()
            self._ensure_acc(ReplayControl)
            obs = ObsClient()
            obs.connect()
            restore_scene = self._obs_scene(obs)
            self._restore_video = self._record_1080p(obs)
            vs = obs.request("GetVideoSettings")
            if (vs.get("fpsNumerator"), vs.get("fpsDenominator")) != (self.OBS_FPS, 1):
                self._restore_video = dict(self._restore_video or {}, fpsNumerator=vs["fpsNumerator"],
                                           fpsDenominator=vs["fpsDenominator"])
                obs.request("SetVideoSettings", {"fpsNumerator": self.OBS_FPS, "fpsDenominator": 1})
            # (changing OBS's recording quality at runtime leaves its outputs half-configured and recording
            #  silently never starts — so file size is left to OBS's own settings)
            have = {lbl: [] if self.force else _existing(self.bundle, drivers[lbl]) for lbl in drivers}
            current = None
            for k, (lbl, p) in enumerate(order):
                if self._stop.is_set():
                    break
                d = drivers[lbl]
                if _has(have[lbl], p):
                    self.steps[k]["state"] = "done"
                    self.steps[k]["est_s"] = 0
                    continue
                if current != lbl or not self._verified(d, detect, ReplayControl):
                    self.expect = {"driver": lbl, "file": d.get("rpy_file"), "length_s": round(d.get("replay_end_s") or 0, 1)}
                    if not self._verified(d, detect, ReplayControl):
                        self.state = "loading_replay"
                        self.log("Loading %s's replay in ACC…" % lbl)
                        try:
                            ReplayControl().load_replay(d["rpy_file"], d["identity"].get("track_id") or 0,
                                                        d["identity"].get("car_model_id") or 0, d.get("replay_end_s") or 0)
                        except (RuntimeError, TimeoutError) as exc:
                            self.log("Automatic load failed (%s) — waiting for you to load it" % exc)
                            self.state = "waiting_for_load"
                            self.prompt = "In ACC: Replays → load %s's replay (%s)" % (lbl, _describe(d))
                        while not self._stop.is_set() and not self._verified(d, detect, ReplayControl):
                            time.sleep(1.0)
                        if self._stop.is_set():
                            break
                    self.prompt = ""
                    current = lbl
                    self._current_driver = lbl
                    time.sleep(2.0)
                    if bc is not None:          # a new replay load restarts ACC's broadcasting
                        bc.close()
                        bc = None
                if bc is not None and not bc.fresh():
                    bc.close()
                    bc = None
                if bc is None:
                    # ACC's broadcasting port only answers once a replay/session is loaded
                    for _ in range(10):
                        bc = BroadcastClient(interval_ms=50)
                        if bc.connect(timeout=3.0):
                            t_end = time.time() + 3.0
                            while time.time() < t_end and not bc.fresh():
                                time.sleep(0.1)
                            if bc.fresh():
                                break
                        bc.close()
                        bc = None
                        time.sleep(2.0)
                    if bc is None:
                        raise RuntimeError("ACC isn't answering on its broadcasting port")
                self.state = "recording"
                self.steps[k]["state"] = "recording"
                if not self._acc_visible(obs):
                    self.steps[k]["state"] = "error: OBS isn't receiving ACC's picture"
                    raise RuntimeError("OBS isn't receiving ACC's picture — is ACC on screen?")
                meta = {"kind": p["kind"], "corner": p.get("corner"), "pass_label": p["label"], "lap": p["lap"]}
                if p.get("s0_m") is not None:
                    meta.update({"s0_m": p["s0_m"], "s1_m": p["s1_m"]})
                cap = Capture(self.bundle, driver=lbl, lap=p["lap"], camera=p["camera"], window=p.get("window"),
                              meta=meta, conns=(obs, bc), log=self.log,
                              lead_s=self.LEAD_FULL_S if p["kind"] == "full" else self.LEAD_CLIP_S,
                              speed=self.SPEED)
                self._cap = cap
                cap.run()
                self.steps[k]["state"] = "done" if cap.state == "done" else ("error: " + (cap.error or cap.state))
            self.state = "cancelled" if self._stop.is_set() else "finishing"
            if not self._stop.is_set():
                self.log("Closing ACC…")
                try:
                    ReplayControl().quit_acc()
                except Exception as exc:
                    self.log("Couldn't close ACC: %s" % exc)
                self.state = "done"
                self.log("Done in %d min" % round((time.time() - self._t0) / 60.0))
        except Exception as exc:   # surface anything to the UI
            self.error, self.state = str(exc), "error"
            self.log("Error: %s" % exc)
        finally:
            if obs is not None:
                try:   # settings only restore when OBS isn't recording
                    if obs.request("GetRecordStatus").get("outputActive"):
                        obs.request("StopRecord")
                        time.sleep(1.0)
                except Exception:
                    pass
                for name, val in (getattr(self, "_restore_profile", None) or {}).items():
                    try:
                        obs.request("SetProfileParameter", {"parameterCategory": "SimpleOutput",
                                                            "parameterName": name, "parameterValue": val})
                    except Exception:
                        pass
                if getattr(self, "_restore_video", None):
                    try:
                        obs.request("SetVideoSettings", self._restore_video)
                    except Exception:
                        pass
                if restore_scene:
                    try:
                        obs.request("SetCurrentProgramScene", {"sceneName": restore_scene})
                    except Exception:
                        pass
            try:
                from .video_store import prune
                pr = prune(self.bundle, keep_corners={sp["corner"] for sp in getattr(self, "_spots", [])} or None,
                           keep_spans=[(sp["s0_m"], sp["s1_m"]) for sp in getattr(self, "_spots", [])] or None)
                if pr["removed"]:
                    self.log("Pruned %d old recordings (%.1f GB)" % (len(pr["removed"]), pr["freed_bytes"] / 1e9))
            except Exception:
                pass
            try:
                unstage()
            except OSError:
                pass
            for c in (bc, obs):
                try:
                    c and c.close()
                except Exception:
                    pass
            self.prompt = ""
            self._return_to_browser()
