"""ACC telemetry → VRE session/lap JSON (shared by rpy, shm, MoTeC paths)."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = 1
CHANNEL_VERSION = 2

ACC_SOURCES = frozenset({"acc_rpy", "acc_shm", "acc_motec"})


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_sessions_root() -> str:
    repo = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".."),
    )
    return os.path.join(repo, "data", "sessions_acc")


def new_session_dir(
    sessions_root: str | None,
    track: str,
    car: str,
) -> tuple[str, str]:
    """Create session folder + laps/; returns (session_dir, session_id)."""
    base = sessions_root or _default_sessions_root()
    ts = time.strftime("%Y-%m-%d_%H%M%S")
    ms = int((time.time() % 1.0) * 1000)
    safe_track = (track or "unknown").replace(" ", "_").lower()
    session_id = "%s_%03d_%s" % (ts, ms, safe_track)
    session_dir = os.path.join(base, session_id)
    laps_dir = os.path.join(session_dir, "laps")
    os.makedirs(laps_dir, exist_ok=True)
    readme = os.path.join(session_dir, "README.txt")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write(
            "Virtual Race Engineer session (ACC)\n"
            "Track: %s\nCar: %s\nStarted: %s\n" % (track, car, ts)
        )
    return session_dir, session_id


def write_session_start(
    session_dir: str,
    *,
    track: str,
    car: str,
    source: str,
    phase: str = "LEARNING",
    baseline_setup: str = "",
    track_config: str = "",
    extras: Mapping[str, Any] | None = None,
) -> None:
    if source not in ACC_SOURCES:
        raise ValueError("source must be one of %s" % sorted(ACC_SOURCES))
    jsonl_path = os.path.join(session_dir, "session.jsonl")
    record: dict[str, Any] = {
        "record_type": "session_start",
        "schema_version": SCHEMA_VERSION,
        "timestamp": _iso_now(),
        "game": "acc",
        "source": source,
        "track": track,
        "track_config": track_config,
        "car": car,
        "phase": phase,
        "baseline_setup": baseline_setup,
        "channel_version": CHANNEL_VERSION,
    }
    if extras:
        record.update(dict(extras))
    with open(jsonl_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, separators=(",", ":")) + "\n")


def append_session_record(session_dir: str, record: Mapping[str, Any]) -> None:
    jsonl_path = os.path.join(session_dir, "session.jsonl")
    rec = dict(record)
    if "timestamp" not in rec:
        rec["timestamp"] = _iso_now()
    if "schema_version" not in rec:
        rec["schema_version"] = SCHEMA_VERSION
    with open(jsonl_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, separators=(",", ":")) + "\n")


def normalize_sample(raw: Mapping[str, Any], source: str | None = None) -> dict[str, Any]:
    """Map a loose ACC sample dict into schema-aligned lap sample fields."""
    if source and source not in ACC_SOURCES:
        raise ValueError("source must be one of %s" % sorted(ACC_SOURCES))

    out: dict[str, Any] = {}

    def pick_float(*keys: str, ndigits: int = 3) -> float | None:
        for key in keys:
            if key in raw and raw[key] is not None:
                return round(float(raw[key]), ndigits)
        return None

    spline = pick_float("spline", "normalizedCarPosition", ndigits=4)
    if spline is not None:
        out["spline"] = spline

    speed = pick_float("speed_kmh", "speedKmh", "Speed", ndigits=1)
    if speed is not None:
        out["speed_kmh"] = speed

    throttle = pick_float("throttle", "gas", "Throttle", ndigits=3)
    if throttle is not None:
        out["throttle"] = throttle

    brake = pick_float("brake", "Brake", ndigits=3)
    if brake is not None:
        out["brake"] = brake

    steer = pick_float("steer_deg", "Steering", "Steed", ndigits=2)
    if steer is None and "steerAngle" in raw:
        steer = round(float(raw["steerAngle"]) * 100.0, 2)
    if steer is not None:
        out["steer_deg"] = steer

    if "gear" in raw and raw["gear"] is not None:
        out["gear"] = int(raw["gear"])
    elif "Gear" in raw and raw["Gear"] is not None:
        out["gear"] = int(raw["Gear"])

    rpm_val = raw.get("rpm", raw.get("rpms", raw.get("RPM")))
    if rpm_val is not None:
        out["rpm"] = int(rpm_val)

    lat = pick_float("acc_g_lat", ndigits=3)
    lon = pick_float("acc_g_long", ndigits=3)
    acc = raw.get("accG")
    if acc is not None and len(acc) >= 3:
        if lat is None:
            lat = round(float(acc[0]), 3)
        if lon is None:
            lon = round(float(acc[2]), 3)
    if lat is not None:
        out["acc_g_lat"] = lat
    if lon is not None:
        out["acc_g_long"] = lon

    px = pick_float("pos_x", ndigits=2)
    pz = pick_float("pos_z", ndigits=2)
    if px is None or pz is None:
        pos = raw.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) >= 3:
            if px is None:
                px = round(float(pos[0]), 2)
            if pz is None:
                pz = round(float(pos[2]), 2)
    if px is not None:
        out["pos_x"] = px
    if pz is not None:
        out["pos_z"] = pz

    heading = pick_float("heading", ndigits=4)
    if heading is not None:
        out["heading"] = heading

    core = raw.get("tyre_core") or raw.get("tyreCoreTemperature") or raw.get("tyreTemp")
    if core is not None:
        out["tyre_core"] = [round(float(v), 1) for v in core]

    psi = raw.get("tyre_psi") or raw.get("wheelsPressure") or raw.get("wheelPressure")
    if psi is not None:
        out["tyre_psi"] = [round(float(v), 2) for v in psi]

    tc_f = pick_float("tc", "tc_intervention", ndigits=3)
    if tc_f is not None:
        out["tc_intervention"] = tc_f

    abs_f = pick_float("abs", "abs_intervention", ndigits=3)
    if abs_f is not None:
        out["abs_intervention"] = abs_f

    if source:
        out["ingest_source"] = source

    for key in ("corner", "phase"):
        if key in raw and raw[key]:
            out[key] = raw[key]

    return out


def write_lap(
    session_dir: str,
    lap_num: int,
    lap_time_ms: int,
    samples: Sequence[Mapping[str, Any]],
    extras: Mapping[str, Any] | None = None,
    *,
    source: str | None = None,
    write_summary: bool = True,
) -> str:
    normed = [normalize_sample(s, source=source) for s in samples]
    payload: dict[str, Any] = {
        "lap": lap_num,
        "lap_time_ms": int(lap_time_ms),
        "samples": normed,
        "corner_summaries": [],
        "sample_count_raw": len(samples),
    }
    if source:
        payload["source"] = source
    if extras:
        payload.update(dict(extras))

    lap_name = "lap_%02d.json" % lap_num
    lap_path = os.path.join(session_dir, "laps", lap_name)
    with open(lap_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
        fh.write("\n")

    if write_summary:
        append_session_record(
            session_dir,
            {
                "record_type": "lap_summary",
                "lap": lap_num,
                "lap_time_ms": int(lap_time_ms),
                "lap_type": "flying",
                "counted": True,
            },
        )
    return lap_path