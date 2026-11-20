"""Poll ACC shared memory and write VRE session folders (Windows + ACC running)."""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from .normalize import new_session_dir, normalize_sample, write_lap, write_session_start
from .shm_structs import (
    ACC_GRAPHICS_MAP,
    ACC_PHYSICS_MAP,
    ACC_STATIC_MAP,
    SPageFileGraphic,
    SPageFilePhysics,
    SPageFileStatic,
    open_shared_memory,
    read_static_identity,
)

AC_STATUS_LIVE = 2


def _player_xyz(graphics: SPageFileGraphic) -> tuple[float, float, float]:
    pid = int(graphics.playerCarID)
    if pid < 0 or pid >= 60:
        return 0.0, 0.0, 0.0
    coords = graphics.carCoordinates[pid]
    return float(coords[0]), float(coords[1]), float(coords[2])


def sample_from_shm(
    physics: SPageFilePhysics,
    graphics: SPageFileGraphic,
    steering_lock_deg: float,
) -> dict[str, Any]:
    if steering_lock_deg > 0:
        steer_deg = float(physics.steerAngle) * steering_lock_deg
    else:
        steer_deg = float(physics.steerAngle) * 100.0

    px, _, pz = _player_xyz(graphics)
    raw = {
        "spline": float(graphics.normalizedCarPosition),
        "speed_kmh": float(physics.speedKmh),
        "throttle": float(physics.gas),
        "brake": float(physics.brake),
        "steer_deg": steer_deg,
        "gear": int(physics.gear),
        "rpms": int(physics.rpms),
        "accG": [float(physics.accG[i]) for i in range(3)],
        "pos": (px, 0.0, pz),
        "heading": float(physics.heading),
        "tyre_core": [float(physics.tyreCoreTemperature[i]) for i in range(4)],
        "tyre_psi": [float(physics.wheelsPressure[i]) for i in range(4)],
        "tc": float(physics.tc),
        "abs": float(physics.abs),
        "tc_level": int(graphics.TC),
        "tc_cut": int(graphics.TCCut),
        "abs_level": int(graphics.ABS),
        "engine_map": int(graphics.EngineMap),
    }
    return normalize_sample(raw, source="acc_shm")


def run_logger(
    hz: float,
    out_root: str | None,
    steering_lock_deg: float,
) -> int:
    if sys.platform != "win32":
        print(
            "ACC shared memory is only available on Windows while the game is running.",
            file=sys.stderr,
        )
        print("Waiting for SHM (will retry indefinitely)...", flush=True)

    period = 1.0 / max(1.0, float(hz))
    session_dir: str | None = None
    last_completed = -1
    lap_samples: list[dict[str, Any]] = []
    current_lap = 0

    while True:
        physics, phys_buf = open_shared_memory(ACC_PHYSICS_MAP, SPageFilePhysics)
        graphics, gfx_buf = open_shared_memory(ACC_GRAPHICS_MAP, SPageFileGraphic)
        static, static_buf = open_shared_memory(ACC_STATIC_MAP, SPageFileStatic)

        if physics is None or graphics is None or static is None:
            for buf in (phys_buf, gfx_buf, static_buf):
                if buf is not None:
                    buf.close()
            time.sleep(1.0)
            continue

        track, car = read_static_identity(static)
        if session_dir is None:
            session_dir, sid = new_session_dir(out_root, track, car)
            write_session_start(
                session_dir,
                track=track,
                car=car,
                source="acc_shm",
                extras={"session_id": sid},
            )
            print("Session %s → %s" % (sid, session_dir), flush=True)

        if int(graphics.status) != AC_STATUS_LIVE:
            time.sleep(period)
            continue

        completed = int(graphics.completedLaps)
        if last_completed < 0:
            last_completed = completed
            current_lap = max(1, completed + 1)

        if completed > last_completed and lap_samples:
            lap_time = int(graphics.iLastTime)
            write_lap(
                session_dir,
                current_lap,
                lap_time,
                lap_samples,
                source="acc_shm",
            )
            print("Lap %d saved (%d ms, %d samples)" % (current_lap, lap_time, len(lap_samples)))
            lap_samples = []
            last_completed = completed
            current_lap = completed + 1

        lap_samples.append(sample_from_shm(physics, graphics, steering_lock_deg))
        time.sleep(period)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACC shared-memory session logger → VRE JSON")
    parser.add_argument("--hz", type=float, default=50.0, help="Poll rate (default 50)")
    parser.add_argument(
        "--out",
        dest="out_root",
        default=None,
        help="Sessions root (default: repo data/sessions_acc)",
    )
    parser.add_argument(
        "--steering-lock",
        type=float,
        default=400.0,
        help="Steering lock in degrees for steer_deg (296 GT3 default 400)",
    )
    args = parser.parse_args(argv)
    try:
        run_logger(args.hz, args.out_root, args.steering_lock)
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())