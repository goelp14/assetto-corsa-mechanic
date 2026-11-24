"""Record an ACC replay to video with OBS, synced lap-by-lap to a Lap Studio bundle.

    1. Open the replay in ACC, pick the car and camera you want, and press play.
    2. python -m external.query_tools.acc_replay_capture --bundle lab_spa_you_vs_erik
       (records until you pause the replay for 4 s, press Ctrl+C, or --laps N laps finish)

How the sync works: while OBS records, ACC's broadcasting API reports (every 50 ms) the focused
car's lap count and current lap time. Each sample pairs a video time (wall clock since OBS started
recording) with a lap time, so every recorded lap gets a lap-time → video-time table. Completed laps
are matched to the bundle's laps by their exact lap time (ms), which identifies driver and lap.
The result is appended to ``exports/<bundle>/videos.json``; Lap Studio's Video panel plays it beside
the telemetry.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

from .acc_broadcast import BroadcastClient, Snapshot
from .obs_ws import ObsClient, ObsError

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXPORTS = os.path.join(ROOT, "exports")
MATCH_TOL_MS = 3
# ACC rounds 'replay time remaining' to whole seconds, so a tick (N → N−1) happens when the true
# remaining time crosses N − 0.5. Measured on a Spa recording: without this the video lagged the
# telemetry by 0.497 ± 0.005 s at seven points (dash speed readout vs decoded speed).
TICK_PHASE_S = 0.5


# ------------------------------------------------------------------ pure sync logic (tested)

def lap_tables(samples: List[dict]) -> List[dict]:
    """Group samples into laps → [{car, laps, lap_ms (if completed), complete, map: [[lap_t, video_t], ...]}].

    A sample is {"v": video_s, "car": idx, "laps": completed_laps, "cur_ms": current_lap_ms, "last_ms": last_lap_ms}.
    Pairs where the lap clock did not advance (replay paused, video still running) are dropped so the
    table stays monotonic; the panel interpolates between pairs.
    """
    groups: Dict[tuple, List[dict]] = {}
    order: List[tuple] = []
    for s in samples:
        if s.get("cur_ms") is None or s["cur_ms"] < 0:
            continue
        key = (s["car"], s["laps"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(s)
    out = []
    for key in order:
        g = groups[key]
        pts: List[List[float]] = []
        for s in g:
            lt = s["cur_ms"] / 1000.0
            if pts and lt <= pts[-1][0] + 1e-4:
                continue
            pts.append([round(lt, 3), round(s["v"], 3)])
        nxt = groups.get((key[0], key[1] + 1))
        lap_ms = nxt[0]["last_ms"] if nxt else None
        first_lt = pts[0][0] if pts else None
        complete = bool(nxt) and first_lt is not None and first_lt < 1.0
        if pts and lap_ms and lap_ms > 0:
            # anchor the lap end: the next lap's first sample happened (cur_ms of that lap) after the line
            n0 = nxt[0]
            pts.append([round(lap_ms / 1000.0, 3), round(n0["v"] - n0["cur_ms"] / 1000.0, 3)])
        if first_lt is not None and first_lt < 1.0 and pts:
            pts.insert(0, [0.0, round(pts[0][1] - pts[0][0], 3)])
            if len(pts) > 1 and pts[1][0] == 0.0:
                pts.pop(1)
        out.append({"car": key[0], "laps": key[1], "lap_ms": lap_ms if lap_ms and lap_ms > 0 else None,
                    "complete": complete, "map": _thin(pts)})
    return out


def _thin(pts: List[List[float]], tol=0.004) -> List[List[float]]:
    """Drop points that lie on the line between neighbours (1× playback is a straight line)."""
    if len(pts) <= 2:
        return pts
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = keep[-1], pts[i], pts[i + 1]
        if c[0] == a[0]:
            continue
        pred = a[1] + (b[0] - a[0]) * (c[1] - a[1]) / (c[0] - a[0])
        if abs(pred - b[1]) > tol:
            keep.append(b)
    keep.append(pts[-1])
    return keep


def replay_segments(samples: List[dict], end_s: float, phase: float = TICK_PHASE_S) -> List[dict]:
    """Continuous stretches of playback as lines: decoder time = a + b × video time.

    ACC's 'replay time remaining' only ticks in whole seconds, but *when* it ticks is known to one
    sample (~50 ms). At a tick the decoder time is ``end_s − new remaining − TICK_PHASE_S``, so a line
    fitted through the ticks of one stretch is accurate to a few tens of ms. A backwards jump
    (rewind) or a jump of more than 2 s (skip) starts a new stretch.
    """
    segs: List[List[tuple]] = []
    cur: List[tuple] = []
    prev_rem = None
    last_v = None
    for smp in samples:
        rem = smp.get("remaining")
        if rem is None:
            continue
        if prev_rem is not None and rem != prev_rem:
            step = prev_rem - rem
            # pause: the clock sat still for longer than one tick takes at ≥0.5× speed
            stalled = cur and smp["v"] - cur[-1][0] > 2.0 * step + 0.3
            if 0 < step <= 2.0 and not stalled:
                cur.append((smp["v"], end_s - rem - phase))
            else:                                   # rewind / skip
                if len(cur) >= 2:
                    segs.append(cur)
                cur = [(smp["v"], end_s - rem - phase)]
        prev_rem = rem
        last_v = smp["v"]
    if len(cur) >= 2:
        segs.append(cur)
    out = []
    for ticks in segs:
        n = len(ticks)
        mv = sum(v for v, _ in ticks) / n
        md = sum(d for _, d in ticks) / n
        var = sum((v - mv) ** 2 for v, _ in ticks)
        b = sum((v - mv) * (d - md) for v, d in ticks) / var if var > 0 else 1.0
        a = md - b * mv
        v0, v1 = ticks[0][0], ticks[-1][0] + (1.0 / b if b > 0 else 0.0)   # holds until the next tick
        resid = max(abs(a + b * v - d) for v, d in ticks)
        out.append({"v0": v0, "v1": v1, "a": a, "b": b, "ticks": n, "max_resid_s": resid})
    return out


def replay_lap_tables(samples: List[dict], laps: List[dict], end_s: float, phase: float = TICK_PHASE_S) -> List[dict]:
    """Saved replays: per bundle lap (``start_s``, ``lap_ms``), a lap-time → video-time table built
    from the playback stretches (``replay_segments``). If a lap was played more than once (rewind),
    the last full-enough pass wins.

    A sample is {"v": video_s, "remaining": s} (ACC's 'replay time remaining').
    """
    segs = replay_segments(samples, end_s, phase)
    out = []
    for lap in laps:
        if lap.get("start_s") is None:
            continue
        s0, dur = float(lap["start_s"]), lap["lap_ms"] / 1000.0
        pieces = []
        for sg in segs:
            d0, d1 = sg["a"] + sg["b"] * sg["v0"], sg["a"] + sg["b"] * sg["v1"]
            lo, hi = max(d0, s0 - 0.2), min(d1, s0 + dur + 0.2)
            if hi - lo < 0.5:
                continue
            pieces.append((lo - s0, hi - s0, sg))
        if not pieces:
            continue
        # walk back from the latest pass, keeping lap time monotonic in video order
        chosen = []
        for lo, hi, sg in reversed(pieces):
            if chosen and hi > chosen[0][0] + 1e-3:
                if hi - chosen[0][0] <= 1.5 and lo < chosen[0][0] - 0.5:
                    hi = chosen[0][0]          # a stretch's last tick interval runs into the next one
                elif chosen[0][1] - chosen[0][0] >= hi - lo:
                    continue                   # rewound and replayed: keep the longer pass
                else:
                    chosen = []
            chosen.insert(0, (lo, hi, sg))
        pts: List[List[float]] = []
        for lo, hi, sg in chosen:
            for lt in (lo, hi):
                v = (lt + s0 - sg["a"]) / sg["b"]
                pts.append([round(lt, 3), round(v, 3)])
        cover_lo, cover_hi = chosen[0][0], chosen[-1][1]
        out.append({"lap_index": lap["lap_index"], "lap_ms": lap["lap_ms"],
                    "complete": cover_lo <= 0.3 and cover_hi >= dur - 0.3,
                    "fit_resid_s": round(max(sg["max_resid_s"] for _, _, sg in chosen), 3),
                    "map": pts})
    return out


def match_laps(tables: List[dict], manifest: dict) -> Optional[str]:
    """Fill lap_index/driver on tables whose lap time matches a bundle lap; return the driver label."""
    best_label, best_hits = None, 0
    for d in manifest.get("drivers", []):
        hits = 0
        for t in tables:
            if t["lap_ms"] and any(abs(l["lap_ms"] - t["lap_ms"]) <= MATCH_TOL_MS for l in d["laps"]):
                hits += 1
        if hits > best_hits:
            best_label, best_hits = d["label"], hits
    if best_label is None:
        return None
    drv = next(d for d in manifest["drivers"] if d["label"] == best_label)
    for t in tables:
        if t["lap_ms"]:
            m = next((l for l in drv["laps"] if abs(l["lap_ms"] - t["lap_ms"]) <= MATCH_TOL_MS), None)
            if m:
                t["lap_index"] = m["lap_index"]
    return best_label


# ------------------------------------------------------------------ recorder

def _to_wsl(path: str) -> str:
    if sys.platform == "win32" or not path or path.startswith("/"):
        return path
    try:
        return subprocess.check_output(["wslpath", "-u", path], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return path


class Capture:
    """One recording session. ``start()`` blocks until the replay plays; ``stop()`` finalises."""

    def __init__(self, bundle: str, laps: Optional[int] = None, pause_stop_s: float = 4.0, log=print,
                 driver: Optional[str] = None, lap=None, camera: Optional[str] = "Drivable/Dash",
                 lead_s: float = 3.0, window=None, meta: Optional[dict] = None, conns=None, speed: float = 1.0):
        """``lap``: a lap index or "best" → jump there via ACC's own replay functions (UE4SS),
        set ``camera`` (``set/name`` as ACC reports it), record that one lap, pause after it."""
        self.bundle = bundle
        self.driver = driver
        self.lap = lap
        self.camera = camera
        self.lead_s = lead_s
        self.speed = speed            # replay speed while recording (ACC SetTimeMultiplier); sync fits the slope
        self.window = window          # (start_s, end_s) on the replay clock: record just that stretch
        self.meta = dict(meta or {})  # stored with the video (kind, corner, …)
        self._conns = conns           # (obs, broadcast) to reuse across passes
        self._window_end = None
        self.rc = None
        self._tick_phase = TICK_PHASE_S
        self.bdir = os.path.join(EXPORTS, bundle)
        if not os.path.isfile(os.path.join(self.bdir, "manifest.json")):
            raise FileNotFoundError("No Lap Studio bundle named %s in exports/" % bundle)
        self.laps_target = laps
        self.pause_stop_s = pause_stop_s
        self.log = log
        self.bc: Optional[BroadcastClient] = None
        self.obs: Optional[ObsClient] = None
        self.samples: List[dict] = []
        self.rec_wall: Optional[float] = None
        self.state = "idle"
        self.error = ""
        self.result: Optional[dict] = None
        self._stop = threading.Event()
        self._camera = ""

    # -- lifecycle --
    @staticmethod
    def _remove_file(path: str):
        for _ in range(20):                   # OBS may hold the file for a moment after stopping
            try:
                if path and os.path.isfile(path):
                    os.remove(path)
                return
            except OSError:
                time.sleep(0.25)

    def _abort_recording(self):
        """After a failed pass: make sure OBS isn't left recording, and drop the partial file."""
        if not getattr(self, "_recording_started", False) or self.obs is None or self.state in ("saving", "done"):
            return
        try:
            for _ in range(30):
                if self.obs.request("GetRecordStatus").get("outputActive"):
                    path = self.obs.request("StopRecord").get("outputPath")
                    if path:
                        self._remove_file(_to_wsl(path))
                    return
                time.sleep(0.1)
        except (ObsError, OSError):
            pass

    def run(self):
        try:
            self._run()
        except (ObsError, RuntimeError, OSError) as exc:
            self.error, self.state = str(exc), "error"
            self.log("Error: %s" % exc)
            self._abort_recording()
        finally:
            if not self._conns:
                if self.bc:
                    self.bc.close()
                if self.obs:
                    self.obs.close()

    def stop(self):
        self._stop.set()

    def _run(self):
        self.state = "connecting"
        if self._conns:
            self.obs, self.bc = self._conns
        else:
            self.obs = ObsClient()
            self.obs.connect()
            self.bc = BroadcastClient(interval_ms=50)
            if not self.bc.connect():
                raise RuntimeError("ACC's broadcasting API did not answer — is ACC open with a replay loaded?")
        self.state = "waiting"
        if self.lap is not None or self.window is not None:
            self._jump_to_lap()
        else:
            self.log("Connected to OBS and ACC. Press play on the replay in ACC…")
        prev, moving = None, 0
        while not self._stop.is_set() and self.rc is None:
            clk = self._clock(self.bc.snapshot().realtime)
            if clk is not None:
                if prev is not None and abs(clk - prev) > 0.01:
                    moving += 1
                prev = clk
                if moving >= 3:
                    break
            time.sleep(0.05)
        if self._stop.is_set():
            self.state = "cancelled"
            return
        # a previous pass's file may still be finalising: wait until OBS is idle; if it's still recording
        # (left over from a failed pass) stop it so this pass can start
        for i in range(100):
            if not self.obs.request("GetRecordStatus").get("outputActive"):
                break
            if i == 30:
                try:
                    left = self.obs.request("StopRecord").get("outputPath")
                    self.log("Stopped a leftover OBS recording")
                    if left:
                        self._remove_file(_to_wsl(left))
                except ObsError:
                    pass
            time.sleep(0.1)
        self._recording_started = True
        with self.obs._cond:                  # forget events from earlier clips (e.g. the last STOPPED)
            self.obs.events = [e for e in self.obs.events if e[1] != "RecordStateChanged"]
        self.obs.request("StartRecord")
        self.obs.wait_event("RecordStateChanged",
                            lambda d: d.get("outputState") == "OBS_WEBSOCKET_OUTPUT_STARTED", timeout=10.0)
        active = False
        for _ in range(20):                   # OBS reports active shortly after STARTED
            if self.obs.request("GetRecordStatus").get("outputActive"):
                active = True
                break
            time.sleep(0.1)
        if not active:
            raise RuntimeError("OBS accepted the start but isn't recording — check OBS's output settings/log")
        # Video clock = OBS's own recording timer. WSL's clock can run several % fast and get
        # stepped back, so local time is only used to interpolate the ≤50 ms between polls.
        self._polls: List[tuple] = []
        threading.Thread(target=self._poll_obs, daemon=True).start()
        t_wait = time.monotonic() + 10.0
        while not self._polls and not self._stop.is_set():
            if time.monotonic() > t_wait:
                raise RuntimeError("OBS's recording clock never started")
            time.sleep(0.01)
        self.rec_wall = time.monotonic()
        self.state = "recording"
        if self.rc is not None:
            self.rc.play()
        self.log("Recording…")
        self.bc.listeners.append(self._on_update)
        last_move, last_rt = time.monotonic(), None
        while not self._stop.is_set():
            time.sleep(0.1)
            rt = self.bc.snapshot().realtime
            clk = self._clock(rt)
            if clk is not None:
                if last_rt is None or abs(clk - last_rt) > 0.01:
                    last_move, last_rt = time.monotonic(), clk
                self._camera = "%s/%s" % (rt.camera_set, rt.camera)
            if time.monotonic() - last_move > self.pause_stop_s:
                self.log("Replay paused — stopping.")
                break
            if self._window_end is not None:
                d = self._driver_meta()
                rem = self.samples[-1].get("remaining") if self.samples else None
                if d and rem is not None and d["replay_end_s"] - rem - self._tick_phase >= self._window_end + 1.0:
                    self.log("Window recorded — stopping.")
                    break
            elif getattr(self, "_only_lap", None) is not None:
                # keep going ~1 s past the line so the whole lap is in the file
                if any(t.get("lap_index") == self._only_lap and t["complete"] and t["map"]
                       and t["map"][-1][0] >= (t.get("lap_ms") or 0) / 1000.0 for t in self.tables()):
                    self.log("Lap %d recorded — stopping." % self._only_lap)
                    break
            elif self.laps_target and self.complete_laps() >= self.laps_target:
                self.log("%d laps recorded — stopping." % self.laps_target)
                break
        self.bc.listeners.clear()
        if self.rc is not None:
            try:
                self.rc.pause()
                if self.speed and self.speed != 1.0:
                    self.rc.send("speed", "1")
            except (TimeoutError, OSError):
                pass
        self.state = "stopping"
        time.sleep(0.1)
        out = self.obs.request("StopRecord")
        path = out.get("outputPath")
        if not path:
            ev = self.obs.wait_event("RecordStateChanged", lambda d: d.get("outputState") == "OBS_WEBSOCKET_OUTPUT_STOPPED")
            path = ev[1].get("outputPath") if ev else ""
        self.state = "saving"
        self.result = self._save(path)
        want = getattr(self, "_only_lap", None) or (self.lap if isinstance(self.lap, int) else None)
        if want is None and self.window is not None:
            want = self.meta.get("lap") or (self.lap if self.lap not in (None, "best") else None)
        covered = [l for l in self.result.get("laps", []) if l.get("lap_index") == want] if want else self.result.get("laps")
        if not covered:
            self._discard(self.result)
            self.result = None
            raise RuntimeError("recording didn't cover lap %s — discarded" % want)
        self.state = "done"

    def _jump_to_lap(self):
        """Pause, seek to just before the lap, set the camera — all with ACC's own functions."""
        from .acc_ue4ss import ReplayControl

        if not ReplayControl.available():
            raise RuntimeError("Jumping to a lap needs the UE4SS replay control installed in ACC")
        d = self._driver_meta()
        if d is None:
            raise RuntimeError("Can't tell whose replay ACC is showing — pick the driver")
        idx = d.get("best_lap_index") if self.lap in (None, "best") else int(self.lap)
        row = next((l for l in d["laps"] if l["lap_index"] == idx), None)
        if self.window is None and (row is None or row.get("start_s") is None):
            raise RuntimeError("Lap %s of %s isn't in the bundle" % (idx, d["label"]))
        self.rc = ReplayControl()
        st = self.rc.status()
        if not st.get("in_replay"):
            raise RuntimeError("ACC isn't showing a replay")
        acc_end = (st.get("start_s") or 0) + (st.get("total_s") or 0)   # ACC: replay starts at start_s, lasts total_s
        if abs(acc_end - (d.get("replay_end_s") or 0)) > 2.0:
            raise RuntimeError("ACC's replay (ends %.0f s) isn't %s's (ends %.0f s)" % (acc_end, d["label"],
                                                                                      d.get("replay_end_s") or 0))
        self.rc.pause()
        self.driver = d["label"]
        # after a whole-second seek ACC ticks ~1 s late: 1.0 measured first, refined to 0.965 (video was 25–46 ms
        # ahead for both drivers on dash speed vs telemetry)
        self._tick_phase = 0.965
        if self.window is not None:
            target = max(0, int(self.window[0] - self.lead_s))
            got = self.rc.seek(target).get("current_s")
            self._window_end = float(self.window[1])
            self.log("Jumped to %d s for %.1f–%.1f s (%s)" % (got or -1, self.window[0], self.window[1],
                                                                self.meta.get("label", d["label"])))
        else:
            target = max(0, int(row["start_s"] - self.lead_s))
            got = self.rc.seek(target).get("current_s")
            self.log("Jumped to %d s (lap %d of %s starts at %.2f s)" % (got or -1, idx, d["label"], row["start_s"]))
            self.laps_target = 1
            self._only_lap = idx
        if self.camera:
            self._set_camera(self.camera)
        if self.speed and self.speed != 1.0:
            self.rc.send("speed", "%g" % self.speed)

    # ACC's camera keys, mapped by cycling each key and reading the camera ACC reports:
    #   F1: Drivable Dash/Helmet/Bonnet/DashPro/Chase/FarChase/Cockpit · F3: TV set1 → set2 → Helicam ·
    #   F6: Onboard0-3. TV sets pick the trackside camera themselves, so only the set is matched.
    CAMERA_KEYS = {"Drivable": "F1", "set1": "F3", "set2": "F3", "Helicam": "F3", "Onboard": "F6"}
    # ACC's direct camera actions (default keyboard bindings): SelectCockpitCamera = 1,
    # SelectBonnetCamera = 2, SelectChaseCamera = 3, SelectTVCamera = F3. Tried first; cycling is the fallback.
    CAMERA_DIRECT = {"Drivable/Cockpit": "31", "Drivable/Bonnet": "32", "Drivable/Chase": "33",
                     "Drivable/FarChase": "33", "set1": "F3"}

    def _set_camera(self, want: str, tries: int = 12):
        """Press ACC's camera key for that set until ACC reports the wanted camera."""
        from .acc_input import AccWindow

        cur = lambda: (lambda r: "%s/%s" % (r.camera_set, r.camera) if r else "")(self.bc.snapshot().realtime)
        want_set = want.split("/")[0]
        match = (lambda c: c.split("/")[0] == want_set) if want_set in ("set1", "set2") or "/" not in want \
            else (lambda c: c == want)
        if match(cur()):
            return
        key = self.CAMERA_KEYS.get(want_set, "F1")
        direct = self.CAMERA_DIRECT.get(want) or self.CAMERA_DIRECT.get(want_set)
        w = AccWindow()
        try:
            w.focus()
            if direct:
                for _ in range(2):          # e.g. 3 toggles Chase / FarChase
                    w.key(direct, 80)
                    time.sleep(0.5)
                    if match(cur()):
                        break
            for _ in range(0 if match(cur()) else tries):
                w.key(key, 80)
                time.sleep(0.5)
                if match(cur()):
                    break
        finally:
            w.close()
        self.log("Camera: %s" % cur())
        if not match(cur()):
            raise RuntimeError("camera didn't switch to %s (ACC shows %s)" % (want, cur()))

    def _poll_obs(self):
        while not self._stop.is_set() and self.state in ("recording", "waiting", "connecting"):
            try:
                t0 = time.monotonic()
                st = self.obs.request("GetRecordStatus", timeout=2.0)
                t1 = time.monotonic()
            except (ObsError, OSError):
                break
            if st.get("outputActive"):
                self._polls.append(((t0 + t1) / 2.0, st.get("outputDuration", 0) / 1000.0))
                del self._polls[:-40]
            time.sleep(0.2)     # 5 Hz is plenty (local clock interpolates); OBS logs every request

    def _video_time(self, mono: float) -> Optional[float]:
        polls = list(self._polls)
        if not polls:
            return None
        m, d = polls[-1]
        rate = 1.0
        if len(polls) >= 4:
            (m0, d0) = polls[-4]
            if m - m0 > 0.2 and d > d0:
                rate = (d - d0) / (m - m0)      # OBS seconds per local second
        return d + (mono - m) * rate

    @staticmethod
    def _clock(rt) -> Optional[float]:
        """A clock that moves while the replay plays: ACC freezes 'replay time' in saved replays but
        counts 'replay time remaining' down; in live sessions use the session clock."""
        if rt is None:
            return None
        if rt.replay:
            return rt.replay_remaining_s
        return rt.session_time_s

    def _manifest(self) -> dict:
        if not hasattr(self, "_mf"):
            with open(os.path.join(self.bdir, "manifest.json"), encoding="utf-8") as fh:
                self._mf = json.load(fh)
        return self._mf

    def _driver_meta(self) -> Optional[dict]:
        """Driver whose replay is playing: the one asked for, else the only replay long enough."""
        drivers = [d for d in self._manifest().get("drivers", []) if d.get("replay_end_s")]
        if not self.driver:
            # which replay ACC has loaded (ACC log + file access time), if it belongs to this bundle
            try:
                from .acc_replay_detect import detect
                det = detect()
                if det.get("bundle") == self.bundle and det.get("driver"):
                    self.driver = det["driver"]
                    self.log("ACC is showing %s → %s" % (det["file"], self.driver))
            except Exception:
                pass
        if self.driver:
            return next((d for d in drivers if d["label"] == self.driver), None)
        rems = [s["remaining"] for s in self.samples if s.get("remaining") is not None]
        if not rems:
            return None
        fit = [d for d in drivers if d["replay_end_s"] >= max(rems) - 1.0]
        return min(fit, key=lambda d: d["replay_end_s"]) if fit else None

    def tables(self) -> List[dict]:
        d = self._driver_meta()
        if d is not None and any(s.get("remaining") is not None for s in self.samples):
            return replay_lap_tables(self.samples, d["laps"], d["replay_end_s"], self._tick_phase)
        return lap_tables([s for s in self.samples if "car" in s])

    def complete_laps(self) -> int:
        return sum(1 for t in self.tables() if t["complete"])

    def _on_update(self, snap: Snapshot):
        rt = snap.realtime
        if rt is None or self.rec_wall is None:
            return
        v = self._video_time(snap.wall)
        if v is None:
            return
        smp = {"v": round(v, 4), "replay": rt.replay,
               "remaining": rt.replay_remaining_s if rt.replay else None}
        car = snap.cars.get(rt.focused_car)
        if car is not None:
            smp.update({"car": car.car_index, "laps": car.laps, "cur_ms": car.current.ms, "last_ms": car.last.ms})
        self.samples.append(smp)

    def _discard(self, vid: dict):
        """Remove a just-saved recording that turned out unusable (file, samples, videos.json entry)."""
        vpath = os.path.join(self.bdir, "videos.json")
        try:
            with open(vpath, encoding="utf-8") as fh:
                doc = json.load(fh)
            doc["videos"] = [v for v in doc.get("videos", []) if v.get("id") != vid.get("id")]
            with open(vpath, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=1)
        except (OSError, ValueError):
            pass
        for p in (vid.get("file"), os.path.join(self.bdir, "video_%s_samples.json" % vid.get("id"))):
            if p and os.path.isfile(p):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def _save(self, win_path: str) -> dict:
        manifest = self._manifest()
        d = self._driver_meta()
        if d is not None and any(s.get("remaining") is not None for s in self.samples):
            tables, label = replay_lap_tables(self.samples, d["laps"], d["replay_end_s"], self._tick_phase), d["label"]
        else:
            tables = lap_tables([s for s in self.samples if "car" in s])
            label = match_laps(tables, manifest)
        vid_path = os.path.join(self.bdir, "videos.json")
        try:
            with open(vid_path, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, ValueError):
            doc = {"videos": []}
        vid = {
            "id": "v%d" % (int(time.time() * 1000) % 10_000_000_000),
            "driver": label,
            "file": _to_wsl(win_path),
            "file_windows": win_path,
            "camera": self._camera,
            "recorded": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "offset_s": 0.0,
            "laps": [t for t in tables if t.get("map")],
            "tool": "vre",
            "tick_phase_s": self._tick_phase,
            "replay_speed": self.speed,
            "rpy_file": (d or {}).get("rpy_file"),
        }
        vid.update(self.meta)
        doc["videos"].append(vid)
        with open(vid_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=1)
        with open(os.path.join(self.bdir, "video_%s_samples.json" % vid["id"]), "w", encoding="utf-8") as fh:
            json.dump(self.samples, fh)
        matched = [t.get("lap_index") for t in vid["laps"] if t.get("lap_index")]
        self.log("Saved %s — %s, laps matched: %s" % (os.path.basename(win_path), label or "no driver matched",
                                                      matched or "none"))
        return vid


def resync(bundle: str, video_id: str, phase: Optional[float] = None) -> int:
    bdir = os.path.join(EXPORTS, bundle)
    with open(os.path.join(bdir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    vpath = os.path.join(bdir, "videos.json")
    with open(vpath, encoding="utf-8") as fh:
        doc = json.load(fh)
    vid = next((v for v in doc["videos"] if v["id"] == video_id), None)
    if vid is None:
        print("No video %s in %s" % (video_id, bundle))
        return 1
    with open(os.path.join(bdir, "video_%s_samples.json" % video_id), encoding="utf-8") as fh:
        samples = json.load(fh)
    d = next(x for x in manifest["drivers"] if x["label"] == vid["driver"])
    phase = vid.get("tick_phase_s", TICK_PHASE_S) if phase is None else phase
    vid["laps"] = replay_lap_tables(samples, d["laps"], d["replay_end_s"], phase)
    vid["tick_phase_s"] = phase
    with open(vpath, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    for t in vid["laps"]:
        print("lap %s complete=%s fit residual %.3f s map %s" % (t["lap_index"], t["complete"], t["fit_resid_s"], t["map"]))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Record an ACC replay with OBS, synced to a Lap Studio bundle")
    ap.add_argument("--bundle", required=True, help="Lap Studio bundle id (folder in exports/)")
    ap.add_argument("--laps", type=int, default=None, help="stop after this many complete laps")
    ap.add_argument("--pause-stop", type=float, default=4.0, help="stop when the replay is paused this long (s)")
    ap.add_argument("--driver", default=None, help="bundle driver label whose replay is playing (default: auto)")
    ap.add_argument("--resync", metavar="VIDEO_ID", help="recompute an existing recording's sync from its saved samples")
    ap.add_argument("--phase", type=float, default=None, help="with --resync: tick phase in s (0 after a seek)")
    ap.add_argument("--lap", default=None, help='jump to this lap ("best" = fastest) and record only it (needs UE4SS)')
    ap.add_argument("--camera", default="Drivable/Dash", help="camera as ACC reports it, e.g. Drivable/Dash")
    args = ap.parse_args(argv)
    if args.resync:
        return resync(args.bundle, args.resync, args.phase)
    cap = Capture(args.bundle, laps=args.laps, pause_stop_s=args.pause_stop, driver=args.driver,
                  lap=args.lap, camera=args.camera)
    t = threading.Thread(target=cap.run, daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(0.2)
    except KeyboardInterrupt:
        cap.stop()
        t.join(15)
    return 0 if cap.state == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
