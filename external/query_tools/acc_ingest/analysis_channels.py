"""Pure analysis maths for ACC MoTeC / VRE Motec overlays (no I/O)."""

from __future__ import annotations

import math
from typing import Sequence


def coast_mask(
    throttle: Sequence[float],
    brake: Sequence[float],
    speed_kmh: Sequence[float],
    *,
    thr_max: float = 0.05,
    brk_max: float = 0.05,
    speed_min: float = 40.0,
) -> list[float]:
    """1.0 where coasting (both pedals low) above speed_min, else 0.0."""
    n = min(len(throttle), len(brake), len(speed_kmh))
    out: list[float] = []
    for i in range(n):
        if (
            float(throttle[i]) < thr_max
            and float(brake[i]) < brk_max
            and float(speed_kmh[i]) > speed_min
        ):
            out.append(1.0)
        else:
            out.append(0.0)
    return out


def pedal_gap_s(
    throttle: Sequence[float],
    brake: Sequence[float],
    hz: float,
    *,
    brk_on: float = 0.12,
    brk_off: float = 0.05,
    thr_on: float = 0.05,
) -> list[float]:
    """Per-sample gap duration (s) after brake release until throttle; 0 when not in a gap."""
    n = min(len(throttle), len(brake))
    out = [0.0] * n
    i = 0
    dt = 1.0 / max(hz, 1e-6)
    while i < n:
        if float(brake[i]) >= brk_on:
            while i < n and float(brake[i]) > brk_off:
                i += 1
            start = i
            while (
                i < n
                and float(throttle[i]) < thr_on
                and float(brake[i]) < brk_off
            ):
                i += 1
            gap = (i - start) * dt
            for j in range(start, i):
                out[j] = gap
        else:
            i += 1
    return out


def damper_velocity_mm_s(travel_mm: Sequence[float], hz: float) -> list[float]:
    """Finite-difference damper velocity (mm/s). Compression positive if travel increases."""
    if not travel_mm:
        return []
    dt = 1.0 / max(hz, 1e-6)
    out = [0.0]
    for i in range(1, len(travel_mm)):
        out.append((float(travel_mm[i]) - float(travel_mm[i - 1])) / dt)
    return out


def rake_proxy_mm(
    travel_fl: Sequence[float],
    travel_fr: Sequence[float],
    travel_rl: Sequence[float],
    travel_rr: Sequence[float],
) -> list[float]:
    """Front-mean travel minus rear-mean travel (mm). Positive ≈ more front compression / nose down."""
    n = min(len(travel_fl), len(travel_fr), len(travel_rl), len(travel_rr))
    out: list[float] = []
    for i in range(n):
        f = 0.5 * (float(travel_fl[i]) + float(travel_fr[i]))
        r = 0.5 * (float(travel_rl[i]) + float(travel_rr[i]))
        out.append(f - r)
    return out


def yaw_rate_deg_s(roty_rad_s: Sequence[float]) -> list[float]:
    return [float(v) * (180.0 / math.pi) for v in roty_rad_s]


def us_os(
    speed_kmh: Sequence[float],
    steer_deg: Sequence[float],
    g_lat: Sequence[float],
    *,
    steering_lock_deg: float = 400.0,
    wheelbase_m: float = 2.6,
) -> list[float]:
    """Simple balance indicator: steer_deg - expected_steer from v and ay.

    Negative ≈ understeer (more wheel than kinematics need), positive ≈ oversteer.
    Requires consistent units; g_lat in m/s^2 (ACC MoTeC). Not a tyre model —
    use for trends / Motec worksheet parity only.
    """
    n = min(len(speed_kmh), len(steer_deg), len(g_lat))
    out: list[float] = []
    lock = max(steering_lock_deg, 1.0)
    for i in range(n):
        v = float(speed_kmh[i]) / 3.6
        ay = float(g_lat[i])
        if v < 5.0:
            out.append(0.0)
            continue
        # yaw rate ≈ ay/v; kinematic steer ≈ (L/v)*r * (180/pi) scaled to wheel
        r = ay / v
        expected = (wheelbase_m * r) * (180.0 / math.pi)
        # normalize steer to approx road-wheel using lock as full-lock scale
        road = float(steer_deg[i]) * (15.0 / lock)  # ~15° road at full lock heuristic
        out.append(road - expected)
    return out


def wheelspin_lock(
    speed_kmh: Sequence[float],
    wheel_lf: Sequence[float],
    wheel_rf: Sequence[float],
    wheel_lr: Sequence[float],
    wheel_rr: Sequence[float],
    *,
    spin_thresh_kmh: float = 8.0,
    lock_thresh_kmh: float = 8.0,
) -> tuple[list[float], list[float]]:
    """Return (spin_flag, lock_flag) using max rear vs ground and min front vs ground.

    Wheel speeds assumed m/s (ACC MoTeC); converted to km/h.
    """
    n = min(
        len(speed_kmh),
        len(wheel_lf),
        len(wheel_rf),
        len(wheel_lr),
        len(wheel_rr),
    )
    spin: list[float] = []
    lock: list[float] = []
    for i in range(n):
        g = float(speed_kmh[i])
        fl = float(wheel_lf[i]) * 3.6
        fr = float(wheel_rf[i]) * 3.6
        lr = float(wheel_lr[i]) * 3.6
        rr = float(wheel_rr[i]) * 3.6
        rear = max(lr, rr)
        front = min(fl, fr)
        spin.append(1.0 if rear - g > spin_thresh_kmh else 0.0)
        lock.append(1.0 if g - front > lock_thresh_kmh and g > 30 else 0.0)
    return spin, lock


def tc_active(tc: Sequence[float], *, thresh: float = 0.1) -> list[float]:
    return [1.0 if float(v) > thresh else 0.0 for v in tc]


def resample_nearest(values: Sequence[float], target_n: int) -> list[float]:
    if target_n <= 0:
        return []
    if not values:
        return [0.0] * target_n
    if len(values) == target_n:
        return [float(v) for v in values]
    last = len(values) - 1
    if target_n == 1:
        return [float(values[0])]
    return [
        float(values[int(round(i * last / (target_n - 1)))])
        for i in range(target_n)
    ]
