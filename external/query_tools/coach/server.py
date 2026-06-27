"""Lightweight HTTP API for replay viewer coach chat."""

from __future__ import print_function

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

COACH_DIR = os.path.dirname(os.path.abspath(__file__))
QT = os.path.dirname(COACH_DIR)
REPO = os.path.dirname(QT)
EXPORTS = os.path.join(REPO, "exports")

if QT not in sys.path:
    sys.path.insert(0, QT)
if COACH_DIR not in sys.path:
    sys.path.insert(0, COACH_DIR)

from coach_service import ask_coach  # noqa: E402


def _resolve_bundle(bundle_id):
    path = os.path.join(EXPORTS, bundle_id)
    if os.path.isdir(path):
        return path
    index_path = os.path.join(EXPORTS, "sessions_index.json")
    if os.path.isfile(index_path):
        with open(index_path) as fh:
            idx = json.load(fh)
        for entry in idx.get("sessions") or []:
            if entry.get("session_id") == bundle_id:
                rel = entry.get("bundle_path") or entry.get("bundle_url", "").lstrip("/bundles/")
                if rel:
                    return os.path.join(EXPORTS, rel)
    return None


class CoachHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path != "/coach/ask":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(body)
        except ValueError:
            self.send_error(400, "Invalid JSON")
            return

        bundle_id = data.get("bundle_id") or data.get("session_id")
        bundle_dir = data.get("bundle_dir") or _resolve_bundle(bundle_id)
        if not bundle_dir or not os.path.isdir(bundle_dir):
            self.send_error(404, "Bundle not found")
            return

        result = ask_coach(
            bundle_dir,
            data.get("question", ""),
            corner=data.get("corner"),
            spline=data.get("spline"),
            lap=data.get("lap"),
        )
        payload = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print("[coach] %s" % (fmt % args))


def main():
    port = int(os.environ.get("VRE_COACH_PORT", "8787"))
    server = HTTPServer(("127.0.0.1", port), CoachHandler)
    print("Coach API listening on http://127.0.0.1:%d/coach/ask" % port)
    server.serve_forever()


if __name__ == "__main__":
    main()
