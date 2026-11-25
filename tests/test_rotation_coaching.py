"""Rotation metrics (MRP, rotation build, speed shed while rotating) and the coaching they drive."""

import json

import numpy as np

from external.query_tools.coach import habits, rotation
from external.query_tools.coach.distiller import distill

WINDOW = {"corner": "T1", "index": 0, "s0_m": 100.0, "s1_m": 700.0, "apex_m": 400.0, "braked": True}


def _frame(snap: bool, v_mrp: float):
    """A right-hander: braking 150-340 m, turn-in at 340 m, peak rotation ~385 m, throttle from 400 m.

    ``snap``: rotation arrives in one jump right after turn-in instead of building towards the MRP.
    """
    s = np.arange(0.0, 800.0, 1.0)
    v = np.interp(s, [0, 150, 340, 385, 450, 800], [220, 220, v_mrp + (2 if snap else 12), v_mrp, v_mrp + 15, 200])
    t = np.concatenate([[0.0], np.cumsum(1.0 / (v[1:] / 3.6))])
    if snap:
        yr = np.interp(s, [0, 340, 352, 385, 450, 800], [0, 0, 40, 45, 5, 0])
    else:
        yr = np.interp(s, [0, 340, 385, 450, 800], [0, 0, 45, 5, 0])
    yaw = np.degrees(np.concatenate([[0.0], np.cumsum(np.radians(yr[1:]) * np.diff(t))]))
    steer = yr * 2.0
    thr = np.where(s >= 400, 1.0, 0.0)
    g_lon = np.where(s >= 400, 0.3, -1.0)
    brake = np.interp(s, [0, 150, 160, 300, 340, 360, 800], [0, 0, 1, 1, 0.3 if not snap else 0.0, 0, 0])
    gear = np.where(s < 250, 5, np.where(s < 300, 4, 3)).astype(float)
    return {"s_m": s.tolist(), "t": t.tolist(), "yaw_deg": yaw.tolist(), "speed_kmh": v.tolist(),
            "steer_deg": steer.tolist(), "throttle": thr.tolist(), "throttle_masked": thr.tolist(),
            "g_lon": g_lon.tolist(), "g_lat": (yr / 30).tolist(), "brake": brake.tolist(), "gear": gear.tolist(),
            "slip_deg": (yr / 10).tolist()}


LAP = {"ok": True, "turn_in_m": 340.0, "throttle_on_m": 400.0, "full_throttle_m": 420.0, "section_time_s": 10.0}


def test_mrp_is_peak_yaw_rate_and_snap_is_measured():
    smooth = rotation.corner_lap(_frame(False, 70.0), WINDOW, LAP)
    snap = rotation.corner_lap(_frame(True, 62.0), WINDOW, LAP)
    assert abs(smooth["mrp_m"] - 385) < 8 and abs(smooth["mrp_vs_apex_m"] + 15) < 8
    assert smooth["throttle_on_vs_mrp_m"] > 0  # throttle after the MRP
    assert snap["rotation_jerk_dps2"] > 1.5 * smooth["rotation_jerk_dps2"]
    assert smooth["kmh_lost_turn_in_to_mrp"] > snap["kmh_lost_turn_in_to_mrp"] + 8  # smooth lap slows while rotating
    assert snap["mrp_kmh"] < smooth["mrp_kmh"] - 3
    assert smooth["last_downshift_vs_apex_m"] == -100.0  # 4 -> 3 at 300 m, apex 400 m
    assert abs(smooth["mrp_vs_vmin_m"]) < 8  # MRP = slowest point
    assert 0.3 < smooth["rotation_before_throttle_frac"] < 1.0
    assert smooth["rotation_plateau_s"] is not None


def test_missing_optional_channels_only_drop_their_metrics():
    f = _frame(False, 70.0)
    for k in ("g_lat", "brake", "gear"):
        f.pop(k)
    m = rotation.corner_lap(f, WINDOW, LAP)
    assert m["mrp_m"] and m["grip_gap_frac"] is None and m["last_downshift_vs_apex_m"] is None


def test_flat_corner_skips_the_closing_spiral_metrics():
    m = rotation.corner_lap(_frame(False, 70.0), dict(WINDOW, braked=False), LAP)
    assert m["rotation_jerk_dps2"] is None and m["kmh_lost_turn_in_to_mrp"] is None and m["mrp_m"]


def _bundle(tmp_path):
    laps_me, laps_ref = [], []
    for i in range(1, 6):
        (tmp_path / "frames" / "You").mkdir(parents=True, exist_ok=True)
        (tmp_path / "frames" / "You" / f"lap_{i:02d}.json").write_text(json.dumps(_frame(True, 61.0 + 0.3 * i)))
        laps_me.append(dict(LAP, lap_index=i, section_time_s=10.4 + 0.02 * i))
    (tmp_path / "frames" / "Ref").mkdir(parents=True, exist_ok=True)
    (tmp_path / "frames" / "Ref" / "lap_01.json").write_text(json.dumps(_frame(False, 70.0)))
    laps_ref.append(dict(LAP, lap_index=1))
    return {"labels": {"me": "You", "ref": "Ref"}, "windows": [WINDOW],
            "corner_loss_best_vs_ref": [{"corner": "T1", "index": 0, "loss_s": 0.4}],
            "pack": {"corners": [{"display_name": "T1", "apex_m": 400.0, "start_m": 330.0, "end_m": 470.0}]},
            "drivers": {"You": {"corners": {"T1#0": {"laps": laps_me, "best_lap": {"lap_index": 1}}}},
                        "Ref": {"corners": {"T1#0": {"laps": laps_ref, "best_lap": {"lap_index": 1}}}}}}


def test_augment_feeds_habits_and_one_rotation_fix(tmp_path):
    analysis = _bundle(tmp_path)
    assert rotation.augment(analysis, tmp_path / "frames") == 6
    me = analysis["drivers"]["You"]["corners"]["T1#0"]
    assert me["consistency"]["rotation_jerk_dps2"]["n"] == 5 and "mrp_m" in me["best_lap"]
    h = habits.detect(analysis)
    ids = {x["id"] for x in h["habits"]}
    assert {"rotation_snap", "brakes_then_turns", "rotates_at_lower_speed"} <= ids
    c = distill(analysis, h)
    rot = [f for f in c["fixes"] if f["mental_model"] == "build_rotation"]
    assert len(rot) == 1  # one fix per corner and group, carrying the sibling habits' sentences
    assert "°/s²" in rot[0]["drill"] and "km/h" in rot[0]["drill"]
