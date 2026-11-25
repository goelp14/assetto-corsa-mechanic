"""Rotation metrics per corner and lap: where the car rotates, how the rotation is built, what it costs.

Corner model (Almeida Racing Academy; Popometer coaching agrees):
    braking zone -> closing spiral -> Maximum Rotation Point (MRP) -> opening spiral.
While the speed falls the car can rotate more, so rotation should *build* progressively as speed drops
("1-2-3-4-5, power"), peak once at the MRP (peak yaw rate, usually a little before the apex), and the
throttle opens the spiral after it. Common faults this measures:
    * rotation snapped in at turn-in instead of built up (car slides, gets corrected, then understeers);
    * all the slowing done before turning, so no speed is shed while the car rotates (brake straight,
      then turn) where a faster lap keeps trailing into the closing spiral;
    * throttle before the car has rotated;
    * part throttle that does not accelerate (only cancels engine braking and unloads the front).

Input: Lap Studio frames (``frames/<label>/lap_NN.json``: s_m, t, yaw_deg, speed_kmh, steer_deg,
throttle_masked, g_lon, slip_deg) and the analysis windows. Output: extra per-lap metrics merged into
``analysis.drivers.<label>.corners.<key>.laps`` plus their ``consistency`` / ``best_lap`` entries, so the
habit detector, distiller and landmarks use them like any other metric. Any car, any track, AC or ACC.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

METRICS = ("mrp_m", "mrp_vs_apex_m", "mrp_kmh", "mrp_yaw_dps", "rotation_jerk_dps2", "heading_to_mrp_deg",
           "kmh_lost_turn_in_to_mrp", "throttle_on_vs_mrp_m", "steer_unwind_at_full_throttle",
           "maintenance_throttle_s", "entry_slip_peak_deg", "understeer_entry", "grip_gap_frac",
           "brake_release_vs_steer_build", "last_downshift_vs_apex_m", "rotation_before_throttle_frac",
           "rotation_plateau_s", "mrp_vs_vmin_m")


def _smooth(x: np.ndarray, n: int) -> np.ndarray:
    if n <= 1 or len(x) < n:
        return x
    k = np.ones(n) / n
    return np.convolve(np.pad(x, (n // 2, n - 1 - n // 2), mode="edge"), k, "valid")


def steer_gain(frame: Dict[str, Any]) -> Optional[float]:
    """Steering-wheel degrees per unit of path curvature in the near-linear regime, fitted on this lap.

    In the linear range road-wheel angle ≈ wheelbase × curvature, so wheel degrees × v / yaw rate is the
    driver's steering ratio × wheelbase. Fitting it per lap (|g_lat| < 0.5, real speed and lock) makes the
    balance trace independent of each driver's wheel rotation / ratio settings. Cached on the frame.
    """
    if "_vre_steer_gain" in frame:
        return frame["_vre_steer_gain"]
    gain = None
    try:
        t = np.asarray(frame["t"], float)
        yr = np.gradient(np.unwrap(np.radians(np.asarray(frame["yaw_deg"], float))), t)
        v = np.asarray(frame["speed_kmh"], float) / 3.6
        st = np.asarray(frame["steer_deg"], float)
        gl = np.asarray(frame["g_lat"], float)
        ok = (v > 15) & (np.abs(st) > 4) & (np.abs(gl) < 0.5) & (np.abs(yr) > 0.02) & (np.sign(st) == np.sign(yr))
        if ok.sum() >= 30:
            gain = float(np.median(np.abs(st[ok]) * v[ok] / np.abs(yr[ok])))
    except (KeyError, ValueError):
        gain = None
    frame["_vre_steer_gain"] = gain
    return gain


def corner_lap(frame: Dict[str, Any], window: Dict[str, Any], lap: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Rotation metrics for one pass through one corner window (None when the frames don't cover it)."""
    s = np.asarray(frame["s_m"], float)
    t = np.asarray(frame["t"], float)
    apex = float(window["apex_m"])
    sel = (s >= window["s0_m"]) & (s <= min(window["s1_m"], apex + 250.0))
    if sel.sum() < 20:
        return None
    s, t = s[sel], t[sel]
    if np.any(np.diff(t) <= 0):
        return None
    hz = 1.0 / float(np.median(np.diff(t)))
    n = max(3, int(round(0.12 * hz)))  # ~0.12 s smoothing: kills sample noise, keeps the shape of a corner
    yaw = np.unwrap(np.radians(np.asarray(frame["yaw_deg"], float)[sel]))
    v = np.asarray(frame["speed_kmh"], float)[sel]
    yr = _smooth(np.gradient(yaw, t), n)
    near = (s > apex - 30) & (s < apex + 30)
    if not near.any():
        return None
    sign = 1.0 if np.median(yr[near]) >= 0 else -1.0  # positive = turning the corner's way
    yr = yr * sign
    steer = np.asarray(frame["steer_deg"], float)[sel] * sign
    thr = np.asarray(frame.get("throttle_masked") or frame["throttle"], float)[sel]
    glon = np.asarray(frame["g_lon"], float)[sel]
    slip = np.asarray(frame["slip_deg"], float)[sel] * sign

    ti = lap.get("turn_in_m")
    ti = float(ti) if isinstance(ti, (int, float)) else apex - 40.0
    zone = np.where((s >= ti - 20) & (s <= apex + 80))[0]
    if len(zone) == 0:
        return None
    k = int(zone[np.argmax(yr[zone])])  # MRP: peak yaw rate
    i0 = int(np.searchsorted(s, ti))
    yacc = _smooth(np.gradient(yr, t), n)
    jerk = float(np.degrees(yacc[i0:k + 1].max())) if k > i0 else None
    heading = float(np.degrees(yaw[k] - yaw[min(i0, k)]) * sign)
    kmh_lost = float(v[min(i0, k)] - v[k])
    th_on = lap.get("throttle_on_m")
    ft = lap.get("full_throttle_m")
    unwind = None
    if isinstance(ft, (int, float)):
        j = int(np.searchsorted(s, ft))
        if j < len(s) and steer[k] > 1.0:
            unwind = float(steer[j] / steer[k])
    vm = int(np.argmin(v))
    part = (thr[vm:] > 0.10) & (thr[vm:] < 0.90) & (glon[vm:] < 0.03)  # pedal on, car not accelerating
    lo, hi = min(i0, k), min(len(s), k + max(1, int(0.5 * hz)))

    # balance: how much of the rotation the steering asks for actually happens (+ = understeer, - = oversteer)
    gain = steer_gain(frame)
    under = None
    if gain and k > i0:
        seg = slice(i0, k + 1)
        ask = steer[seg] / gain
        ok = steer[seg] > 8.0
        if ok.sum() >= 3:
            got = yr[seg] / np.maximum(v[seg] / 3.6, 3.0)
            under = float(np.median(1.0 - got[ok] / ask[ok]))

    # grip-usage gap between braking and turning ("the tyres go quiet"): a dip in combined g before the MRP
    g0 = int(np.searchsorted(s, ti - 40.0))
    gap = None
    if "g_lat" in frame and k - g0 > 3:
        comb = _smooth(np.hypot(np.asarray(frame["g_lat"], float)[sel], glon), n)
        ends = min(comb[g0], comb[k])
        if ends > 0.3:
            gap = float(max(0.0, 1.0 - comb[g0:k + 1].min() / ends))

    # brake release length vs steering build length (a quick drop leaves a hole the steering can't fill)
    brk = np.asarray(frame.get("brake") or np.zeros(len(sel)), float)[sel]
    release_ratio = None
    pre = brk[:k + 1]
    if len(pre) and pre.max() > 0.2 and k > i0:
        pk = int(np.argmax(pre))
        hold = pk + int(np.where(pre[pk:] >= 0.6 * pre[pk])[0][-1])
        off = np.where(brk[hold:] < 0.03)[0]
        if len(off):
            rel_s = float(t[hold + off[0]] - t[hold])
            build_s = float(t[k] - t[i0])
            release_ratio = rel_s / build_s if build_s > 0.05 else None

    # downshifts (engine braking = a third of the rotation toolkit; their timing sets the entry balance)
    gear = np.asarray(frame.get("gear") or [], float)
    last_ds = None
    if len(gear):
        g = gear[sel][:k + 1]
        down = np.where(np.diff(g) < 0)[0]
        if len(down):
            last_ds = float(s[down[-1] + 1] - apex)

    # share of the corner's rotation done before the throttle (rule of thumb: at least half, ~55 % on entry)
    rot_before = None
    total = float(np.degrees(yaw[-1] - yaw[min(i0, len(yaw) - 1)]) * sign)
    if isinstance(th_on, (int, float)) and total > 20.0:
        j = min(int(np.searchsorted(s, th_on)), len(s) - 1)
        rot_before = float(np.degrees(yaw[j] - yaw[min(i0, j)]) * sign) / total

    # "maximum rotation line": rotation held near its peak while neither slowing nor accelerating, waiting
    plateau = None
    if isinstance(th_on, (int, float)) and k > i0:
        j = int(np.searchsorted(s, th_on))
        if j > k:
            held = (yr[k:j] >= 0.85 * yr[k])
            plateau = float(held.sum()) / hz

    if not window.get("braked", True):  # flat/lift corners: speed isn't falling, the closing-spiral model doesn't apply
        jerk, kmh_lost, release_ratio, rot_before, plateau = None, None, None, None, None
    return {
        "rotation_before_throttle_frac": None if rot_before is None else round(rot_before, 2),
        "rotation_plateau_s": None if plateau is None else round(plateau, 2),
        "mrp_vs_vmin_m": round(float(s[k] - s[vm]), 1),
        "understeer_entry": None if under is None else round(under, 3),
        "grip_gap_frac": None if gap is None else round(gap, 3),
        "brake_release_vs_steer_build": None if release_ratio is None else round(release_ratio, 2),
        "last_downshift_vs_apex_m": None if last_ds is None else round(last_ds, 1),
        "mrp_m": round(float(s[k]), 1),
        "mrp_vs_apex_m": round(float(s[k] - apex), 1),
        "mrp_kmh": round(float(v[k]), 1),
        "mrp_yaw_dps": round(float(np.degrees(yr[k])), 1),
        "rotation_jerk_dps2": None if jerk is None else round(jerk, 1),
        "heading_to_mrp_deg": round(heading, 1),
        "kmh_lost_turn_in_to_mrp": None if kmh_lost is None else round(kmh_lost, 1),
        "throttle_on_vs_mrp_m": round(float(th_on) - float(s[k]), 1) if isinstance(th_on, (int, float)) else None,
        "steer_unwind_at_full_throttle": None if unwind is None else round(unwind, 2),
        "maintenance_throttle_s": round(float(part.sum()) / hz, 2),
        "entry_slip_peak_deg": round(float(slip[lo:hi].max()), 1) if hi > lo else None,
    }


def _consistency(rows: List[Dict[str, Any]], keys) -> Dict[str, Any]:
    """Same statistics as vre-rpy's consistency(): median, IQR, n, correlation with section time."""
    out = {}
    times = np.array([r.get("section_time_s", np.nan) for r in rows], float)
    for key in keys:
        vals = np.array([r.get(key) if r.get(key) is not None else np.nan for r in rows], float)
        ok = np.isfinite(vals)
        if ok.sum() < 3:
            continue
        q1, q3 = np.percentile(vals[ok], [25, 75])
        both = ok & np.isfinite(times)
        r = float(np.corrcoef(vals[both], times[both])[0, 1]) if both.sum() >= 5 and np.std(vals[both]) > 0 else None
        out[key] = {"median": round(float(np.median(vals[ok])), 3), "iqr": round(float(q3 - q1), 3), "n": int(ok.sum()),
                    "r_with_time": None if r is None else round(r, 3),
                    "matters": bool(r is not None and abs(r) >= 0.4 and both.sum() >= 8)}
    return out


def augment(analysis: Dict[str, Any], frames_root: Path) -> int:
    """Merge rotation metrics into ``analysis`` in place from ``frames_root/<label>/lap_NN.json``.

    Returns the number of corner passes measured. Laps without frames are left as they were.
    """
    windows = {f"{w['corner']}#{w['index']}": w for w in analysis.get("windows") or []}
    count = 0
    for label, drv in (analysis.get("drivers") or {}).items():
        cache: Dict[int, Optional[Dict[str, Any]]] = {}
        for key, corner in (drv.get("corners") or {}).items():
            w = windows.get(key)
            if not w:
                continue
            for lap in corner.get("laps") or []:
                if not lap.get("ok"):
                    continue
                li = lap.get("lap_index")
                if li not in cache:
                    p = Path(frames_root) / label / f"lap_{int(li):02d}.json"
                    cache[li] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
                fr = cache[li]
                if fr is None:
                    continue
                try:
                    m = corner_lap(fr, w, lap)
                except (KeyError, ValueError, IndexError):
                    m = None
                if m:
                    lap.update(m)
                    count += 1
            corner.setdefault("consistency", {}).update(_consistency(corner.get("laps") or [], METRICS))
            best = corner.get("best_lap")
            if isinstance(best, dict):
                src = next((l for l in corner.get("laps") or [] if l.get("lap_index") == best.get("lap_index")), None)
                if src:
                    best.update({k: src[k] for k in METRICS if k in src})
    analysis["rotation_metrics"] = {"schema": "vre.rotation.v1", "metrics": list(METRICS), "passes": count}
    return count


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Add rotation metrics (MRP, rotation build, throttle timing) to a Lap Studio bundle")
    ap.add_argument("bundle", type=Path, help="exports/<bundle> directory")
    ap.add_argument("--no-recoach", action="store_true", help="only rewrite analysis.json")
    a = ap.parse_args(argv)
    ap_path = a.bundle / "analysis.json"
    analysis = json.loads(ap_path.read_text(encoding="utf-8"))
    n = augment(analysis, a.bundle / "frames")
    ap_path.write_text(json.dumps(analysis, default=float), encoding="utf-8")
    print(f"rotation metrics: {n} corner passes")
    if not a.no_recoach:
        from .acc_coach import run as coach_run
        from .reviews import auto_breakdown

        sp = a.bundle / "setup.json"
        setup = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else None
        coaching = coach_run(analysis, setup)
        (a.bundle / "coaching.json").write_text(json.dumps(coaching, default=float), encoding="utf-8")
        (a.bundle / "reviews").mkdir(exist_ok=True)
        (a.bundle / "reviews" / "auto.json").write_text(json.dumps(auto_breakdown(analysis, coaching), default=float), encoding="utf-8")
        for f in coaching.get("fixes") or []:
            print(f"FIX  {f['title']}  ({f['pace_impact_s']:.2f}s, {f['confidence']})\n     drill: {f['drill']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
