#!/usr/bin/env python3
"""One-command VRE replay launcher: sync sessions + serve viewer."""

from __future__ import print_function

import argparse
import json
import mimetypes
import os
import subprocess
import sys
import webbrowser
from functools import partial
import queue
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QT)

from export_replay import (  # noqa: E402
    default_sessions_root,
    sync_all_sessions,
)

VIEWER_DIST = os.path.join(REPO, "replay-viewer", "dist")
EXPORTS_ROOT = os.path.join(REPO, "exports")
DEFAULT_PORT = 8765


def _running_in_wsl():
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def open_browser(url):
    """Open URL in the default browser (Windows browser when running under WSL)."""
    if _running_in_wsl():
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            pass
    try:
        if webbrowser.open(url):
            return True
    except Exception:
        pass
    print("Open this URL in your browser (Windows/Chrome): %s" % url)
    return False


def _viewer_stale(index):
    """True when the built viewer is missing or older than any viewer source file."""
    if not os.path.isfile(index):
        return True
    built = os.path.getmtime(index)
    app = os.path.join(REPO, "replay-viewer")
    paths = [os.path.join(app, f) for f in ("index.html", "package.json", "vite.config.ts")]
    for base, _dirs, files in os.walk(os.path.join(app, "src")):
        paths.extend(os.path.join(base, f) for f in files)
    return any(os.path.isfile(p) and os.path.getmtime(p) > built for p in paths)


def ensure_viewer_built():
    index = os.path.join(VIEWER_DIST, "index.html")
    if not _viewer_stale(index):
        return True
    app = os.path.join(REPO, "replay-viewer")
    print("Building replay viewer (source changed since the last build)...")
    try:
        if not os.path.isdir(os.path.join(app, "node_modules")):
            subprocess.check_call(["npm", "install"], cwd=app)
        subprocess.check_call(
            ["npm", "run", "build"],
            cwd=app,
        )
        return os.path.isfile(index)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print("Failed to build viewer: %s" % exc, file=sys.stderr)
        print("Run: cd replay-viewer && npm install && npm run build", file=sys.stderr)
        return False


class ViewerBus(object):
    """Live link between agents (MCP / HTTP) and open Lap Studio pages."""

    def __init__(self):
        self.lock = threading.Lock()
        self.clients = []
        self.state = {}

    def subscribe(self):
        q = queue.Queue()
        with self.lock:
            self.clients.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

    def publish(self, msg):
        with self.lock:
            for q in list(self.clients):
                q.put(msg)
            return len(self.clients)


VIEWER_BUS = ViewerBus()
VIEWER_COMMANDS = {"seek", "play_range", "pause", "set_mode", "focus_corner", "set_laps", "annotate",
                   "clear_annotations", "open_review", "add_scene", "set_tab", "set_map_color", "reload"}


class ReplayHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Serve viewer static files, /api/sessions, and /bundles/<id>/ exports."""

    exports_root = EXPORTS_ROOT
    viewer_root = VIEWER_DIST

    def log_message(self, fmt, *args):
        if args and "200" in str(args[1] if len(args) > 1 else ""):
            return
        super().log_message(fmt, *args)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/sessions":
            self._serve_sessions_api()
            return

        if path == "/api/viewer/events":
            self._serve_viewer_events()
            return

        if path == "/api/viewer/state":
            self._send_json(VIEWER_BUS.state or {"connected": False})
            return

        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "bundles"] and parts[3] == "reviews":
            bdir = self._bundle_dir(parts[2])
            if bdir is None:
                self._send_json({"ok": False, "error": "bundle not found"}, 404)
                return
            rdir = os.path.join(bdir, "reviews")
            names = sorted(f[:-5] for f in os.listdir(rdir) if f.endswith(".json")) if os.path.isdir(rdir) else []
            self._send_json({"ok": True, "reviews": names})
            return

        if path.startswith("/bundles/"):
            self._serve_bundle_file(path[len("/bundles/"):])
            return

        self._serve_viewer_file(path)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            return json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            return None

    def _serve_viewer_events(self):
        """Server-sent events: commands for the open page."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = VIEWER_BUS.subscribe()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    msg = q.get(timeout=15)
                    self.wfile.write(("data: %s\n\n" % json.dumps(msg)).encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            VIEWER_BUS.unsubscribe(q)

    def _bundle_dir(self, bundle_id):
        if not bundle_id or ".." in bundle_id or "/" in bundle_id:
            return None
        d = os.path.join(self.exports_root, bundle_id)
        return d if os.path.isfile(os.path.join(d, "manifest.json")) else None

    def _handle_viewer_post(self, path):
        data = self._read_json()
        if data is None:
            self.send_error(400, "Invalid JSON")
            return True
        if path == "/api/viewer/command":
            cmd = data.get("cmd")
            if cmd not in VIEWER_COMMANDS:
                self._send_json({"ok": False, "error": "unknown command", "commands": sorted(VIEWER_COMMANDS)}, 400)
                return True
            n = VIEWER_BUS.publish({"cmd": cmd, "args": data.get("args") or {}, "ts": time.time()})
            self._send_json({"ok": True, "delivered_to_pages": n})
            return True
        if path == "/api/viewer/state":
            data["updated"] = time.time()
            VIEWER_BUS.state = data
            self._send_json({"ok": True})
            return True
        parts = path.strip("/").split("/")
        # /api/bundles/<id>/annotations | /api/bundles/<id>/reviews/<name>
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "bundles":
            bdir = self._bundle_dir(parts[2])
            if bdir is None:
                self._send_json({"ok": False, "error": "bundle not found"}, 404)
                return True
            if parts[3] == "annotations":
                anns = data.get("annotations")
                if not isinstance(anns, list):
                    self._send_json({"ok": False, "error": "annotations list required"}, 400)
                    return True
                with open(os.path.join(bdir, "annotations.json"), "w") as fh:
                    json.dump({"annotations": anns}, fh, indent=1)
                VIEWER_BUS.publish({"cmd": "reload", "args": {"what": "annotations"}, "ts": time.time()})
                self._send_json({"ok": True, "count": len(anns)})
                return True
            if parts[3] == "reviews" and len(parts) == 5:
                name = "".join(c for c in parts[4] if c.isalnum() or c in "-_")[:60] or "review"
                repo_root = os.path.dirname(os.path.dirname(QT))
                if repo_root not in sys.path:
                    sys.path.insert(0, repo_root)
                from external.query_tools.coach.reviews import validate

                sources = {}
                for key in ("analysis", "coaching", "track_limits"):
                    fp = os.path.join(bdir, key + ".json")
                    if os.path.isfile(fp):
                        with open(fp) as fh:
                            sources[key] = json.load(fh)
                if "coaching" in sources:
                    sources["habits"] = sources["coaching"].get("habits")
                length = (sources.get("analysis") or {}).get("length_m")
                errs = validate(data, sources, track_length_m=length)
                if errs:
                    self._send_json({"ok": False, "errors": errs}, 422)
                    return True
                os.makedirs(os.path.join(bdir, "reviews"), exist_ok=True)
                with open(os.path.join(bdir, "reviews", name + ".json"), "w") as fh:
                    json.dump(data, fh, indent=1)
                VIEWER_BUS.publish({"cmd": "open_review", "args": {"name": name}, "ts": time.time()})
                self._send_json({"ok": True, "name": name})
                return True
        return False

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/viewer/") or parsed.path.startswith("/api/bundles/"):
            if self._handle_viewer_post(parsed.path):
                return
        if parsed.path != "/coach/ask":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(body)
        except ValueError:
            self.send_error(400, "Invalid JSON")
            return

        coach_dir = os.path.join(QT, "coach")
        if coach_dir not in sys.path:
            sys.path.insert(0, coach_dir)
        from coach_service import ask_coach

        bundle_id = data.get("bundle_id") or data.get("session_id")
        bundle_dir = data.get("bundle_dir") or os.path.join(self.exports_root, bundle_id or "")
        if not os.path.isdir(bundle_dir):
            self.send_error(404, "Bundle not found")
            return

        result = ask_coach(
            bundle_dir,
            data.get("question", ""),
            corner=data.get("corner"),
            spline=data.get("spline"),
            lap=data.get("lap"),
        )
        self._send_json(result)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_sessions_api(self):
        index_path = os.path.join(self.exports_root, "sessions_index.json")
        if not os.path.isfile(index_path):
            self._send_json({"sessions": [], "count": 0, "latest_id": None})
            return
        with open(index_path, "r") as fh:
            data = json.load(fh)
        self._send_json(data)

    def _serve_bundle_file(self, rel):
        rel = rel.lstrip("/")
        if ".." in rel.split("/"):
            self.send_error(403)
            return
        full = os.path.join(self.exports_root, rel)
        if not os.path.isfile(full):
            self.send_error(404, "Bundle file not found: %s" % rel)
            return
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        try:
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            self.send_error(500)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _serve_viewer_file(self, path):
        if path in ("", "/"):
            path = "/index.html"
        rel = path.lstrip("/")
        if ".." in rel.split("/"):
            self.send_error(403)
            return
        full = os.path.join(self.viewer_root, rel)
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            full = os.path.join(self.viewer_root, "index.html")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        try:
            with open(full, "rb") as fh:
                data = fh.read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _merge_lab_bundles(exports_dir):
    """Keep Lap Studio (replay) bundles in sessions_index.json after an AC session sync."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(QT)))
        from external.query_tools.acc_replay_bundle import _refresh_index
        from pathlib import Path

        _refresh_index(Path(exports_dir))
    except Exception as exc:  # never block the viewer
        print("note: could not merge replay bundles: %s" % exc)


def _lab_bundle_count(exports_dir):
    idx = os.path.join(exports_dir, "sessions_index.json")
    if not os.path.isfile(idx):
        return 0
    with open(idx) as fh:
        return sum(1 for s_ in json.load(fh).get("sessions") or [] if s_.get("schema") == "vre.replay_bundle.acc.v2")


def main():
    parser = argparse.ArgumentParser(
        description="Sync VRE sessions and launch replay viewer",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--sessions-dir", default="", help="Override VRE sessions root")
    parser.add_argument("--exports-dir", default=EXPORTS_ROOT)
    parser.add_argument("--no-open", action="store_true", help="Do not open browser")
    parser.add_argument("--no-sync", action="store_true", help="Skip session sync")
    parser.add_argument("--force-sync", action="store_true", help="Re-export all sessions")
    parser.add_argument("--sync-only", action="store_true", help="Sync and exit")
    args = parser.parse_args()

    sessions_root = args.sessions_dir or default_sessions_root()
    lab_only = not os.path.isdir(sessions_root)
    if lab_only:
        print("AC sessions folder not found (%s); serving replay bundles only." % sessions_root)
        args.no_sync = True

    if not args.no_sync:
        print("Scanning sessions in %s" % sessions_root)
        payload = sync_all_sessions(
            exports_root=args.exports_dir,
            sessions_root=sessions_root,
            force=args.force_sync,
        )
        _merge_lab_bundles(args.exports_dir)
        if payload["count"] == 0 and not _lab_bundle_count(args.exports_dir):
            print("No VRE sessions found. Drive a stint with Virtual Race Engineer first.")
            return 1
        print("Ready: %d session(s). Latest: %s" % (
            payload["count"], payload.get("latest_id", ""),
        ))

    if lab_only:
        _merge_lab_bundles(args.exports_dir)
    if args.sync_only:
        return 0

    if not ensure_viewer_built():
        return 1

    handler = partial(
        ReplayHTTPRequestHandler,
    )
    ReplayHTTPRequestHandler.exports_root = args.exports_dir
    ReplayHTTPRequestHandler.viewer_root = VIEWER_DIST

    url = "http://127.0.0.1:%d/" % args.port
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError:
        # already running (e.g. the launcher was double-clicked twice): just show it
        print("Replay viewer is already running: %s" % url)
        if not args.no_open:
            open_browser(url)
        return 0
    server.daemon_threads = True
    print("\nReplay viewer: %s" % url)
    print("Press Ctrl+C to stop.\n")

    if not args.no_open:
        open_browser(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
