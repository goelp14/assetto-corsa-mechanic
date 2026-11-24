"""Build a Lap Studio bundle from ACC replays (any car/track) for the replay viewer.

    python -m external.query_tools.acc_replay_bundle --rpy me.rpy:You [--ref fast.rpy:Ref] \\
        [--ref-car-index N] [--setups-dir DIR] [--id NAME]

Writes ``exports/<id>/``:
    manifest.json        schema vre.replay_bundle.acc.v2 (drivers, laps, files)
    track.json           AI line + official edges (world X/Z), corners/terrain (metres from S/F)
    frames/<label>/lap_NN.json   full-rate frames (vre-rpy frames)
    analysis.json        vre-rpy analyze (corner events, losses, cliffs, car state)
    coaching.json        habits → 1-2 fixes → diagnosis
    setup.json           setup fingerprint (+ comparison with the reference)
    track_limits.json    cut attribution, excursions, legal track use
    reviews/             AI / user video reviews (created empty)
and refreshes ``exports/sessions_index.json``. Requires the ``vre_rpy`` package (pip install -e vre-rpy-cli).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
EXPORTS = REPO / "exports"
SCHEMA = "vre.replay_bundle.acc.v2"



def _replay_end_s(rf) -> Optional[float]:
    """Last recorded moment on the decoder clock. ACC's replay ends at the same instant, so ACC's
    'replay time remaining' maps onto this clock as end − remaining (used to sync recorded video)."""
    ends = []
    for arr in (getattr(rf, "t", None), (rf.inputs or {}).get("time_s") if isinstance(rf.inputs, dict) else None):
        try:
            if arr is not None and len(arr):
                ends.append(float(arr[-1]))
        except TypeError:
            continue
    return round(max(ends), 4) if ends else None

def _spec(s: str) -> Tuple[Path, str]:
    if ":" in s:
        p, _, label = s.rpartition(":")
        if p.endswith(".rpy") or Path(p).exists():
            return Path(p), label or Path(p).stem
    return Path(s), Path(s).stem


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")[:40] or "driver"


def build(me_spec: Tuple[Path, str], ref_spec: Optional[Tuple[Path, str]] = None, *, ref_car_index: Optional[int] = None,
          car_index: Optional[int] = None, setups_dir: Optional[Path] = None, bundle_id: Optional[str] = None,
          exports: Path = EXPORTS, laps: str = "all") -> Path:
    from vre_rpy.lap_analysis import run_analysis
    from vre_rpy.replay_frames import ReplayFrames
    from vre_rpy.setup_fingerprint import compare_fingerprints, fingerprint
    from vre_rpy.track_limits import analyze as limits

    from .coach.acc_coach import run as coach_run

    me = ReplayFrames(me_spec[0], car_index=car_index)
    me.label = _slug(me_spec[1])
    ref = None
    if ref_spec:
        ref = ReplayFrames(ref_spec[0], car_index=ref_car_index)
        ref.label = _slug(ref_spec[1])
        if ref.label == me.label:
            ref.label += "_ref"
    track = str(me.ident.get("track") or "track")
    bid = bundle_id or f"lab_{track}_{me.label}" + (f"_vs_{ref.label}" if ref else "") + dt.datetime.now().strftime("_%Y%m%d_%H%M%S")
    out = exports / bid
    (out / "frames").mkdir(parents=True, exist_ok=True)
    (out / "reviews").mkdir(exist_ok=True)

    analysis = run_analysis(me, ref)
    (out / "analysis.json").write_text(json.dumps(analysis, default=float), encoding="utf-8")
    sf_off = analysis.get("pack", {}).get("sf_offset_m") or 0.0

    drivers_meta: List[Dict[str, Any]] = []
    for role, rf in (("me", me), ("ref", ref)):
        if rf is None:
            continue
        d = out / "frames" / rf.label
        d.mkdir(exist_ok=True)
        lap_rows = []
        best = rf.best_lap_index()
        for l in rf.laps:
            if not l.get("completed"):
                continue
            if laps == "best" and l["lap_index"] != best:
                continue
            try:
                fr = rf.lap_frames(l["lap_index"])
            except ValueError:
                continue
            fn = d / f"lap_{l['lap_index']:02d}.json"
            fn.write_text(json.dumps(fr, separators=(",", ":")), encoding="utf-8")
            lap_rows.append({"lap_index": l["lap_index"], "lap_ms": l["lap_ms"], "valid": l.get("valid"),
                             "flying": l.get("flying_candidate"), "partial": fr["meta"].get("partial"),
                             "sync_ok": fr["meta"]["sync"].get("lap_sync_go"),
                             "start_s": round(float(l.get("sf_time_s", l["session_start_s"])), 4),
                             "frames": f"frames/{rf.label}/{fn.name}"})
        drivers_meta.append({"label": rf.label, "role": role, "identity": rf.ident, "car": rf.car,
                             "best_lap_index": best, "laps": lap_rows, "sync": rf.sync,
                             "pose_hz": rf.clock["hz"], "replay_end_s": _replay_end_s(rf),
                             "rpy_file": Path(str(rf.path)).name})

    try:
        rep = limits([x for x in (me, ref) if x is not None])
        (out / "track_limits.json").write_text(json.dumps(rep, default=float), encoding="utf-8")
    except Exception as exc:  # additive
        (out / "track_limits.json").write_text(json.dumps({"error": str(exc)}), encoding="utf-8")

    fp_me = fingerprint(me)
    setup: Dict[str, Any] = {"fingerprint": fp_me, "label": me.label}
    if ref is not None:
        fp_ref = fingerprint(ref)
        setup["reference"] = {"label": ref.label, "fingerprint": fp_ref}
        setup["comparison"] = compare_fingerprints(fp_me, fp_ref, labels=(me.label, ref.label))
    try:
        from vre_rpy.setup_files import candidates_for_session, default_setups_dir, physical

        sdir = Path(setups_dir) if setups_dir else default_setups_dir()
        cands = candidates_for_session(sdir, str(me.ident.get("car") or ""), track, me.path.stat().st_mtime)
        setup["library_candidates"] = [{"name": c["name"], "physical": physical(c), "values": c["values"]} for c in cands]
    except Exception:
        setup["library_candidates"] = []
    (out / "setup.json").write_text(json.dumps(setup, default=float), encoding="utf-8")

    coaching = coach_run(analysis, setup)
    (out / "coaching.json").write_text(json.dumps(coaching, default=float), encoding="utf-8")
    from .coach.reviews import auto_breakdown

    (out / "reviews" / "auto.json").write_text(json.dumps(auto_breakdown(analysis, coaching), default=float), encoding="utf-8")

    line = me.line
    track_json: Dict[str, Any] = {"track_id": track, "length_m": me.length_m, "sf_offset_m": sf_off,
                                  "corners": analysis.get("pack", {}).get("corners") or [],
                                  "terrain": analysis.get("pack", {}).get("terrain") or [],
                                  "notes": analysis.get("pack", {}).get("notes")}
    if line is not None:
        track_json.update({"centerline": line.c.round(2).tolist(), "left": line.left.round(2).tolist(),
                           "right": line.right.round(2).tolist()})
    (out / "track.json").write_text(json.dumps(track_json, default=float), encoding="utf-8")
    if not (out / "annotations.json").exists():
        (out / "annotations.json").write_text(json.dumps({"annotations": []}), encoding="utf-8")

    me_best = min((l["lap_ms"] for l in drivers_meta[0]["laps"] if l.get("valid") and l.get("flying")), default=None)
    manifest = {
        "schema": SCHEMA, "session_id": bid, "game": "acc", "source": "acc_rpy",
        "track_id": track, "track_display": (analysis.get("pack", {}).get("notes") or {}).get("track") or track.replace("_", " ").title(),
        "car_id": me.ident.get("car"), "track_length_m": me.length_m,
        "best_lap_ms": me_best, "created": dt.datetime.now().isoformat(timespec="seconds"),
        "drivers": drivers_meta,
        "files": {"analysis": "analysis.json", "coaching": "coaching.json", "setup": "setup.json",
                  "limits": "track_limits.json", "track": "track.json", "annotations": "annotations.json",
                  "reviews": "reviews/"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, default=float), encoding="utf-8")
    try:  # an improved lap or a replaced reference makes old footage stale
        from .video_store import prune

        prune(out.name, exports=str(exports))
    except Exception:
        pass
    _refresh_index(exports)
    return out


def _refresh_index(exports: Path) -> None:
    """Add Lab bundles to sessions_index.json (keeps existing AC/ACC entries)."""
    idx_p = exports / "sessions_index.json"
    idx = json.loads(idx_p.read_text()) if idx_p.is_file() else {"sessions": []}
    keep = [s for s in idx.get("sessions") or [] if s.get("schema") != SCHEMA]
    lab = []
    for m in sorted(exports.glob("*/manifest.json")):
        try:
            man = json.loads(m.read_text())
        except ValueError:
            continue
        if man.get("schema") != SCHEMA:
            continue
        lab.append({"id": man["session_id"], "session_id": man["session_id"], "schema": SCHEMA, "game": "acc",
                    "track": man.get("track_display"), "track_id": man.get("track_id"), "car_id": man.get("car_id"),
                    "best_lap_ms": man.get("best_lap_ms"), "bundle_url": f"/bundles/{m.parent.name}",
                    "bundle_path": m.parent.name, "created": man.get("created"),
                    "drivers": [d["label"] for d in man.get("drivers") or []]})
    lab.sort(key=lambda s: s.get("created") or "", reverse=True)
    idx["sessions"] = lab + keep
    idx["count"] = len(idx["sessions"])
    idx["latest_id"] = idx["sessions"][0]["id"] if idx["sessions"] else None
    idx_p.write_text(json.dumps(idx, indent=1), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build a Lap Studio bundle from ACC replays")
    ap.add_argument("--rpy", required=True)
    ap.add_argument("--ref", default=None)
    ap.add_argument("--car-index", type=int, default=None)
    ap.add_argument("--ref-car-index", type=int, default=None)
    ap.add_argument("--setups-dir", type=Path, default=None)
    ap.add_argument("--id", default=None)
    ap.add_argument("--laps", choices=["all", "best"], default="all")
    a = ap.parse_args(argv)
    out = build(_spec(a.rpy), _spec(a.ref) if a.ref else None, ref_car_index=a.ref_car_index,
                car_index=a.car_index, setups_dir=a.setups_dir, bundle_id=a.id, laps=a.laps)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
