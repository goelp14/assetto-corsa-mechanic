"""Install/uninstall UE4SS + the VREReplayControl script into ACC, and talk to it.

    python -m external.query_tools.acc_ue4ss install --zip UE4SS_v4.0.0.zip   # ACC must be closed
    python -m external.query_tools.acc_ue4ss status
    python -m external.query_tools.acc_ue4ss uninstall                         # ACC must be closed

Install copies ``dwmapi.dll`` and ``ue4ss/`` into ACC's ``AC2/Binaries/Win64``, disables every bundled
UE4SS example mod (console enabler, cheat manager, keybinds …), enables only VREReplayControl, and
writes ``vre_ue4ss_install.json`` listing exactly what was added so uninstall removes only that.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import sys
import time
import zipfile
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
MOD_SRC = os.path.join(os.path.dirname(HERE), "acc_ue4ss", "VREReplayControl")
MANIFEST = "vre_ue4ss_install.json"


def game_bin_dir() -> str:
    cands = []
    if sys.platform == "win32":
        cands.append(r"C:\Program Files (x86)\Steam\steamapps\common\Assetto Corsa Competizione\AC2\Binaries\Win64")
    else:
        cands.append("/mnt/c/Program Files (x86)/Steam/steamapps/common/Assetto Corsa Competizione/AC2/Binaries/Win64")
        cands += glob.glob("/mnt/*/SteamLibrary/steamapps/common/Assetto Corsa Competizione/AC2/Binaries/Win64")
    env = os.environ.get("VRE_ACC_BIN")
    if env:
        cands.insert(0, env)
    for c in cands:
        if os.path.isfile(os.path.join(c, "AC2-Win64-Shipping.exe")):
            return c
    raise FileNotFoundError("ACC's AC2/Binaries/Win64 folder not found (set VRE_ACC_BIN)")


def _acc_running() -> bool:
    from .acc_bindings import acc_running
    return acc_running()


def install(zip_path: str) -> dict:
    if _acc_running():
        raise RuntimeError("Close ACC first")
    dest = game_bin_dir()
    if os.path.exists(os.path.join(dest, "dwmapi.dll")) and not os.path.exists(os.path.join(dest, MANIFEST)):
        raise RuntimeError("A dwmapi.dll already exists in ACC's folder (another mod?) — not overwriting")
    added = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if not (name == "dwmapi.dll" or name.startswith("ue4ss/")):
                continue
            target = os.path.join(dest, *name.split("/"))
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            added.append(name)
    mods = os.path.join(dest, "ue4ss", "Mods")
    shutil.copytree(MOD_SRC, os.path.join(mods, "VREReplayControl"), dirs_exist_ok=True)
    os.makedirs(os.path.join(mods, "VREReplayControl", "ipc"), exist_ok=True)
    # only our mod runs: every bundled example off
    with open(os.path.join(mods, "mods.txt"), "w", newline="\r\n") as fh:
        for m in ("CheatManagerEnablerMod", "ConsoleCommandsMod", "ConsoleEnablerMod", "SplitScreenMod",
                  "LineTraceMod", "BPML_GenericFunctions", "BPModLoaderMod", "Keybinds"):
            fh.write("%s : 0\n" % m)
        fh.write("VREReplayControl : 1\n")
    rec = {"installed": time.strftime("%Y-%m-%dT%H:%M:%S"), "zip": os.path.basename(zip_path),
           "paths": ["dwmapi.dll", "ue4ss"]}
    with open(os.path.join(dest, MANIFEST), "w") as fh:
        json.dump(rec, fh, indent=1)
    return {"dest": dest, "files": len(added)}


def uninstall() -> None:
    if _acc_running():
        raise RuntimeError("Close ACC first")
    dest = game_bin_dir()
    if not os.path.exists(os.path.join(dest, MANIFEST)):
        raise RuntimeError("No VRE UE4SS install found")
    os.remove(os.path.join(dest, "dwmapi.dll"))
    shutil.rmtree(os.path.join(dest, "ue4ss"), ignore_errors=True)
    os.remove(os.path.join(dest, MANIFEST))


class ReplayControl:
    """Send commands to VREReplayControl and read its status (file IPC)."""

    def __init__(self):
        self.dir = os.path.join(game_bin_dir(), "ue4ss", "Mods", "VREReplayControl", "ipc")
        self._id = int(time.time() * 1000) % 1_000_000_000

    def _status_raw(self) -> dict:
        try:
            with open(os.path.join(self.dir, "status.txt"), encoding="utf-8", errors="replace") as fh:
                kv = dict(line.rstrip("\n").split("=", 1) for line in fh if "=" in line)
        except OSError:
            return {}
        out = dict(kv)
        for k in ("current_s", "total_s", "start_s", "clock"):
            if k in out:
                try:
                    out[k] = float(out[k])
                except ValueError:
                    pass
        out["in_replay"] = kv.get("in_replay") == "true"
        out["last_id"] = int(kv.get("last_id", "-1") or -1)
        return out

    def send(self, verb: str, arg: str = "", timeout: float = 3.0) -> dict:
        self._id += 1
        tmp = os.path.join(self.dir, "cmd.tmp")
        with open(tmp, "w") as fh:
            fh.write("%d %s %s\n" % (self._id, verb, arg))
        os.replace(tmp, os.path.join(self.dir, "cmd.txt"))
        end = time.time() + timeout
        while time.time() < end:
            st = self._status_raw()
            if st.get("last_id") == self._id:
                return st
            time.sleep(0.03)
        raise TimeoutError("ACC did not answer '%s' — is ACC running with UE4SS loaded?" % verb)

    def status(self) -> dict:
        return self.send("status")

    def pause(self) -> dict:
        return self.send("pause")

    def play(self) -> dict:
        return self.send("play")

    def seek(self, seconds: float) -> dict:
        """Jump to an absolute replay time (the clock ACC reports, = vre-rpy's decoder clock).

        ACC's SetCurrentReplayTimeToSeconds takes whole seconds *from the start of the replay*, while its
        current time is absolute (a replay can start at e.g. 1714 s), so subtract the start."""
        start = self.status().get("start_s") or 0.0
        return self.send("seek", "%d" % max(0, int(seconds - max(0.0, start))))

    def where(self) -> str:
        """"menu", "race" (a session/replay is loaded) or "loading"."""
        try:
            return self.send("where", timeout=3).get("result", "loading")
        except TimeoutError:
            return "loading"

    def to_menu(self, timeout: float = 60.0) -> bool:
        """Leave the replay for ACC's main menu (refuses to close a live session)."""
        if self.where() == "menu":
            return True
        res = self.send("menu").get("result", "")
        if not res.startswith("ok"):
            raise RuntimeError("ACC didn't go to the menu: %s" % res)
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(1.0)
            if self.where() == "menu":
                time.sleep(2.0)          # let the menu settle before loading
                return True
        return False

    def load_replay(self, filename: str, track_id: int, car_model_id: int, length_s: float,
                    timeout: float = 90.0) -> dict:
        """Load a saved replay by file name through ACC's own AcMenuGameMode.LoadReplay; wait until it plays."""
        if not self.to_menu():
            raise RuntimeError("ACC didn't reach the main menu")
        name = filename[:-4] if filename.lower().endswith(".rpy") else filename
        res = self.send("load", "Filename=%s;TrackId=%d;Length=%.1f;carModelTypeId=%d;Version=25"
                        % (name, track_id, length_s, car_model_id), timeout=20).get("result", "")
        if "returned true" not in res:
            raise RuntimeError("ACC refused to load %s: %s" % (name, res))
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(1.5)
            try:
                st = self.status()
            except TimeoutError:
                continue
            if st.get("in_replay") and st.get("total_s"):
                return st
        raise RuntimeError("ACC didn't open %s in time" % name)

    def quit_acc(self, timeout: float = 60.0) -> bool:
        """Close ACC through the engine's own QuitGame (refused during a live session)."""
        from .acc_bindings import acc_running

        try:
            res = self.send("quit", timeout=5).get("result", "")
        except TimeoutError:
            res = "timeout"
        if not res.startswith("ok"):
            raise RuntimeError("ACC didn't quit: %s" % res)
        end = time.time() + timeout
        while time.time() < end:
            time.sleep(1.0)
            if not acc_running():
                return True
        return False

    @staticmethod
    def available() -> bool:
        try:
            d = game_bin_dir()
        except FileNotFoundError:
            return False
        return os.path.isfile(os.path.join(d, MANIFEST)) and os.path.isdir(os.path.join(d, "ue4ss", "Mods", "VREReplayControl"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["install", "uninstall", "status", "pause", "play", "seek"])
    ap.add_argument("value", nargs="?")
    ap.add_argument("--zip")
    a = ap.parse_args(argv)
    if a.action == "install":
        print(install(a.zip))
    elif a.action == "uninstall":
        uninstall()
        print("removed")
    else:
        rc = ReplayControl()
        fn = getattr(rc, a.action)
        print(fn(float(a.value)) if a.action == "seek" else fn())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
