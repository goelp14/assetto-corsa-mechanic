"""ACC shared memory → an object shaped like AC's ``sim_info.info`` (physics / graphics / static).

Two sources:
- ``WindowsSource``: native Windows Python opens the named mappings directly.
- ``BridgeSource``: inside WSL, ``bridge.ps1`` (Windows PowerShell) streams the raw pages over a pipe.

Struct layouts come from ``external/query_tools/acc_ingest/shm_structs.py``; wide-char strings are
re-declared as UTF-16 code units so the same layout parses on Linux, where ``c_wchar`` is 4 bytes.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import struct
import subprocess
import sys
import threading
import time
from typing import Optional

from external.query_tools.acc_ingest import shm_structs as _src

PHYS_SIZE, GFX_SIZE, STATIC_SIZE = 800, 1588, 820
STATUS_OFF, STATUS_REPLAY, STATUS_LIVE, STATUS_PAUSE = 0, 1, 2, 3


def _portable(cls):
    """Copy a ctypes Structure, turning c_wchar arrays into c_uint16 arrays (Windows wchar_t)."""
    fields, strings = [], set()
    for name, typ in cls._fields_:
        if issubclass(typ, ctypes.Array) and typ._type_ is ctypes.c_wchar:
            fields.append((name, ctypes.c_uint16 * typ._length_))
            strings.add(name)
        else:
            fields.append((name, typ))
    new = type(cls.__name__, (ctypes.Structure,), {"_pack_": 4, "_layout_": "ms", "_fields_": fields})
    new._strings = strings
    return new


Physics = _portable(_src.SPageFilePhysics)
Graphics = _portable(_src.SPageFileGraphic)
Static = _portable(_src.SPageFileStatic)
assert (ctypes.sizeof(Physics), ctypes.sizeof(Graphics), ctypes.sizeof(Static)) == (PHYS_SIZE, GFX_SIZE, STATIC_SIZE)


def _wstr(arr) -> str:
    return bytes(arr).decode("utf-16-le", "ignore").split("\x00", 1)[0]


class Page:
    """Attribute view over a parsed page: strings decoded, everything else passed through."""

    def __init__(self, raw: ctypes.Structure):
        object.__setattr__(self, "_raw", raw)

    def __getattr__(self, name):
        raw = object.__getattribute__(self, "_raw")
        value = getattr(raw, name)
        if name in type(raw)._strings:
            return _wstr(value)
        return value


class GraphicsPage(Page):
    """ACC stores one coordinate triple per car; AC apps expect the player's triple."""

    def __getattr__(self, name):
        if name == "carCoordinates":
            raw = object.__getattribute__(self, "_raw")
            idx = 0
            for i in range(max(1, min(60, int(raw.activeCars)))):
                if int(raw.carID[i]) == int(raw.playerCarID):
                    idx = i
                    break
            c = raw.carCoordinates[idx]
            return (float(c[0]), float(c[1]), float(c[2]))
        return Page.__getattr__(self, name)


class AccInfo:
    """Drop-in for AC's ``sim_info.info``; ``update()`` pulls the latest pages from a source."""

    def __init__(self, source):
        self.source = source
        self.physics = Page(Physics())
        self.graphics = GraphicsPage(Graphics())
        self.static = Page(Static())
        self.connected = False

    def update(self) -> bool:
        """True when ACC is running and a fresh physics/graphics pair was read."""
        pages = self.source.read()
        if pages is None:
            self.connected = False
            return False
        phys, gfx, stat = pages
        self.physics = Page(Physics.from_buffer_copy(phys))
        self.graphics = GraphicsPage(Graphics.from_buffer_copy(gfx))
        if stat:
            self.static = Page(Static.from_buffer_copy(stat))
        self.connected = True
        return True

    @property
    def status(self) -> int:
        return int(self.graphics.status) if self.connected else -1

    def close(self):
        self.source.close()


class WindowsSource:
    """Native Windows: open ACC's named mappings with mmap."""

    def __init__(self):
        import mmap  # noqa: F401  (Windows tagname support)
        self._maps = None

    def _open(self):
        import mmap
        try:
            self._maps = (
                mmap.mmap(-1, PHYS_SIZE, "Local\\acpmf_physics", access=mmap.ACCESS_READ),
                mmap.mmap(-1, GFX_SIZE, "Local\\acpmf_graphics", access=mmap.ACCESS_READ),
                mmap.mmap(-1, STATIC_SIZE, "Local\\acpmf_static", access=mmap.ACCESS_READ),
            )
        except OSError:
            self._maps = None

    def read(self):
        if self._maps is None:
            self._open()
            if self._maps is None:
                return None
        p, g, s = (bytes(m[:]) for m in self._maps)
        if not any(s[:30]):   # mapping exists but ACC never wrote it (game not running)
            return None
        return p, g, s

    def close(self):
        for m in self._maps or ():
            m.close()


def _powershell() -> Optional[str]:
    for name in ("powershell.exe", "pwsh.exe"):
        path = shutil.which(name)
        if path:
            return path
    for path in ("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",):
        if os.path.exists(path):
            return path
    return None


def _winpath(path: str) -> str:
    return subprocess.check_output(["wslpath", "-w", path], text=True).strip()


class BridgeSource:
    """WSL: run bridge.ps1 under Windows PowerShell and keep the latest pages it streams."""

    STALE_S = 1.5

    def __init__(self, hz: int = 50):
        ps = _powershell()
        if not ps:
            raise RuntimeError("powershell.exe not found — is this WSL with Windows interop enabled?")
        script = _winpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge.ps1"))
        self._proc = subprocess.Popen(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, "-Hz", str(int(hz))],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self._lock = threading.Lock()
        self._dyn = None
        self._static = None
        self._dyn_t = 0.0
        self._fresh = False
        self._running = False
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self._proc.stdout.read(n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return buf

    def _reader(self):
        try:
            while True:
                head = self._read_exact(9)
                if head[:4] != b"VRE1":   # resync on garbage
                    continue
                kind = head[4]
                n = struct.unpack("<I", head[5:9])[0]
                payload = self._read_exact(n) if n else b""
                with self._lock:
                    if kind == 0:
                        self._running = False
                    elif kind == 1 and n == PHYS_SIZE + GFX_SIZE:
                        self._dyn, self._dyn_t, self._fresh, self._running = payload, time.time(), True, True
                    elif kind == 2 and n == STATIC_SIZE:
                        self._static = payload
        except (EOFError, ValueError, OSError):
            with self._lock:
                self._running = False

    def read(self):
        with self._lock:
            if not self._running or self._dyn is None or time.time() - self._dyn_t > self.STALE_S:
                return None
            if not self._static or not any(self._static[:30]):
                return None
            d = self._dyn
            self._fresh = False
            return d[:PHYS_SIZE], d[PHYS_SIZE:], self._static

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None

    def close(self):
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()


def open_source(hz: int = 50):
    if sys.platform == "win32":
        return WindowsSource()
    return BridgeSource(hz=hz)
