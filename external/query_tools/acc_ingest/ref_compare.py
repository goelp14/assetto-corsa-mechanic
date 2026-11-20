"""Rough reference-lap delta summary (stdlib only)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _sample_val(sample: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    v = sample.get(key)
    if v is None:
        return default
    return float(v)


def _sector_slices(
    samples: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    s1: list[Mapping[str, Any]] = []
    s2: list[Mapping[str, Any]] = []
    s3: list[Mapping[str, Any]] = []
    for s in samples:
        sp = s.get("spline")
        if sp is None:
            s1.append(s)
            continue
        sp_f = float(sp)
        if sp_f < 0.34:
            s1.append(s)
        elif sp_f < 0.67:
            s2.append(s)
        else:
            s3.append(s)
    return s1, s2, s3


def _mean_speed(samples: Sequence[Mapping[str, Any]]) -> float:
    if not samples:
        return 0.0
    speeds = [_sample_val(s, "speed_kmh") for s in samples if "speed_kmh" in s]
    if not speeds:
        return 0.0
    return sum(speeds) / len(speeds)


def _integrated_speed(samples: Sequence[Mapping[str, Any]]) -> float:
    """Rough speed·time proxy using uniform sample spacing."""
    if len(samples) < 2:
        return _mean_speed(samples)
    total = 0.0
    for i in range(1, len(samples)):
        v0 = _sample_val(samples[i - 1], "speed_kmh")
        v1 = _sample_val(samples[i], "speed_kmh")
        total += 0.5 * (v0 + v1)
    return total


def _first_brake_spline(samples: Sequence[Mapping[str, Any]]) -> float | None:
    for s in samples:
        if _sample_val(s, "brake") > 0.12:
            sp = s.get("spline")
            if sp is not None:
                return float(sp)
    return None


def summarize_lap_delta(
    samples_a: Sequence[Mapping[str, Any]],
    samples_b: Sequence[Mapping[str, Any]],
) -> dict:
    """
    Compare two normalized lap sample sequences.
    Returns sector-ish speed integrals and simple flags (e.g. slower_entry).
    """
    a1, a2, a3 = _sector_slices(samples_a)
    b1, b2, b3 = _sector_slices(samples_b)

    sectors = {
        "sector1_speed_integral": _integrated_speed(a1) - _integrated_speed(b1),
        "sector2_speed_integral": _integrated_speed(a2) - _integrated_speed(b2),
        "sector3_speed_integral": _integrated_speed(a3) - _integrated_speed(b3),
        "mean_speed_a_kmh": _mean_speed(samples_a),
        "mean_speed_b_kmh": _mean_speed(samples_b),
    }

    flags: list[str] = []
    mid_a = _mean_speed(a2)
    mid_b = _mean_speed(b2)
    if mid_a + 2.0 < mid_b:
        flags.append("slower_mid")

    br_a = _first_brake_spline(samples_a)
    br_b = _first_brake_spline(samples_b)
    if br_a is not None and br_b is not None:
        if br_a > br_b + 0.02 and mid_a + 1.0 < mid_b:
            flags.append("slower_entry")

    if sectors["mean_speed_a_kmh"] + 0.5 < sectors["mean_speed_b_kmh"]:
        flags.append("slower_lap")

    return {"sectors": sectors, "flags": flags}