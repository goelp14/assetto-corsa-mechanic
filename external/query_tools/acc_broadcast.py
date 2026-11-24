"""Minimal client for ACC's broadcasting API (UDP, protocol v4).

Enabled in ``Documents/Assetto Corsa Competizione/Config/broadcasting.json`` (port, connection
password). Works in live sessions *and* while a saved replay plays: the realtime update then
carries the replay clock, and per-car updates carry each car's lap count and current lap time.
"""

from __future__ import annotations

import io
import json
import os
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

REGISTER, UNREGISTER, REQUEST_ENTRY_LIST, REQUEST_TRACK_DATA = 1, 9, 10, 11
CHANGE_HUD_PAGE, CHANGE_FOCUS = 49, 50
R_REGISTRATION, R_REALTIME, R_CAR, R_ENTRY_LIST, R_TRACK, R_ENTRY_CAR, R_EVENT = 1, 2, 3, 4, 5, 6, 7


class _R:
    def __init__(self, data: bytes):
        self.b = io.BytesIO(data)

    def u8(self):
        return self.b.read(1)[0]

    def u16(self):
        return struct.unpack("<H", self.b.read(2))[0]

    def i32(self):
        return struct.unpack("<i", self.b.read(4))[0]

    def f32(self):
        return struct.unpack("<f", self.b.read(4))[0]

    def s(self):
        n = self.u16()
        return self.b.read(n).decode("utf-8", "replace")


def _w_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<H", len(b)) + b


@dataclass
class Lap:
    ms: int
    invalid: bool
    outlap: bool
    inlap: bool


def _lap(r: _R) -> Lap:
    ms = r.i32()
    r.u16(), r.u16()
    for _ in range(r.u8()):
        r.i32()
    invalid, _valid_best, outlap, inlap = r.u8(), r.u8(), r.u8(), r.u8()
    return Lap(ms, bool(invalid), bool(outlap), bool(inlap))


@dataclass
class Realtime:
    session_type: int
    phase: int
    session_time_s: float
    focused_car: int
    camera_set: str
    camera: str
    hud_page: str
    replay: bool
    replay_time_s: Optional[float]
    replay_remaining_s: Optional[float]


@dataclass
class CarUpdate:
    car_index: int
    gear: int
    x: float
    y: float
    yaw: float
    kmh: int
    spline: float
    laps: int
    current: Lap
    last: Lap
    best: Lap


def parse_realtime(data: bytes) -> Realtime:
    r = _R(data[1:])
    r.u16(), r.u16()
    st, ph = r.u8(), r.u8()
    stime, _end = r.f32(), r.f32()
    focus = r.i32()
    cset, cam, hud = r.s(), r.s(), r.s()
    rep = r.u8() > 0
    rt = rr = None
    if rep:
        rt, rr = r.f32() / 1000.0, r.f32() / 1000.0
    return Realtime(st, ph, stime / 1000.0, focus, cset, cam, hud, rep, rt, rr)


def parse_car(data: bytes) -> CarUpdate:
    r = _R(data[1:])
    idx = r.u16()
    r.u16(), r.u8()
    gear = r.u8() - 2
    x, y, yaw = r.f32(), r.f32(), r.f32()
    r.u8()
    kmh = r.u16()
    r.u16(), r.u16(), r.u16()
    spline = r.f32()
    laps = r.u16()
    r.i32()
    best, last, cur = _lap(r), _lap(r), _lap(r)
    return CarUpdate(idx, gear, x, y, yaw, kmh, spline, laps, cur, last, best)


def parse_track(data: bytes) -> dict:
    r = _R(data[1:])
    r.i32()
    name, tid, meters = r.s(), r.i32(), r.i32()
    sets = {}
    for _ in range(r.u8()):
        cs = r.s()
        sets[cs] = [r.s() for _ in range(r.u8())]
    hud = [r.s() for _ in range(r.u8())]
    return {"track": name, "track_id": tid, "length_m": meters, "cameras": sets, "hud_pages": hud}


def broadcasting_config() -> dict:
    """Port and connection password from ACC's broadcasting.json (UTF-16 on disk)."""
    from external.acc_mechanic.acc_setup import acc_documents

    docs = acc_documents()
    cfg = {"port": 9000, "password": "asd", "command_password": ""}
    if not docs:
        return cfg
    path = os.path.join(docs, "Config", "broadcasting.json")
    try:
        raw = open(path, "rb").read()
        text = raw.decode("utf-16-le" if raw[1:2] == b"\x00" else "utf-8", "ignore").lstrip("﻿")
        d = json.loads(text)
        cfg["port"] = int(d.get("updListenerPort") or d.get("udpListenerPort") or 9000)
        cfg["password"] = d.get("connectionPassword", "asd")
        cfg["command_password"] = d.get("commandPassword", "")
    except (OSError, ValueError):
        pass
    return cfg


@dataclass
class Snapshot:
    wall: float
    realtime: Optional[Realtime]
    cars: Dict[int, CarUpdate] = field(default_factory=dict)


class BroadcastClient:
    """Register with ACC and keep the latest realtime + per-car updates (background thread)."""

    def __init__(self, host="127.0.0.1", port=None, password=None, command_password=None,
                 interval_ms=50, name="vre-capture"):
        cfg = broadcasting_config()
        self.addr = (host, port or cfg["port"])
        self.password = cfg["password"] if password is None else password
        self.command_password = cfg["command_password"] if command_password is None else command_password
        self.interval_ms = interval_ms
        self.name = name
        self.conn_id: Optional[int] = None
        self.readonly = True
        self.error = ""
        self.track: Optional[dict] = None
        self.realtime: Optional[Realtime] = None
        self.realtime_wall = 0.0
        self.cars: Dict[int, CarUpdate] = {}
        self.listeners: List = []
        self._lock = threading.Lock()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(0.5)
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _send(self, payload: bytes):
        self._sock.sendto(payload, self.addr)

    def connect(self, timeout=5.0) -> bool:
        self._thread.start()
        msg = (bytes([REGISTER, 4]) + _w_str(self.name) + _w_str(self.password)
               + struct.pack("<i", self.interval_ms) + _w_str(self.command_password))
        end = time.time() + timeout
        while time.time() < end and self.conn_id is None:
            self._send(msg)
            time.sleep(0.5)
        if self.conn_id is not None:
            self._send(bytes([REQUEST_ENTRY_LIST]) + struct.pack("<i", self.conn_id))
            self._send(bytes([REQUEST_TRACK_DATA]) + struct.pack("<i", self.conn_id))
        return self.conn_id is not None

    def _loop(self):
        while not self._stop:
            try:
                data, _ = self._sock.recvfrom(65535)
            except (socket.timeout, OSError):
                continue
            if not data:
                continue
            kind = data[0]
            now = time.monotonic()
            try:
                if kind == R_REGISTRATION:
                    r = _R(data[1:])
                    cid, ok, ro, err = r.i32(), r.u8(), r.u8(), r.s()
                    if ok:
                        self.conn_id, self.readonly = cid, bool(ro)
                    self.error = err
                elif kind == R_REALTIME:
                    rt = parse_realtime(data)
                    with self._lock:
                        self.realtime, self.realtime_wall = rt, now
                    for fn in list(self.listeners):
                        fn(self.snapshot())
                elif kind == R_CAR:
                    cu = parse_car(data)
                    with self._lock:
                        self.cars[cu.car_index] = cu
                elif kind == R_TRACK:
                    self.track = parse_track(data)
            except (struct.error, IndexError, ValueError):
                continue

    def fresh(self, max_age_s: float = 2.0) -> bool:
        """True while ACC is still sending realtime updates on this connection (it drops them on a level load)."""
        with self._lock:
            return self.realtime is not None and time.monotonic() - self.realtime_wall < max_age_s

    def snapshot(self) -> Snapshot:
        with self._lock:
            return Snapshot(self.realtime_wall, self.realtime, dict(self.cars))

    def focus(self, car_index: int):
        if self.conn_id is not None:
            self._send(bytes([CHANGE_FOCUS]) + struct.pack("<i", self.conn_id) + bytes([1])
                       + struct.pack("<H", car_index) + bytes([0]))

    def set_camera(self, camera_set: str, camera: str):
        if self.conn_id is not None:
            self._send(bytes([CHANGE_FOCUS]) + struct.pack("<i", self.conn_id) + bytes([0, 1])
                       + _w_str(camera_set) + _w_str(camera))

    def close(self):
        if self.conn_id is not None:
            try:
                self._send(bytes([UNREGISTER]) + struct.pack("<i", self.conn_id))
            except OSError:
                pass
        self._stop = True
        self._sock.close()
