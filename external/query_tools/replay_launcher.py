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
from http.server import HTTPServer, SimpleHTTPRequestHandler
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


def ensure_viewer_built():
    index = os.path.join(VIEWER_DIST, "index.html")
    if os.path.isfile(index):
        return True
    print("Building replay viewer (first run only)...")
    try:
        subprocess.check_call(
            ["npm", "run", "build"],
            cwd=os.path.join(REPO, "replay-viewer"),
        )
        return os.path.isfile(index)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print("Failed to build viewer: %s" % exc, file=sys.stderr)
        print("Run: cd replay-viewer && npm install && npm run build", file=sys.stderr)
        return False


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

        if path.startswith("/bundles/"):
            self._serve_bundle_file(path[len("/bundles/"):])
            return

        self._serve_viewer_file(path)

    def do_POST(self):
        parsed = urlparse(self.path)
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
    if not os.path.isdir(sessions_root):
        print("Sessions folder not found:\n  %s" % sessions_root, file=sys.stderr)
        print("Set VRE_SESSIONS or pass --sessions-dir", file=sys.stderr)
        return 1

    if not args.no_sync:
        print("Scanning sessions in %s" % sessions_root)
        payload = sync_all_sessions(
            exports_root=args.exports_dir,
            sessions_root=sessions_root,
            force=args.force_sync,
        )
        if payload["count"] == 0:
            print("No VRE sessions found. Drive a stint with Virtual Race Engineer first.")
            return 1
        print("Ready: %d session(s). Latest: %s" % (
            payload["count"], payload.get("latest_id", ""),
        ))

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
    server = HTTPServer(("127.0.0.1", args.port), handler)
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
