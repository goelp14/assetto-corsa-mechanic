"""Import ACC MoTeC .ld logs into VRE session folders."""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Any, Sequence

from .normalize import new_session_dir, normalize_sample, write_lap, write_session_start

_LDPARSER_HINT = (
    "MoTeC import needs gotzl/ldparser and numpy on PYTHONPATH. "
    "Example: pip install numpy && git clone https://github.com/gotzl/ldparser "
    "&& export PYTHONPATH=$PYTHONPATH:/path/to/ldparser"
)


def _load_ld_data():
    try:
        from ldparser import ldData  # type: ignore
        return ldData
    except ImportError:
        raise ImportError(_LDPARSER_HINT)


def discover_channels(ld_path: str) -> list[str]:
    """List channel names in a .ld file (requires ldparser)."""
    ld_data_cls = _load_ld_data()
    data = ld_data_cls.fromfile(ld_path)
    return sorted(data)


def _channel_map() -> dict[str, list[str]]:
    # Include ACC Epic MoTeC uppercase names (SPEED, THROTTLE, …).
    return {
        "speed": ["SPEED", "Speed", "Ground Speed", "GPS Speed"],
        "throttle": ["THROTTLE", "Throttle", "Throttle Pos"],
        "brake": ["BRAKE", "Brake", "Brake Pos", "Brake Pedal"],
        "steer": [
            "STEERANGLE",
            "Steering",
            "Steer",
            "Steed",
            "Steering Wheel Angle",
        ],
        "gear": ["GEAR", "Gear"],
        "rpm": ["RPMS", "RPM", "Engine RPM"],
        "lap": ["LAP_BEACON", "Lap", "Lap Number"],
        "lap_dist": ["Lap Distance", "Distance", "Lap Dist", "LAP_DIST"],
        "time": ["TIME", "Time"],
        "g_lat": ["G_LAT", "G Lat"],
        "g_lon": ["G_LON", "G Lon"],
        "tc": ["TC"],
        "abs": ["ABS"],
        "pos_x": ["GPS Latitude", "Latitude", "GPS Lat"],
        "pos_z": ["GPS Longitude", "Longitude", "GPS Lon"],
        "spline": ["Lap Distance", "Distance", "LAP_DIST"],
    }


def _channel_names(data) -> list[str]:
    return [str(x) for x in data]


def _pick_series(data, names: Sequence[str]):
    available = {n.lower(): n for n in _channel_names(data)}
    for name in names:
        key = name.lower()
        if key not in available:
            continue
        real = available[key]
        try:
            ch = data[real]
            freq = float(getattr(ch, "freq", 0) or 0)
            return [float(v) for v in list(ch.data)], real, freq
        except Exception:
            continue
    return None, "", 0.0


def _steer_to_deg(values: list[float], name: str) -> list[float]:
    if re.search(r"deg", name, re.I):
        return [float(v) for v in values]
    sample = values[: min(200, len(values))] or [0.0]
    peak = max(abs(v) for v in sample)
    # ACC MoTeC STEERANGLE is often ±1 normalized.
    if peak <= 1.5:
        return [float(v) * 100.0 for v in values]
    return [float(v) for v in values]


def _pedal_unit(values: list[float]) -> list[float]:
    """Normalize 0–100 pedals to 0–1 when needed."""
    if not values:
        return values
    peak = max(abs(v) for v in values[: min(200, len(values))])
    if peak > 1.5:
        return [max(0.0, min(1.0, float(v) / 100.0)) for v in values]
    return [max(0.0, min(1.0, float(v))) for v in values]


def _infer_track_car(data) -> tuple[str, str]:
    head = data.head
    venue = str(getattr(head, "venue", "") or "").strip().lower().replace(" ", "_")
    vehicle = str(getattr(head, "vehicleid", "") or "").strip().lower().replace(" ", "_")
    if not venue:
        venue = "unknown"
    if not vehicle:
        vehicle = "unknown"
    return venue, vehicle


def _build_samples(
    data,
    track_length_m: float | None,
) -> tuple[list[dict[str, Any]], list[tuple[int, int]]]:
    cmap = _channel_map()
    speed, _, speed_freq = _pick_series(data, cmap["speed"])
    if speed is None:
        raise ValueError("No Speed channel found in %s" % ", ".join(_channel_names(data)))

    series: dict[str, list[float] | list[int]] = {"speed": speed}
    hz = speed_freq if speed_freq > 1.0 else 60.0

    throttle, _, _ = _pick_series(data, cmap["throttle"])
    brake, _, _ = _pick_series(data, cmap["brake"])
    steer_vals, steer_name, _ = _pick_series(data, cmap["steer"])
    gear, _, _ = _pick_series(data, cmap["gear"])
    rpm, _, _ = _pick_series(data, cmap["rpm"])
    lap_no, _, _ = _pick_series(data, cmap["lap"])
    lap_dist, _, _ = _pick_series(data, cmap["lap_dist"])
    time_s, _, _ = _pick_series(data, cmap["time"])
    g_lat, _, _ = _pick_series(data, cmap["g_lat"])
    g_lon, _, _ = _pick_series(data, cmap["g_lon"])
    tc, _, _ = _pick_series(data, cmap["tc"])
    abs_v, _, _ = _pick_series(data, cmap["abs"])
    lat, _, _ = _pick_series(data, cmap["pos_x"])
    lon, _, _ = _pick_series(data, cmap["pos_z"])

    if steer_vals is not None:
        series["steer"] = _steer_to_deg(steer_vals, steer_name)
    if throttle is not None:
        series["throttle"] = _pedal_unit(throttle)
    if brake is not None:
        series["brake"] = _pedal_unit(brake)

    for key, values in (
        ("gear", gear),
        ("rpm", rpm),
        ("lap_dist", lap_dist),
        ("time", time_s),
        ("g_lat", g_lat),
        ("g_lon", g_lon),
        ("tc", tc),
        ("abs", abs_v),
        ("lat", lat),
        ("lon", lon),
        ("lap", lap_no),
    ):
        if values is not None:
            series[key] = values

    # ACC MoTeC mixes channel rates. Keep the SPEED timeline and only keep
    # same-length channels; resample shorter ones by nearest index.
    n = len(series["speed"])

    def _resample_to_n(values: list[float] | list[int], target: int) -> list[float]:
        if len(values) == target:
            return [float(v) for v in values]
        if len(values) < 2 or target < 2:
            return [float(values[0])] * target if values else [0.0] * target
        out: list[float] = []
        last = len(values) - 1
        for i in range(target):
            src = int(round(i * last / (target - 1)))
            out.append(float(values[src]))
        return out

    for key in list(series.keys()):
        if key == "speed":
            continue
        series[key] = _resample_to_n(series[key], n)  # type: ignore[assignment]

    # ACC Epic SPEED is often m/s (peak ~70–80); convert to km/h for VRE.
    speed_peak = max(abs(float(v)) for v in series["speed"][: min(5000, n)] or [0.0])
    if speed_peak > 0.0 and speed_peak < 120.0:
        series["speed"] = [float(v) * 3.6 for v in series["speed"]]

    # Integrate distance from speed×dt when Lap Distance is missing (common in ACC .ld).
    integrated_dist: list[float] | None = None
    dt_fixed = 1.0 / hz
    if "lap_dist" not in series and n > 1:
        integrated_dist = [0.0] * n
        acc_m = 0.0
        for i in range(1, n):
            v_ms = float(series["speed"][i]) / 3.6
            acc_m += v_ms * dt_fixed
            integrated_dist[i] = acc_m

    samples: list[dict[str, Any]] = []
    for i in range(n):
        raw: dict[str, Any] = {"speed_kmh": series["speed"][i]}
        if "throttle" in series:
            raw["throttle"] = series["throttle"][i]
        if "brake" in series:
            raw["brake"] = series["brake"][i]
        if "steer" in series:
            raw["steer_deg"] = series["steer"][i]
        if "gear" in series:
            raw["gear"] = int(series["gear"][i])
        if "rpm" in series:
            raw["rpm"] = int(series["rpm"][i])
        if "g_lat" in series:
            raw["acc_g_lat"] = float(series["g_lat"][i])
        if "g_lon" in series:
            raw["acc_g_long"] = float(series["g_lon"][i])
        if "tc" in series:
            raw["tc"] = float(series["tc"][i])
        if "abs" in series:
            raw["abs"] = float(series["abs"][i])
        if "lat" in series:
            raw["pos_x"] = float(series["lat"][i])
        if "lon" in series:
            raw["pos_z"] = float(series["lon"][i])
        dist = None
        if "lap_dist" in series:
            dist = float(series["lap_dist"][i])
        elif integrated_dist is not None:
            dist = float(integrated_dist[i])
        if dist is not None:
            if track_length_m and track_length_m > 0:
                # Keep continuous distance for lap splitting; store spline within lap later.
                raw["lap_dist_m"] = dist
                raw["spline"] = (dist / track_length_m) % 1.0
            elif dist <= 1.5:
                raw["spline"] = dist
            else:
                raw["spline"] = dist / max(dist, 1.0)
        samples.append(normalize_sample(raw, source="acc_motec"))

    # Lap splits (prefer exact sources):
    # 1) TIME channel resets (ACC MoTeC stores per-lap elapsed seconds; drops each S/F)
    # 2) LAP_BEACON rising edges
    # 3) Track-length wraps on integrated distance
    # 4) Single stint chunk
    lap_splits: list[tuple[int, int, int]] = []  # (lap_num, count, lap_time_ms)

    def _finalize_lap_splines(start: int, end: int) -> None:
        if integrated_dist is None or not track_length_m or track_length_m <= 0:
            return
        base = float(integrated_dist[start])
        for j in range(start, end):
            local = float(integrated_dist[j]) - base
            samples[j]["spline"] = max(0.0, min(1.0, local / track_length_m))

    time_vals = series.get("time")
    if time_vals is not None and n > 2:
        # Resampled TIME is on the SPEED timeline; detect lap resets as large drops.
        edges = [0]
        exact_ms: list[int] = []
        for i in range(1, n):
            prev_t = float(time_vals[i - 1])
            cur_t = float(time_vals[i])
            if cur_t < prev_t - 1.0:
                edges.append(i)
                # Lap time is the TIME value at the last sample of the completed lap.
                exact_ms.append(int(round(prev_t * 1000.0)))
        edges.append(n)
        # Trailing open lap (may be incomplete) — use last TIME reading.
        if len(exact_ms) == len(edges) - 2:
            exact_ms.append(int(round(float(time_vals[n - 1]) * 1000.0)))
        for li, start in enumerate(edges[:-1], start=1):
            end = edges[li]
            count = end - start
            if count < 50:
                continue
            if li - 1 < len(exact_ms):
                lap_ms = max(0, exact_ms[li - 1])
            else:
                lap_ms = int(round(count / hz * 1000.0))
            lap_splits.append((li, count, lap_ms))
            _finalize_lap_splines(start, end)

    if not lap_splits:
        lap_beacon = series.get("lap")
        if lap_beacon is not None and max(float(v) for v in lap_beacon) > 0.5:
            edges = [0]
            prev = float(lap_beacon[0])
            for i in range(1, n):
                cur = float(lap_beacon[i])
                if cur > prev + 0.5 or (cur >= 1.0 and prev < 0.5):
                    edges.append(i)
                prev = cur
            edges.append(n)
            for li, start in enumerate(edges[:-1], start=1):
                end = edges[li]
                count = end - start
                if count <= 0:
                    continue
                lap_ms = int(round(count / hz * 1000.0))
                lap_splits.append((li, count, max(0, lap_ms)))
                _finalize_lap_splines(start, end)

    if not lap_splits and integrated_dist is not None and track_length_m and track_length_m > 500:
        edges = [0]
        for i in range(1, n):
            prev_lap = int(integrated_dist[i - 1] // track_length_m)
            cur_lap = int(integrated_dist[i] // track_length_m)
            if cur_lap > prev_lap:
                edges.append(i)
        edges.append(n)
        for li, start in enumerate(edges[:-1], start=1):
            end = edges[li]
            count = end - start
            if count < 50:
                continue
            lap_ms = int(round(count / hz * 1000.0))
            lap_splits.append((li, count, max(0, lap_ms)))
            _finalize_lap_splines(start, end)

    if not lap_splits:
        lap_ms = int(round(n / hz * 1000.0)) if n > 1 else 0
        lap_splits = [(1, n, max(0, lap_ms))]

    return samples, lap_splits


def import_ld(
    ld_path: str,
    session_dir: str | None = None,
    *,
    sessions_root: str | None = None,
    track_length_m: float | None = None,
    subsample: int = 1,
) -> str:
    ld_data_cls = _load_ld_data()
    data = ld_data_cls.fromfile(ld_path)
    track, car = _infer_track_car(data)
    if not track_length_m and track in ("spa", "spa_francorchamps"):
        track_length_m = 7004.0
    if not track_length_m and track in ("monza",):
        track_length_m = 5793.0
    built, lap_splits = _build_samples(data, track_length_m)

    offset = 0
    if session_dir is None:
        session_dir, sid = new_session_dir(sessions_root, track, car)
        write_session_start(
            session_dir,
            track=track,
            car=car,
            source="acc_motec",
            extras={"session_id": sid, "motec_ld": ld_path},
        )
    else:
        # If caller passed a sessions root (no session.jsonl yet), create child session
        if not os.path.isfile(os.path.join(session_dir, "session.jsonl")) and (
            not os.path.isdir(os.path.join(session_dir, "laps"))
        ):
            session_dir, sid = new_session_dir(session_dir, track, car)
            write_session_start(
                session_dir,
                track=track,
                car=car,
                source="acc_motec",
                extras={"session_id": sid, "motec_ld": ld_path},
            )
        else:
            write_session_start(session_dir, track=track, car=car, source="acc_motec")

    step = max(1, int(subsample))
    for lap_num, count, lap_ms in lap_splits:
        chunk = built[offset : offset + count : step]
        offset += count
        if len(chunk) < 5:
            continue
        write_lap(session_dir, lap_num, lap_ms, chunk, source="acc_motec")

    return session_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACC MoTeC .ld → VRE session")
    parser.add_argument("ld_path", help="Path to .ld file")
    parser.add_argument("--out", dest="session_dir", default=None, help="Existing or new session dir")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="List channel names and exit (requires ldparser)",
    )
    parser.add_argument(
        "--track-length-m",
        type=float,
        default=None,
        help="Track length for spline from Lap Distance",
    )
    args = parser.parse_args(argv)

    if args.discover:
        try:
            for name in discover_channels(args.ld_path):
                print(name)
        except ImportError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 0

    try:
        out = import_ld(
            args.ld_path,
            args.session_dir,
            track_length_m=args.track_length_m,
        )
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print("Import failed: %s" % exc, file=sys.stderr)
        return 1

    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())