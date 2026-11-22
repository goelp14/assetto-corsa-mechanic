"""Unit tests for analysis_channels maths."""

from __future__ import annotations

import math

from external.query_tools.acc_ingest.analysis_channels import (
    coast_mask,
    damper_velocity_mm_s,
    pedal_gap_s,
    rake_proxy_mm,
    resample_nearest,
    us_os,
    wheelspin_lock,
    yaw_rate_deg_s,
)


def test_coast_mask_basic():
    thr = [0.0, 0.5, 0.0]
    brk = [0.0, 0.0, 0.2]
    spd = [80.0, 80.0, 80.0]
    assert coast_mask(thr, brk, spd) == [1.0, 0.0, 0.0]


def test_pedal_gap_after_brake():
    # brake on, then off, then throttle after 3 samples @10Hz => 0.3s gap
    brk = [0.5, 0.5, 0.0, 0.0, 0.0, 0.0]
    thr = [0.0, 0.0, 0.0, 0.0, 0.0, 0.2]
    gap = pedal_gap_s(thr, brk, hz=10.0)
    assert abs(gap[2] - 0.3) < 1e-9
    assert gap[2] == gap[3] == gap[4]
    assert gap[5] == 0.0


def test_damper_velocity():
    travel = [0.0, 10.0, 10.0]  # 10mm in 0.1s @10Hz
    vel = damper_velocity_mm_s(travel, hz=10.0)
    assert vel[0] == 0.0
    assert abs(vel[1] - 100.0) < 1e-6
    assert abs(vel[2]) < 1e-6


def test_rake_proxy():
    fl = fr = [20.0]
    rl = rr = [10.0]
    assert rake_proxy_mm(fl, fr, rl, rr) == [10.0]


def test_yaw_rate():
    assert abs(yaw_rate_deg_s([math.pi])[0] - 180.0) < 1e-6


def test_us_os_straight():
    # high speed, zero ay, zero steer → ~0
    out = us_os([200.0], [0.0], [0.0])
    assert abs(out[0]) < 1e-6


def test_wheelspin_lock():
    # ground 100 km/h; rear wheel 30 m/s = 108 km/h → spin
    # front wheel 20 m/s = 72 → lock when ground high
    spin, lock = wheelspin_lock(
        [100.0],
        [20.0],
        [20.0],
        [32.0],  # 115.2 km/h rear vs 100 ground
        [32.0],
    )
    assert spin == [1.0]
    assert lock == [1.0]


def test_resample_nearest():
    assert resample_nearest([0.0, 10.0], 2) == [0.0, 10.0]
    assert len(resample_nearest([1.0, 2.0, 3.0], 5)) == 5
    assert resample_nearest([7.0], 3) == [7.0, 7.0, 7.0]
