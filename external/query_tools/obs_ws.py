"""Tiny OBS WebSocket v5 client (stdlib only): start/stop recording and get the file path.

Enable in OBS: Tools → WebSocket Server Settings → Enable WebSocket server (port 4455).
If authentication is on, put the password in the environment variable ``VRE_OBS_PASSWORD``
(the tool never stores or prints it).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
import uuid
from typing import Any, Dict, Optional


class ObsError(RuntimeError):
    pass


PASSWORD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "obs_password.txt")


def _stored_password() -> str:
    """$VRE_OBS_PASSWORD, else the first line of data/obs_password.txt (git-ignored), else ''."""
    env = os.environ.get("VRE_OBS_PASSWORD", "")
    if env:
        return env
    try:
        with open(PASSWORD_FILE, "r", encoding="utf-8-sig") as fh:
            return fh.readline().strip()
    except OSError:
        return ""


class ObsClient:
    def __init__(self, host="127.0.0.1", port=4455, password: Optional[str] = None, timeout=5.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.password = _stored_password() if password is None else password
        self._sock: Optional[socket.socket] = None
        self._buf = b""
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._cond = threading.Condition()
        self.events = []          # (wall_time, eventType, eventData)
        self._reader: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()

    # ---- websocket framing ----
    def _send_frame(self, text: str):
        payload = text.encode("utf-8")
        head = bytearray([0x81])
        n = len(payload)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        mask = os.urandom(4)
        head += mask
        frame = bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self._send_lock:
            self._sock.sendall(frame)

    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ObsError("OBS closed the connection")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _recv_frame(self) -> Optional[str]:
        b1, b2 = self._recv_exact(2)
        op, n = b1 & 0x0F, b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self._recv_exact(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self._recv_exact(8))[0]
        if b2 & 0x80:
            mask = self._recv_exact(4)
            data = bytes(b ^ mask[i % 4] for i, b in enumerate(self._recv_exact(n)))
        else:
            data = self._recv_exact(n)
        if op == 0x8:
            raise ObsError("OBS closed the connection")
        if op == 0x9:   # ping → pong
            return None
        return data.decode("utf-8") if op in (0x1, 0x0) else None

    # ---- protocol ----
    def connect(self):
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as exc:
            raise ObsError("Can't reach OBS on port %d — is OBS open with its WebSocket server enabled "
                           "(Tools → WebSocket Server Settings)?" % self.port) from exc
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall((
            "GET / HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Protocol: obswebsocket.json\r\n\r\n"
            % (self.host, self.port, key)).encode())
        while b"\r\n\r\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ObsError("OBS refused the WebSocket handshake")
            self._buf += chunk
        head, self._buf = self._buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ObsError("OBS refused the WebSocket handshake")
        hello = json.loads(self._recv_frame())
        ident: Dict[str, Any] = {"rpcVersion": 1, "eventSubscriptions": 1 << 6}   # Outputs events
        auth = hello.get("d", {}).get("authentication")
        if auth:
            if not self.password:
                raise ObsError("OBS asks for a password: paste it into data/obs_password.txt, or untick "
                               "'Enable Authentication' in OBS's WebSocket settings")
            secret = base64.b64encode(hashlib.sha256((self.password + auth["salt"]).encode()).digest()).decode()
            ident["authentication"] = base64.b64encode(
                hashlib.sha256((secret + auth["challenge"]).encode()).digest()).decode()
        self._send_frame(json.dumps({"op": 1, "d": ident}))
        msg = json.loads(self._recv_frame() or "{}")
        if msg.get("op") != 2:
            raise ObsError("OBS rejected the login (wrong VRE_OBS_PASSWORD?)")
        self._sock.settimeout(None)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        try:
            while True:
                text = self._recv_frame()
                if not text:
                    continue
                msg = json.loads(text)
                op, d = msg.get("op"), msg.get("d", {})
                with self._cond:
                    if op == 7:
                        self._pending[d.get("requestId")] = d
                    elif op == 5:
                        self.events.append((time.time(), d.get("eventType"), d.get("eventData", {})))
                    self._cond.notify_all()
        except (ObsError, OSError, ValueError):
            with self._cond:
                self._cond.notify_all()

    def request(self, rtype: str, data: Optional[dict] = None, timeout=10.0) -> dict:
        rid = uuid.uuid4().hex
        body = {"requestType": rtype, "requestId": rid}
        if data:
            body["requestData"] = data
        self._send_frame(json.dumps({"op": 6, "d": body}))
        end = time.time() + timeout
        with self._cond:
            while rid not in self._pending:
                left = end - time.time()
                if left <= 0:
                    raise ObsError("OBS did not answer %s" % rtype)
                self._cond.wait(left)
            resp = self._pending.pop(rid)
        st = resp.get("requestStatus", {})
        if not st.get("result"):
            raise ObsError("%s failed: %s" % (rtype, st.get("comment") or st.get("code")))
        return resp.get("responseData") or {}

    def wait_event(self, etype: str, pred=lambda d: True, timeout=10.0):
        end = time.time() + timeout
        with self._cond:
            while True:
                for i, (t, et, d) in enumerate(self.events):
                    if et == etype and pred(d):
                        self.events.pop(i)
                        return t, d
                left = end - time.time()
                if left <= 0:
                    return None
                self._cond.wait(left)

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
