"""MCP server (stdio, stdlib only): lets an AI watch and drive Lap Studio like a coach doing video review.

    claude mcp add vre-viewer -- python3 external/query_tools/viewer_mcp.py [--url http://127.0.0.1:8765]

Needs the launcher running (./replay.sh). Every number an AI puts in a saved review is checked against
the data it cites (coach/reviews.validate) — the launcher rejects ungrounded reviews with the errors.

Read tools  : list_bundles, get_state, get_coaching, get_corner, get_frames_window, get_track_limits, get_setup
Drive tools : seek, play_range, pause, set_mode, focus_corner, set_laps, set_tab, set_map_color
Annotate    : annotate, clear_annotations, add_scene
Reviews     : list_reviews, create_review, open_review
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

PROTOCOL = "2024-11-05"
BASE = os.environ.get("VRE_VIEWER_URL", "http://127.0.0.1:8765")


def _http(method: str, path: str, payload: Any = None) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            return {"ok": False, "status": e.code, **json.loads(e.read())}
        except ValueError:
            return {"ok": False, "status": e.code}
    except urllib.error.URLError as e:
        return {"ok": False, "error": f"viewer not reachable at {BASE} ({e.reason}); start it with ./replay.sh"}


def _cmd(cmd: str, **args: Any) -> Any:
    return _http("POST", "/api/viewer/command", {"cmd": cmd, "args": {k: v for k, v in args.items() if v is not None}})


def _bundle(bundle: Optional[str]) -> str:
    if bundle:
        return bundle
    st = _http("GET", "/api/viewer/state")
    if st.get("bundle"):
        return st["bundle"]
    idx = _http("GET", "/api/sessions")
    lab = [s for s in idx.get("sessions") or [] if s.get("schema") == "vre.replay_bundle.acc.v2"]
    if not lab:
        raise ValueError("no Lap Studio bundle open or available")
    return lab[0]["id"]


def _file(bundle: str, name: str) -> Any:
    return _http("GET", f"/bundles/{urllib.parse.quote(bundle)}/{name}")


# ---------------- tools ----------------

def list_bundles() -> Any:
    idx = _http("GET", "/api/sessions")
    return [{k: s.get(k) for k in ("id", "track", "car_id", "drivers", "best_lap_ms", "created")}
            for s in idx.get("sessions") or [] if s.get("schema") == "vre.replay_bundle.acc.v2"]


def get_state() -> Any:
    return _http("GET", "/api/viewer/state")


def get_coaching(bundle: Optional[str] = None) -> Any:
    b = _bundle(bundle)
    c = _file(b, "coaching.json")
    keep = ("driver", "reference", "fixes", "later", "strengths", "setup_checks", "diagnosis", "persistent_habits", "preferences")
    out = {k: c.get(k) for k in keep}
    out["habits"] = [{k: h.get(k) for k in ("id", "title", "polarity", "pace_impact_s", "corners", "repeats")}
                     for h in (c.get("habits") or {}).get("habits") or []]
    a = _file(b, "analysis.json")
    out["corner_loss_best_vs_ref"] = a.get("corner_loss_best_vs_ref")
    out["laps"] = {d: {"best_lap_ms": v.get("best_lap_ms"), "theoretical": v.get("theoretical")} for d, v in (a.get("drivers") or {}).items()}
    out["citation_roots"] = "analysis.*, coaching.* (incl. coaching.landmarks.<corner_key>), habits.*, track_limits.*"
    return out


def get_corner(corner: str, bundle: Optional[str] = None) -> Any:
    b = _bundle(bundle)
    a = _file(b, "analysis.json")
    c = _file(b, "coaching.json")
    key = next((f"{w['corner']}#{w['index']}" for w in a.get("windows") or []
                if corner in (w["corner"], f"{w['corner']}#{w['index']}")), None)
    if not key:
        return {"error": f"unknown corner {corner}", "corners": [f"{w['corner']}#{w['index']}" for w in a.get("windows") or []]}
    w = next(w for w in a["windows"] if f"{w['corner']}#{w['index']}" == key)
    out: Dict[str, Any] = {"key": key, "window": w, "landmarks": (c.get("landmarks") or {}).get(key),
                           "loss_best_vs_ref": next((r for r in a.get("corner_loss_best_vs_ref") or [] if f"{r['corner']}#{r['index']}" == key), None),
                           "terrain": [t for t in (a.get("pack") or {}).get("terrain") or [] if w["s0_m"] <= t["peak_m"] <= w["s1_m"]],
                           "notes": next((p.get("notes") for p in (a.get("pack") or {}).get("corners") or [] if p.get("display_name") == w["corner"]), None),
                           "drivers": {}}
    for d, v in (a.get("drivers") or {}).items():
        cs = (v.get("corners") or {}).get(key) or {}
        out["drivers"][d] = {"best_lap": cs.get("best_lap"), "consistency": cs.get("consistency")}
    out["citations"] = [f"analysis.drivers.{d}.corners.{key}.best_lap" for d in out["drivers"]] + [f"coaching.landmarks.{key}"]
    return out


def get_frames_window(s0_m: float, s1_m: float, driver: Optional[str] = None, lap: Optional[int] = None,
                      step_m: float = 5.0, bundle: Optional[str] = None,
                      channels: Optional[List[str]] = None) -> Any:
    """Frames of one lap between two distances, resampled every step_m (default: A/B laps on screen)."""
    b = _bundle(bundle)
    man = _file(b, "manifest.json")
    st = get_state()
    out = {}
    chans = channels or ["t", "speed_kmh", "throttle", "brake", "steer_deg", "gear", "g_lat", "g_lon", "lat_m", "y", "slip_deg"]
    targets = []
    if driver is not None:
        d = next((x for x in man["drivers"] if x["label"] == driver), None)
        if not d:
            return {"error": f"unknown driver {driver}"}
        targets.append((driver, lap if lap is not None else d["best_lap_index"]))
    else:
        for slot in ("A", "B"):
            if st.get(slot):
                targets.append((st[slot]["driver"], st[slot]["lap"]))
        if not targets:
            targets = [(d["label"], d["best_lap_index"]) for d in man["drivers"]]
    for drv, lp in targets:
        row = next((l for d in man["drivers"] if d["label"] == drv for l in d["laps"] if l["lap_index"] == lp), None)
        if not row:
            continue
        f = _file(b, row["frames"])
        s = f["s_m"]
        rows = []
        x = float(s0_m)
        j = 0
        while x <= s1_m and len(rows) < 400:
            while j < len(s) - 2 and s[j + 1] < x:
                j += 1
            k = (x - s[j]) / ((s[j + 1] - s[j]) or 1.0)
            k = max(0.0, min(1.0, k))
            r = {"s_m": round(x, 1)}
            for ch in chans:
                arr = f.get(ch)
                if isinstance(arr, list) and arr[j] is not None and arr[j + 1] is not None:
                    r[ch] = round(arr[j] + k * (arr[j + 1] - arr[j]), 3)
            rows.append(r)
            x += step_m
        out[f"{drv}#L{lp}"] = rows
    return out


def get_track_limits(bundle: Optional[str] = None) -> Any:
    L = _file(_bundle(bundle), "track_limits.json")
    return {"zones": L.get("zones"), "notes": L.get("notes"),
            "drivers": [{"label": d["label"], "laps": [{"lap": l["lap_index"], "valid": l["valid"], "cut": l.get("cut")} for l in d["laps"]]}
                        for d in L.get("drivers") or []]}


def get_setup(bundle: Optional[str] = None) -> Any:
    b = _bundle(bundle)
    s = _file(b, "setup.json")
    a = _file(b, "analysis.json")
    return {"car_state": a.get("car_state"), "comparison": s.get("comparison"),
            "exact": (s.get("fingerprint") or {}).get("exact"),
            "library_candidates": [c.get("name") for c in s.get("library_candidates") or []],
            "note": "the setup is not stored in ACC replays; this is measured behaviour + matching library files"}


def seek(s_m: float) -> Any:
    return _cmd("seek", s_m=s_m)


def play_range(s0_m: float, s1_m: float, rate: float = 0.5, mode: Optional[str] = None) -> Any:
    return _cmd("play_range", s0_m=s0_m, s1_m=s1_m, rate=rate, mode=mode)


def pause() -> Any:
    return _cmd("pause")


def set_mode(mode: str, rate: Optional[float] = None) -> Any:
    return _cmd("set_mode", mode=mode, rate=rate)


def focus_corner(corner: str, play: bool = False) -> Any:
    return _cmd("focus_corner", corner=corner, play=play)


def set_laps(me: Any = None, ref: Any = None) -> Any:
    return _cmd("set_laps", me=me, ref=ref)


def set_tab(tab: str) -> Any:
    return _cmd("set_tab", tab=tab)


def set_map_color(by: str) -> Any:
    return _cmd("set_map_color", by=by)


def annotate(annotations: List[Dict[str, Any]], persist: bool = False) -> Any:
    return _cmd("annotate", annotations=annotations, persist=persist)


def clear_annotations(persisted: bool = False) -> Any:
    return _cmd("clear_annotations", persisted=persisted)


def add_scene(scene: Dict[str, Any]) -> Any:
    return _cmd("add_scene", scene=scene)


def list_reviews(bundle: Optional[str] = None) -> Any:
    return _http("GET", f"/api/bundles/{urllib.parse.quote(_bundle(bundle))}/reviews")


def create_review(name: str, review: Dict[str, Any], bundle: Optional[str] = None) -> Any:
    review = {"schema": "vre.review.v1", **review}
    res = _http("POST", f"/api/bundles/{urllib.parse.quote(_bundle(bundle))}/reviews/{urllib.parse.quote(name)}", review)
    return res


def open_review(name: str, scene: int = 0) -> Any:
    return _cmd("open_review", name=name, scene=scene)


S = {"type": "string"}
N = {"type": "number"}
B = {"type": "boolean"}
OPT_BUNDLE = {"bundle": {"type": "string", "description": "bundle id (default: the one open in the viewer)"}}
OVERLAY = {"type": "object", "properties": {"kind": {"enum": ["pin", "zone", "arrow", "text", "line"]}, "at_m": N, "s0_m": N, "s1_m": N,
                                            "driver": {"enum": ["me", "ref"]}, "text": S, "color": S}}
SCENE = {"type": "object", "description": "vre.review.v1 scene", "properties": {
    "title": S, "corner_key": S, "s0_m": N, "s1_m": N, "mode": {"enum": ["dist", "time"]}, "rate": N,
    "laps": {"type": "object"}, "narration": S,
    "pauses": {"type": "array", "items": {"type": "object", "properties": {"at_m": N, "text": S, "driver": S}}},
    "overlays": {"type": "array", "items": OVERLAY}, "lanes": {"type": "array", "items": S},
    "citations": {"type": "array", "items": S, "description": "dotted paths, e.g. analysis.drivers.You.corners.La Source#0.best_lap, coaching.landmarks.La Source#0"}},
    "required": ["title", "s0_m", "s1_m", "citations"]}

TOOLS = {
    "list_bundles": (list_bundles, "List Lap Studio bundles (ACC replay comparisons).", {}),
    "get_state": (get_state, "What the viewer shows now: laps A/B, cursor (metres from S/F and apex-relative 'where'), values for both cars, delta, view range, review/scene, tab.", {}),
    "get_coaching": (get_coaching, "Fixes (with landmark phrasing), habits, diagnosis, per-corner losses and lap/theoretical times.", OPT_BUNDLE),
    "get_corner": (get_corner, "Everything for one corner: window, events for both drivers' best laps, consistency, landmark sentences, terrain, track notes and citation paths.", {"corner": S, **OPT_BUNDLE}),
    "get_frames_window": (get_frames_window, "Resampled frames between two distances for the laps on screen (or a given driver/lap).", {"s0_m": N, "s1_m": N, "driver": S, "lap": {"type": "integer"}, "step_m": N, "channels": {"type": "array", "items": S}, **OPT_BUNDLE}),
    "get_track_limits": (get_track_limits, "Lap validity, attributed cut per lap, learned cut zones.", OPT_BUNDLE),
    "get_setup": (get_setup, "Measured car state, behaviour fingerprint vs reference, exact gearing, matching setup files.", OPT_BUNDLE),
    "seek": (seek, "Move the cursor to a distance (metres from S/F).", {"s_m": N}),
    "play_range": (play_range, "Frame the range and play it (rate 0.1-4; mode 'dist' same place or 'time' same moment).", {"s0_m": N, "s1_m": N, "rate": N, "mode": {"enum": ["dist", "time"]}}),
    "pause": (pause, "Pause playback.", {}),
    "set_mode": (set_mode, "Sync mode: 'dist' (same place) or 'time' (same moment from the view start); optional rate.", {"mode": {"enum": ["dist", "time"]}, "rate": N}),
    "focus_corner": (focus_corner, "Frame a corner (name or key) from braking to exit; play=true to play it at 0.5x.", {"corner": S, "play": B}),
    "set_laps": (set_laps, "Choose laps: me/ref = 'best' or a lap number.", {"me": {}, "ref": {}}),
    "set_tab": (set_tab, "Open a side panel: coaching | corners | review | setup | limits.", {"tab": {"enum": ["coaching", "corners", "review", "setup", "limits"]}}),
    "set_map_color": (set_map_color, "Colour the line by delta | speed | pedals | gear | g_lat.", {"by": {"enum": ["delta", "speed", "pedals", "gear", "g_lat"]}}),
    "annotate": (annotate, "Draw pins/zones/text at distances on map and traces. persist=true saves them to the bundle.", {"annotations": {"type": "array", "items": OVERLAY}, "persist": B}),
    "clear_annotations": (clear_annotations, "Remove live annotations (persisted=true also clears saved ones).", {"persisted": B}),
    "add_scene": (add_scene, "Put a draft scene into the viewer's review editor (not saved).", {"scene": SCENE}),
    "list_reviews": (list_reviews, "Names of saved reviews in the bundle.", OPT_BUNDLE),
    "create_review": (create_review, "Save a review (title + scenes). Rejected with the list of problems if any number is not in its citations or a window is invalid.", {"name": S, "review": {"type": "object", "properties": {"title": S, "scenes": {"type": "array", "items": SCENE}}, "required": ["title", "scenes"]}, **OPT_BUNDLE}),
    "open_review": (open_review, "Open a saved review in the viewer and play from a scene.", {"name": S, "scene": {"type": "integer"}}),
}
REQUIRED = {"get_corner": ["corner"], "get_frames_window": ["s0_m", "s1_m"], "seek": ["s_m"], "play_range": ["s0_m", "s1_m"],
            "set_mode": ["mode"], "focus_corner": ["corner"], "set_tab": ["tab"], "set_map_color": ["by"],
            "annotate": ["annotations"], "add_scene": ["scene"], "create_review": ["name", "review"], "open_review": ["name"]}


def tool_list() -> List[Dict[str, Any]]:
    return [{"name": n, "description": d, "inputSchema": {"type": "object", "properties": p, "required": REQUIRED.get(n, [])}}
            for n, (_, d, p) in TOOLS.items()]


def handle(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    mid, method = msg.get("id"), msg.get("method")
    if mid is None:
        return None  # notification
    if method == "initialize":
        res = {"protocolVersion": PROTOCOL, "capabilities": {"tools": {}},
               "serverInfo": {"name": "vre-viewer", "version": "1.0"},
               "instructions": "Drive VRE Lap Studio. Read get_state/get_coaching/get_corner first; cite data paths in reviews."}
    elif method == "tools/list":
        res = {"tools": tool_list()}
    elif method == "tools/call":
        name = (msg.get("params") or {}).get("name")
        args = (msg.get("params") or {}).get("arguments") or {}
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}}
        try:
            out = TOOLS[name][0](**args)
            bad = isinstance(out, dict) and out.get("ok") is False
            res = {"content": [{"type": "text", "text": json.dumps(out, default=str)[:60000]}], "isError": bool(bad)}
        except Exception as exc:  # report to the model, keep serving
            res = {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True}
    elif method == "ping":
        res = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def main(argv=None) -> int:
    global BASE
    ap = argparse.ArgumentParser(description="VRE Lap Studio MCP server (stdio)")
    ap.add_argument("--url", default=BASE)
    BASE = ap.parse_args(argv).url.rstrip("/")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        out = handle(msg)
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
