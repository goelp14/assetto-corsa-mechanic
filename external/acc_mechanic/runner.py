"""Run the Virtual Race Engineer live on ACC.

ACC has no in-game app API, so ac_app's engine runs here, outside the game:

    ACC shared memory ──► AccInfo (sim_info stand-in) ──► VirtualRaceEngineer.acUpdate()
                                                         │
               voice (Windows speech) ◄── feedback ──────┤
               browser dashboard + overlay ◄── HUD labels ┤
               Setups/<car>/<track>/Auto_Tweak.json ◄─────┘ setup tweaks (written on pit entry)

    python -m external.acc_mechanic            # voice + dashboard + overlay
    python -m external.acc_mechanic --no-overlay --no-voice
"""

from __future__ import annotations

import argparse
import collections
import importlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import ac_shim, acc_setup
from .shm import STATUS_LIVE, STATUS_PAUSE, STATUS_REPLAY, AccInfo, open_source

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
AC_APP = os.path.join(REPO, "ac_app")
DEFAULT_DATA = os.path.join(REPO, "data", "acc_live")
STATUS_NAMES = {-1: "waiting for an ACC session", 0: "menu", STATUS_REPLAY: "replay", STATUS_LIVE: "live", STATUS_PAUSE: "paused"}
SESSION_NAMES = {-1: "", 0: "Practice", 1: "Qualifying", 2: "Race", 3: "Hotlap", 4: "Time attack",
                 7: "Hotstint", 8: "Hotlap superpole"}


def _say_text(text: str) -> str:
    """Engineer lines were written for AC; name the ACC setup file correctly."""
    return text.replace("Auto_Tweak.ini", "Auto_Tweak").replace("Auto_Tweak", "the Auto Tweak setup")


# ------------------------------------------------------------------ engine

class Mechanic:
    """Boots ac_app's VirtualRaceEngineer against ACC data and ticks it."""

    def __init__(self, info: AccInfo, data_dir: str = DEFAULT_DATA):
        self.info = info
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.shim = ac_shim.install(info)
        if AC_APP not in sys.path:
            sys.path.insert(0, AC_APP)
        sys.modules.pop("VirtualRaceEngineer", None)
        self.vre = importlib.import_module("VirtualRaceEngineer")
        self.writer = acc_setup.AccSetupWriter()
        self.spoken = collections.deque(maxlen=30)
        self.on_speak = None
        self._last_tick = None
        self._last_packet = None
        self._booted = False
        self.ticks = 0
        self._patch()

    # -- wiring ac_app to ACC ------------------------------------------------
    def _patch(self):
        vre, writer, data_dir = self.vre, self.writer, self.data_dir
        vre._data_path = lambda *parts: os.path.join(data_dir, *parts)
        profiles = os.path.join(data_dir, "car_profiles")
        os.makedirs(profiles, exist_ok=True)

        def car_profile_path(car_id):
            sample = None
            if car_id and car_id != vre._DEFAULT_CAR_ID:
                writer.car_id = car_id
                sample = writer.sample_setup()
            prof = acc_setup.build_profile(car_id or "gt3", sample)
            path = os.path.join(profiles, "%s.json" % (car_id or "gt3"))
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(prof, fh, indent=1)
            return path

        vre._car_profile_path = car_profile_path

        orig_track_cfg = vre._load_track_config

        def load_track_config(track, layout, length_m=0.0):
            cfg = orig_track_cfg("%s_acc" % track.lower(), layout, length_m)
            if cfg.get("generic"):
                cfg = orig_track_cfg(track, layout, length_m)
            return cfg

        vre._load_track_config = load_track_config
        vre._resolve_track_folder = lambda track_name, track_cfg=None: track_name
        vre._read_setup_values = acc_setup.read_values

    def _after_init(self):
        vre = self.vre
        vre._setup_writer = self.writer
        cat = vre._catalog
        cat.symptom_map = acc_setup.acc_symptom_map(cat.symptom_map)
        cat.tradeoffs = acc_setup.acc_tradeoffs(cat.tradeoffs)
        voice = vre._voice
        orig_append = voice.append

        def append(message):
            orig_append(message)
            text = _say_text(str(message))
            self.spoken.append({"t": time.time(), "text": text})
            if self.on_speak:
                self.on_speak(text)

        voice.append = append

    def boot(self):
        self.vre.acMain(1)
        self._after_init()
        self._booted = True

    # -- loop ------------------------------------------------------------------
    def tick(self) -> bool:
        """One step: read ACC, run the engineer if driving. True when the engineer ran."""
        if not self.info.update():
            self._last_tick = None
            return False
        if self.info.status != STATUS_LIVE:
            self._last_tick = None
            return False
        packet = int(self.info.physics.packetId)
        if packet == self._last_packet:
            return False
        self._last_packet = packet
        now = time.monotonic()
        dt = 0.02 if self._last_tick is None else min(0.1, max(0.001, now - self._last_tick))
        self._last_tick = now
        if not self._booted:
            self.boot()
        self.vre.acUpdate(dt)
        self.ticks += 1
        return True

    def shutdown(self):
        if self._booted:
            try:
                self.vre.acShutdown()
            except Exception:
                pass

    # -- state for dashboard / overlay ------------------------------------------
    def _label(self, key):
        lid = self.vre._ui_labels.get(key)
        lab = self.shim.labels.get(lid) if lid is not None else None
        return (lab["text"], lab["color"]) if lab else ("", None)

    def state(self) -> dict:
        info, vre = self.info, self.vre
        st = {"connected": info.connected, "status": STATUS_NAMES.get(info.status, str(info.status)),
              "ticks": self.ticks, "spoken": list(self.spoken)[::-1]}
        if info.connected:
            g, s = info.graphics, info.static
            st.update({
                "car": s.carModel, "track": s.track,
                "session": SESSION_NAMES.get(int(g.session), str(int(g.session))),
                "lap": int(g.completedLaps) + 1, "current_lap": g.currentTime, "last_lap": g.lastTime,
                "best_lap": g.bestTime, "tyre_compound": g.tyreCompound,
                "tc": int(g.TC), "tc_cut": int(g.TCCut), "abs": int(g.ABS), "engine_map": int(g.EngineMap) + 1,
                "fuel_l": round(float(info.physics.fuel), 1),
            })
            p = info.physics
            st["tyres"] = {
                "core_c": [round(float(v), 1) for v in p.tyreCoreTemperature],
                "psi": [round(float(v), 2) for v in p.wheelsPressure],
                "brake_c": [round(float(v)) for v in p.brakeTemp],
                "pad_mm": [round(float(v), 1) for v in p.padLife],
            }
        labels = {k: {"text": t, "color": c} for k, (t, c) in
                  ((k, self._label(k)) for k in getattr(vre, "_ui_labels", {}))}
        st["labels"] = labels
        snap = getattr(vre, "_hud_snapshot", None)
        if snap is not None:
            st["hud"] = {k: getattr(snap, k) for k in (
                "corner_display", "phase_name", "volatility_phase", "clean_laps", "target_laps",
                "consistency_pct", "lap_delta_s", "potential_gap_s", "speed_kmh", "gear",
                "tyre_ideal_lo", "tyre_ideal_hi", "tyre_hot_c", "tyre_cold_c", "in_pit",
                "grip_hint", "shift_line", "pit_queue_count", "last_lap_ms")}
        note = getattr(vre, "_last_setup_note", None)
        st["setup"] = {
            "note": {k: (_say_text(v) if isinstance(v, str) else v) for k, v in note.items()} if note else None,
            "base": os.path.basename(self.writer.last_base) if self.writer.last_base else "",
            "auto_tweak": self._auto_tweak_path(),
            "queued": len(getattr(vre, "_pit_tweak_queue", []) or []),
        }
        text = lambda k: _say_text(self._label(k)[0])
        t_lo, t_hi = (st.get("hud", {}).get("tyre_ideal_lo", 70), st.get("hud", {}).get("tyre_ideal_hi", 100))
        tyre_bits = []
        for i, w in enumerate(("LF", "RF", "LR", "RR")):
            if "tyres" in st:
                tyre_bits.append("%s %d\xb0 %.1f" % (w, st["tyres"]["core_c"][i], st["tyres"]["psi"][i]))
        dtext, dcolor = self._label("delta_val")
        st["overlay"] = {
            "status": " · ".join(x for x in (st["status"].upper(), st.get("session", ""), text("stint_line")) if x),
            "delta": dtext, "delta_color": dcolor,
            "tyres": "   ".join(tyre_bits) + ("   (ideal %d-%d\xb0)" % (t_lo, t_hi) if tyre_bits else ""),
            "phase": text("status_line") or text("learn_line"),
            "coach": text("coach_hint") or text("learn_detail"),
            "feedback": text("feedback_line") or (text("cue1") + " " + text("cue2")).strip(),
            "setup": text("setup_line") or text("pit_setup"),
        }
        return st

    def _auto_tweak_path(self):
        track = self.info.static.track if self.info.connected else ""
        if not track:
            return ""
        p = self.writer.resolve_output_path(track)
        return p if p and os.path.isfile(p) else ""


# ------------------------------------------------------------------ outputs

class Speaker:
    """Windows speech through a long-lived PowerShell process (works from WSL and Windows)."""

    def __init__(self, rate: int = 1):
        ps = shutil.which("powershell.exe") or "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
        script = os.path.join(HERE, "speak.ps1")
        if sys.platform != "win32":
            script = subprocess.check_output(["wslpath", "-w", script], text=True).strip()
        self._proc = subprocess.Popen(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Rate", str(rate)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8",
        )

    def say(self, text: str):
        if self._proc.poll() is None:
            try:
                self._proc.stdin.write(text.replace("\n", " ") + "\n")
                self._proc.stdin.flush()
            except OSError:
                pass

    def close(self):
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except OSError:
                pass
            self._proc.terminate()


def start_overlay(port: int):
    ps = shutil.which("powershell.exe") or "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    script = os.path.join(HERE, "overlay.ps1")
    if sys.platform != "win32":
        script = subprocess.check_output(["wslpath", "-w", script], text=True).strip()
    return subprocess.Popen(
        [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-STA", "-WindowStyle", "Hidden",
         "-File", script, "-Port", str(port)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def make_server(mech_state, port: int):
    page = os.path.join(HERE, "dashboard.html")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/state":
                self._send(200, json.dumps(mech_state(), default=str).encode("utf-8"), "application/json")
            elif path in ("/", "/index.html"):
                with open(page, "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

    return ThreadingHTTPServer(("0.0.0.0", port), Handler)


# ------------------------------------------------------------------ main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live ACC mechanic (voice, dashboard, overlay, setup tweaks)")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--hz", type=int, default=50, help="shared-memory poll rate")
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--no-overlay", action="store_true")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--voice-rate", type=int, default=1, help="Windows speech rate, -10..10")
    ap.add_argument("--data", default=DEFAULT_DATA, help="where learned baselines/sessions are kept")
    args = ap.parse_args(argv)

    info = AccInfo(open_source(hz=args.hz))
    mech = Mechanic(info, data_dir=args.data)
    lock = threading.Lock()

    def state():
        with lock:
            return mech.state()

    try:
        server = make_server(state, args.port)
    except OSError:
        print("Port %d is busy — is the mechanic already running? Opening its dashboard." % args.port)
        if not args.no_browser:
            webbrowser.open("http://localhost:%d/" % args.port)
        return 0
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = "http://localhost:%d/" % args.port
    print("ACC mechanic dashboard: %s" % url, flush=True)

    speaker = None if args.no_voice else Speaker(rate=args.voice_rate)
    if speaker:
        mech.on_speak = speaker.say
    overlay = None if args.no_overlay else start_overlay(args.port)
    if not args.no_browser:
        _open_browser(url)

    period = 1.0 / max(10, args.hz)
    last_status = None
    try:
        while True:
            with lock:
                ran = mech.tick()
            st = info.status
            if st != last_status:
                print("ACC: %s%s" % (STATUS_NAMES.get(st, st),
                                     " — %s @ %s" % (info.static.carModel, info.static.track) if info.connected else ""),
                      flush=True)
                last_status = st
            time.sleep(period if ran else period * 2)
    except KeyboardInterrupt:
        print("\nStopping…", flush=True)
    finally:
        with lock:
            mech.shutdown()
        info.close()
        if speaker:
            speaker.close()
        if overlay and overlay.poll() is None:
            overlay.terminate()
        server.shutdown()
    return 0


def _open_browser(url):
    if sys.platform != "win32" and shutil.which("cmd.exe"):
        subprocess.Popen(["cmd.exe", "/c", "start", "", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         cwd="/mnt/c")
    else:
        webbrowser.open(url)


if __name__ == "__main__":
    raise SystemExit(main())
