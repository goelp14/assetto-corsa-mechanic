"""Repair dynamics channels in VRE sessions recorded before channel_version 2.

Older archives logged AC's vertical accG as acc_g_lat, its lateral accG as
acc_g_long, a yaw rate stuck at 0 and a body slip angle built from the
vertical velocity. Lateral g is recovered directly; yaw rate, body slip,
longitudinal g and the understeer angle are rebuilt from position, heading and
speed, which are trustworthy in every archive.
"""

from __future__ import print_function

import json
import math
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CARS_DIR = os.path.join(REPO, "ac_app", "config", "cars")
G = 9.81
MIN_SPEED_MS = 30.0 / 3.6
MIN_BALANCE_SPEED_MS = 15.0
MIN_BALANCE_AY_G = 0.3
CURRENT_CHANNEL_VERSION = 2

_session_cache = {}


def _wrap_pi(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def _load_car(car_id):
    cfg = {"wheelbase_m": 2.6, "max_road_wheel_deg": 20.0}
    path = os.path.join(CARS_DIR, "%s.json" % car_id) if car_id else ""
    if path and os.path.isfile(path):
        with open(path) as fh:
            data = json.load(fh)
        for key in cfg:
            if data.get(key):
                cfg[key] = float(data[key])
    return cfg


def session_info(session_dir):
    """(legacy, car_cfg) for a raw session dir; non-session dirs are never legacy."""
    session_dir = os.path.abspath(session_dir)
    if session_dir in _session_cache:
        return _session_cache[session_dir]
    legacy, car_id = False, ""
    jsonl = os.path.join(session_dir, "session.jsonl")
    if os.path.isfile(jsonl):
        with open(jsonl) as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("record_type") == "session_start":
                    legacy = rec.get("channel_version", 1) < CURRENT_CHANNEL_VERSION
                    car_id = rec.get("car", "")
                    break
    info = (legacy, _load_car(car_id) if legacy else None)
    _session_cache[session_dir] = info
    return info


def _has_pos(s):
    return s.get("pos_x") is not None and s.get("pos_z") is not None and not s.get("pos_projected")


def _travel_and_dt(samples):
    """Per-sample travel direction (rad, world x/z) and central-difference dt.

    dt is None where positions are missing and 0 below MIN_SPEED_MS.
    """
    n = len(samples)
    travel = [None] * n
    dts = [None] * n
    for i in range(1, n - 1):
        a, b = samples[i - 1], samples[i + 1]
        if not (_has_pos(a) and _has_pos(b)):
            continue
        dx = b["pos_x"] - a["pos_x"]
        dz = b["pos_z"] - a["pos_z"]
        dist = math.hypot(dx, dz)
        v = (a.get("speed_kmh", 0.0) + b.get("speed_kmh", 0.0)) / 7.2
        if v < MIN_SPEED_MS or dist < 0.05:
            dts[i] = 0.0
            continue
        travel[i] = math.atan2(dz, dx)
        dts[i] = dist / v
    return travel, dts


def _position_lag(samples, travel, max_lag=6):
    """Samples by which archived positions trail the physics heading.

    carCoordinates comes from the graphics page and lags heading by a few
    frames, which otherwise shows up as large fake body slip in fast corners.
    """
    best, best_spread = 0, None
    for lag in range(0, max_lag + 1):
        resid = []
        for i in range(len(samples)):
            j = i + lag
            if j >= len(samples) or travel[j] is None or "heading" not in samples[i]:
                continue
            resid.append(_wrap_pi(travel[j] - samples[i]["heading"] - math.pi / 2.0))
        if len(resid) < 20:
            continue
        spread = sum(r * r for r in resid) / len(resid)
        if best_spread is None or spread < best_spread:
            best, best_spread = lag, spread
    return best


def repair_samples(samples, car_cfg):
    """Return repaired copies of legacy samples, kept in recorded (time) order."""
    out = [dict(s) for s in samples]
    road_scale = car_cfg["max_road_wheel_deg"] / 57.2958
    wheelbase = car_cfg["wheelbase_m"]
    for s in out:
        raw_lat = s.pop("acc_g_long", None)
        raw_vert = s.pop("acc_g_lat", None)
        if raw_lat is not None:
            s["acc_g_lat"] = round(-raw_lat, 3)
        if raw_vert is not None:
            s["acc_g_vert"] = raw_vert
        if "steer_deg" in s:
            s["steer_road_deg"] = round(s["steer_deg"] * road_scale, 2)
        for key in ("beta_deg", "yaw_rate", "delta_us_deg"):
            s.pop(key, None)

    travel, dts = _travel_and_dt(out)
    lag = _position_lag(out, travel)

    for i in range(1, len(out) - 1):
        a, s, b = out[i - 1], out[i], out[i + 1]
        dt = dts[i]
        if dt is None or "heading" not in a or "heading" not in b:
            continue
        if dt <= 0:
            s["beta_deg"] = 0.0
            s["yaw_rate"] = 0.0
            continue
        v = (a.get("speed_kmh", 0.0) + b.get("speed_kmh", 0.0)) / 7.2
        j = i + lag
        if j < len(out) and travel[j] is not None:
            beta = math.degrees(_wrap_pi(travel[j] - (s["heading"] + math.pi / 2.0)))
            s["beta_deg"] = round(max(-90.0, min(90.0, beta)), 2)
        yaw = _wrap_pi(b["heading"] - a["heading"]) / dt
        s["yaw_rate"] = round(yaw, 4)
        s["acc_g_long"] = round((b.get("speed_kmh", 0.0) - a.get("speed_kmh", 0.0)) / 3.6 / dt / G, 3)
        ay = v * yaw
        if v >= MIN_BALANCE_SPEED_MS and abs(ay) >= MIN_BALANCE_AY_G * G and "steer_road_deg" in s:
            turn = 1.0 if ay >= 0 else -1.0
            delta_ack = wheelbase * yaw / v
            delta_us = turn * (math.radians(s["steer_road_deg"]) - delta_ack)
            s["delta_us_deg"] = round(math.degrees(delta_us), 2)
    return out


def read_lap(path):
    """Load a lap JSON, repairing legacy dynamics channels when the session predates the fix."""
    with open(path) as fh:
        data = json.load(fh)
    legacy, car_cfg = session_info(os.path.dirname(os.path.dirname(os.path.abspath(path))))
    if legacy:
        data["samples"] = repair_samples(data.get("samples", []), car_cfg)
        data["channels_repaired"] = True
    return data
