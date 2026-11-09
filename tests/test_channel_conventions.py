import json
import math
import os
import sys
from types import SimpleNamespace

import telemetry_ingest
from car_profile import build_car_profile, has_downforce, parse_ini
from telemetry_ingest import TelemetryIngest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "external", "query_tools"))
from channel_repair import read_lap  # noqa: E402


def _sim(heading, acc_g=(0.0, 0.0, 0.0), steer=0.0):
    physics = SimpleNamespace(
        speedKmh=100.0, gas=0.5, brake=0.0, steerAngle=steer,
        velocity=(0.0, 0.0, 27.8), accG=acc_g, heading=heading, roll=0.0,
        wheelSlip=(0, 0, 0, 0), wheelLoad=(0, 0, 0, 0), camberRAD=(0, 0, 0, 0),
        suspensionTravel=(0, 0, 0, 0), tyreCoreTemperature=(0, 0, 0, 0),
        wheelsPressure=(0, 0, 0, 0), gear=3, rpms=8000,
    )
    graphics = SimpleNamespace(
        normalizedCarPosition=0.5, completedLaps=1, currentSectorIndex=0,
        isInPit=0, carCoordinates=(0.0, 0.0, 0.0),
    )
    static = SimpleNamespace(
        suspensionMaxTravel=(0.1, 0.1, 0.1, 0.1), track="t", carModel="c",
        trackConfiguration="", trackSPlineLength=1000.0,
    )
    return SimpleNamespace(physics=physics, graphics=graphics, static=static)


def test_ingest_maps_ac_axes_and_differentiates_heading(monkeypatch):
    monkeypatch.setattr(telemetry_ingest, "ac", None)
    sim = _sim(0.0)
    ingest = TelemetryIngest(sim)
    ingest.set_steer_range(22.5)
    ingest.sample(0.02)
    sim.physics.heading = 0.01
    sim.physics.accG = (-1.4, 0.05, -0.3)
    sim.physics.steerAngle = 0.4
    f = ingest.sample(0.02)
    assert abs(f.yaw_rate - 0.5) < 1e-9
    assert f.acc_g == (-0.3, 1.4, 0.05)
    assert abs(f.steer_road - math.radians(9.0)) < 1e-9
    assert f.steer == 0.4
    assert f.tyres_out == 0
    sim.physics.numberOfTyresOut = 3
    assert ingest.sample(0.02).tyres_out == 3
    assert f.ffb == 0.0 and f.brake_bias == 0.0
    sim.physics.finalFF = -0.42
    sim.physics.brakeBias = 0.58
    f = ingest.sample(0.02)
    assert f.ffb == -0.42 and f.brake_bias == 0.58
    sim.physics.brakeBias = 12.0
    assert ingest.sample(0.02).brake_bias == 0.0


def test_ingest_reads_tyre_brake_and_ride_height_channels(monkeypatch):
    monkeypatch.setattr(telemetry_ingest, "ac", None)
    sim = _sim(0.0)
    ingest = TelemetryIngest(sim)
    f = ingest.sample(0.02)
    assert f.tyre_temp_imo == () and f.brake_temp == () and f.ride_height == ()
    sim.physics.wheelAngularSpeed = (90.0, 91.0, 95.0, 96.0)
    sim.static.tyreRadius = (0.30, 0.30, 0.33, 0.33)
    sim.physics.tyreTempI = (80.0, 81.0, 85.0, 86.0)
    sim.physics.tyreTempM = (75.0, 76.0, 80.0, 81.0)
    sim.physics.tyreTempO = (70.0, 71.0, 75.0, 76.0)
    sim.physics.brakeTemp = (400.0, 410.0, 300.0, 310.0)
    sim.physics.rideHeight = (0.055, 0.070)
    f = ingest.sample(0.02)
    assert f.wheel_speed == (90.0, 91.0, 95.0, 96.0)
    assert f.tyre_radius == (0.30, 0.30, 0.33, 0.33)
    assert f.tyre_temp_imo[2] == (85.0, 80.0, 75.0)
    assert f.brake_temp == (400.0, 410.0, 300.0, 310.0)
    assert f.ride_height == (0.055, 0.070)
    sim.physics.rideHeight = (55.0, 1e9)
    sim.physics.tyreTempI = (80.0, 81.0, 1e7, 86.0)
    f = ingest.sample(0.02)
    assert f.ride_height == () and f.tyre_temp_imo == ()


CAR_INI = "[CONTROLS]\nSTEER_LOCK=315\nSTEER_RATIO=14.0\n"
WINGLESS = "[WING_0]\nNAME=BODY\nCL_GAIN=1\n[WING_1]\nNAME=BODY_LIFT\nCL_GAIN=1.0\n"
WINGED = WINGLESS + "[WING_2]\nNAME=FRONT\nCL_GAIN=1.0\n"


def test_car_profile_steer_range_and_aero():
    assert not has_downforce(parse_ini(WINGLESS))
    assert has_downforce(parse_ini(WINGED))
    profile = build_car_profile("x", {"car.ini": CAR_INI, "aero.ini": WINGLESS})
    assert profile["max_road_wheel_deg"] == 22.5
    assert profile["lat_g_per_ms"] == 0.0


def _write_session(tmp_path, start_record, samples):
    session = tmp_path / "sess"
    (session / "laps").mkdir(parents=True)
    (session / "session.jsonl").write_text(json.dumps(start_record) + "\n")
    lap = session / "laps" / "lap_1.json"
    lap.write_text(json.dumps({"lap": 1, "samples": samples}))
    return str(lap)


def _right_hander(n=30, radius=20.0, speed_kmh=72.0):
    """Clockwise arc in AC world coords: heading increases, travel = heading + 90 deg."""
    samples = []
    for i in range(n):
        h = i * 0.05
        # Tangent of (cos h, sin h) is (-sin h, cos h) = the travel direction.
        px = radius * math.cos(h)
        pz = radius * math.sin(h)
        samples.append({
            "spline": 0.1 + i * 0.001, "speed_kmh": speed_kmh, "steer_deg": 20.0,
            "acc_g_lat": 0.02, "acc_g_long": -2.0, "beta_deg": 90.0, "yaw_rate": 0.0,
            "pos_x": px, "pos_z": pz, "heading": h,
        })
    return samples


def test_legacy_session_channels_are_rebuilt(tmp_path):
    start = {"record_type": "session_start", "car": "ks_ferrari_312_67"}
    lap = read_lap(_write_session(tmp_path, start, _right_hander()))
    mid = lap["samples"][15]
    assert lap["channels_repaired"]
    assert abs(mid["acc_g_lat"] - 2.0) < 1e-9
    assert mid["acc_g_vert"] == 0.02
    assert abs(mid["yaw_rate"] - 20.0 / 20.0) < 0.01
    assert abs(mid["beta_deg"]) < 0.5
    assert abs(mid["acc_g_long"]) < 1e-6
    assert abs(mid["steer_road_deg"] - 20.0 * 22.5 / 57.2958) < 0.01
    assert "delta_us_deg" in mid


def test_lagging_positions_do_not_create_fake_slip(tmp_path):
    samples = _right_hander(60)
    lag = 2
    for i in range(len(samples) - 1, -1, -1):
        src = samples[max(0, i - lag)]
        samples[i]["pos_x"], samples[i]["pos_z"] = src["pos_x"], src["pos_z"]
    start = {"record_type": "session_start", "car": "ks_ferrari_312_67"}
    lap = read_lap(_write_session(tmp_path, start, samples))
    assert max(abs(s.get("beta_deg", 0.0)) for s in lap["samples"][5:-5]) < 0.5


def test_current_sessions_are_untouched(tmp_path):
    start = {"record_type": "session_start", "car": "c", "channel_version": 2}
    samples = _right_hander(5)
    lap = read_lap(_write_session(tmp_path, start, samples))
    assert "channels_repaired" not in lap
    assert lap["samples"] == samples
