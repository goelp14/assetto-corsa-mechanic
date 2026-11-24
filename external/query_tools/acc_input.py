"""Python handle on ``acc_input.ps1``: focus ACC, screenshot it, click, press keys (Windows or WSL)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))

VK = {"F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75, "F7": 0x76,
      "SPACE": 0x20, "ESC": 0x1B, "LEFT": 0x25, "RIGHT": 0x27, "UP": 0x26, "DOWN": 0x28}


def _winpath(p: str) -> str:
    if sys.platform == "win32":
        return p
    return subprocess.check_output(["wslpath", "-w", p], text=True).strip()


class AccWindow:
    def __init__(self):
        ps = shutil.which("powershell.exe") or "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
        self._p = subprocess.Popen(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", _winpath(os.path.join(HERE, "acc_input.ps1"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )

    def _cmd(self, line: str) -> str:
        self._p.stdin.write(line + "\n")
        self._p.stdin.flush()
        out = self._p.stdout.readline().strip()
        if out.startswith("ERR"):
            raise RuntimeError(out[4:])
        return out

    def focus(self) -> bool:
        return self._cmd("focus").endswith("True")

    def restore(self):
        self._cmd("restore")

    def size(self):
        _, w, h = self._cmd("size").split()
        return int(w), int(h)

    def shot(self, path: str):
        self._cmd("shot %s" % _winpath(os.path.abspath(path)))
        return path

    def move(self, x: float, y: float):
        self._cmd("move %d %d" % (x, y))

    def click(self, x: float, y: float):
        self._cmd("click %d %d" % (x, y))

    def key(self, name: str, hold_ms: int = 60):
        self._cmd("key %x %d" % (VK.get(name.upper(), 0) or int(name, 16), hold_ms))

    def chord(self, mods: str, name: str):
        """Modifier(s) + key, e.g. chord("CTRL+SHIFT", "F9")."""
        table = {"CTRL": 0x11, "SHIFT": 0x10, "ALT": 0x12}
        mv = "+".join("%x" % table[m] for m in mods.upper().split("+"))
        keys = dict(VK, F9=0x78, F10=0x79, F11=0x7A, F12=0x7B, HOME=0x24, END=0x23)
        self._cmd("chord %s %x" % (mv, keys.get(name.upper(), 0) or int(name, 16)))

    def foreground(self) -> int:
        """Handle of the window in front right now (e.g. the browser running Lap Studio)."""
        return int(self._cmd("fg").split()[1])

    def activate(self, hwnd: int) -> bool:
        return self._cmd("activate %d" % hwnd).endswith("True")

    def close(self):
        if self._p.poll() is None:
            try:
                self._p.stdin.close()
            except OSError:
                pass
            self._p.terminate()
