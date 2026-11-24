"""Bind ACC's menu actions (which drive the replay bar) to keyboard chords in ACC's own controls.json.

ACC has no dedicated replay play/seek action; its replay bar runs on the generic menu actions
(``Forward`` = pause/play, ``CycleLeft``/``CycleRight`` = −5/+5 s, ``Left``/``Right`` = speed …),
which are normally only on a wheel/gamepad. This adds keyboard bindings for them, using ACC's own
binding format, on Ctrl+Shift chords nothing in ACC uses by default. ``Backward`` (quit replay) is
deliberately never bound.

    python -m external.query_tools.acc_bindings apply    # ACC must be closed; backs up first
    python -m external.query_tools.acc_bindings remove
    python -m external.query_tools.acc_bindings show
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

from external.acc_mechanic.acc_setup import acc_documents

TAG_KEYS = {  # action -> Unreal key name (always with Ctrl+Shift)
    "Forward": "F9",
    "CycleLeft": "F10",
    "CycleRight": "F11",
    "Left": "F12",
    "Right": "Home",
    "Gamepad3": "End",
}
# Windows virtual-key codes for the same keys (used by acc_input to press them)
VK = {"F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B, "Home": 0x24, "End": 0x23}


def controls_path() -> str:
    docs = acc_documents()
    if not docs:
        raise FileNotFoundError("ACC documents folder not found")
    return os.path.join(docs, "Config", "controls.json")


def acc_running() -> bool:
    try:
        out = subprocess.check_output(["tasklist.exe", "/FI", "IMAGENAME eq AC2-Win64-Shipping.exe"], text=True,
                                      stderr=subprocess.DEVNULL)
        return "AC2-Win64-Shipping" in out
    except (OSError, subprocess.CalledProcessError):
        return False


def _load(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def _save(path, doc):
    # ACC writes tab-indented JSON with CRLF; keep that style
    text = json.dumps(doc, indent="\t", ensure_ascii=False).replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _entry(action, key):
    return {"actionType": action, "key": {"key": key, "bShift": True, "bCtrl": True, "bAlt": False, "bCmd": False}}


def apply(force=False) -> str:
    if acc_running() and not force:
        raise RuntimeError("ACC is running — close it first (it may rewrite controls.json on exit)")
    path = controls_path()
    backup = path + ".vre-backup-%s" % time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, backup)
    doc = _load(path)
    kb = doc.setdefault("keyboardSettings", {})
    ui = [e for e in kb.get("uICommandButtonList", []) if e.get("actionType") not in TAG_KEYS]
    ui += [_entry(a, k) for a, k in TAG_KEYS.items()]
    kb["uICommandButtonList"] = ui
    _save(path, doc)
    return backup


def remove() -> None:
    path = controls_path()
    doc = _load(path)
    kb = doc.get("keyboardSettings", {})
    kb["uICommandButtonList"] = [e for e in kb.get("uICommandButtonList", [])
                                 if not (e.get("actionType") in TAG_KEYS and e.get("key", {}).get("bCtrl")
                                         and e.get("key", {}).get("bShift"))]
    _save(path, doc)


def show() -> list:
    return _load(controls_path()).get("keyboardSettings", {}).get("uICommandButtonList", [])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "apply":
        print("backup:", apply())
    elif cmd == "remove":
        remove()
        print("removed")
    for e in show():
        print(e)
