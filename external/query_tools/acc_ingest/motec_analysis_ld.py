"""Build Motec-openable vre_analysis_*.ld with VRE overlay channels.

Keeps all source Epic channels (native rates) and appends VRE_* series at 60 Hz
aligned to SPEED. Also writes analysis_meta.json + optional CSV sidecar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

try:
    from .analysis_channels import (
        coast_mask,
        damper_velocity_mm_s,
        pedal_gap_s,
        rake_proxy_mm,
        resample_nearest,
        tc_active,
        us_os,
        wheelspin_lock,
        yaw_rate_deg_s,
    )
except ImportError:  # script / pytest flat path
    from analysis_channels import (  # type: ignore
        coast_mask,
        damper_velocity_mm_s,
        pedal_gap_s,
        rake_proxy_mm,
        resample_nearest,
        tc_active,
        us_os,
        wheelspin_lock,
        yaw_rate_deg_s,
    )

_LDPARSER_HINT = (
    "Analysis .ld write needs gotzl/ldparser and numpy on PYTHONPATH. "
    "Example: export PYTHONPATH=$PYTHONPATH:/path/to/ldparser"
)


@dataclass
class ChannelSeries:
    name: str
    freq: float
    data: list[float]
    unit: str = ""
    short_name: str = ""


def _load_ld_data():
    try:
        from ldparser import ldData  # type: ignore

        return ldData
    except ImportError as exc:
        raise ImportError(_LDPARSER_HINT) from exc


def load_ld_channels(ld_path: str) -> dict[str, ChannelSeries]:
    """Load every channel at native rate (no truncation to shortest)."""
    ld_data_cls = _load_ld_data()
    data = ld_data_cls.fromfile(ld_path)
    out: dict[str, ChannelSeries] = {}
    for name in data:
        ch = data[name]
        # Force materialize before file handle assumptions matter.
        arr = list(map(float, ch.data))
        out[name] = ChannelSeries(
            name=name,
            freq=float(getattr(ch, "freq", 0) or 0),
            data=arr,
            unit=str(getattr(ch, "unit", "") or ""),
            short_name=str(getattr(ch, "short_name", "") or name[:8]),
        )
    return out


def _get(channels: dict[str, ChannelSeries], *names: str) -> ChannelSeries | None:
    lower = {k.lower(): v for k, v in channels.items()}
    for n in names:
        hit = lower.get(n.lower())
        if hit is not None:
            return hit
    return None


def _to_kmh(speed: ChannelSeries) -> list[float]:
    peak = max((abs(v) for v in speed.data[:5000]), default=0.0)
    if peak > 0.0 and peak < 120.0:
        return [v * 3.6 for v in speed.data]
    return list(speed.data)


def _pedal01(vals: Sequence[float]) -> list[float]:
    peak = max((abs(v) for v in vals[:500]), default=0.0)
    if peak > 1.5:
        return [max(0.0, min(1.0, float(v) / 100.0)) for v in vals]
    return [max(0.0, min(1.0, float(v))) for v in vals]


def time_reset_laps_ms(time_s: Sequence[float]) -> list[int]:
    """Lap times (ms) from ACC TIME channel resets (exact Motec values)."""
    if len(time_s) < 2:
        return []
    out: list[int] = []
    for i in range(1, len(time_s)):
        prev_t = float(time_s[i - 1])
        cur_t = float(time_s[i])
        if cur_t < prev_t - 1.0:
            out.append(int(round(prev_t * 1000.0)))
    # trailing open lap
    out.append(int(round(float(time_s[-1]) * 1000.0)))
    return out


def compute_derived(channels: dict[str, ChannelSeries]) -> dict[str, ChannelSeries]:
    """Compute VRE overlays aligned to SPEED timeline (60 Hz typical)."""
    speed_ch = _get(channels, "SPEED", "Speed")
    if speed_ch is None:
        raise ValueError("SPEED channel required")
    hz = speed_ch.freq if speed_ch.freq > 1 else 60.0
    n = len(speed_ch.data)
    speed_kmh = _to_kmh(speed_ch)

    thr_ch = _get(channels, "THROTTLE", "Throttle")
    brk_ch = _get(channels, "BRAKE", "Brake")
    steer_ch = _get(channels, "STEERANGLE", "Steering")
    glat_ch = _get(channels, "G_LAT")
    roty_ch = _get(channels, "ROTY")
    tc_ch = _get(channels, "TC")
    fl = _get(channels, "SUS_TRAVEL_LF")
    fr = _get(channels, "SUS_TRAVEL_RF")
    rl = _get(channels, "SUS_TRAVEL_LR")
    rr = _get(channels, "SUS_TRAVEL_RR")
    wfl = _get(channels, "WHEEL_SPEED_LF")
    wfr = _get(channels, "WHEEL_SPEED_RF")
    wrl = _get(channels, "WHEEL_SPEED_LR")
    wrr = _get(channels, "WHEEL_SPEED_RR")

    thr = _pedal01(resample_nearest(thr_ch.data, n)) if thr_ch else [0.0] * n
    brk = _pedal01(resample_nearest(brk_ch.data, n)) if brk_ch else [0.0] * n
    steer = resample_nearest(steer_ch.data, n) if steer_ch else [0.0] * n
    # STEERANGLE often ±1; scale like motec_ld
    if steer and max(abs(v) for v in steer[:200]) <= 1.5:
        steer = [v * 100.0 for v in steer]
    glat = resample_nearest(glat_ch.data, n) if glat_ch else [0.0] * n
    roty = resample_nearest(roty_ch.data, n) if roty_ch else [0.0] * n
    tc = resample_nearest(tc_ch.data, n) if tc_ch else [0.0] * n

    derived: dict[str, ChannelSeries] = {}
    derived["VRE_SPEED_KMH"] = ChannelSeries("VRE_SPEED_KMH", hz, speed_kmh, "km/h", "VSpd")
    derived["VRE_COAST"] = ChannelSeries(
        "VRE_COAST", hz, coast_mask(thr, brk, speed_kmh), "flag", "Coast"
    )
    derived["VRE_PEDAL_GAP"] = ChannelSeries(
        "VRE_PEDAL_GAP", hz, pedal_gap_s(thr, brk, hz), "s", "Gap"
    )
    derived["VRE_YAW_DEG"] = ChannelSeries(
        "VRE_YAW_DEG", hz, yaw_rate_deg_s(roty), "deg/s", "YawD"
    )
    derived["VRE_US_OS"] = ChannelSeries(
        "VRE_US_OS", hz, us_os(speed_kmh, steer, glat), "deg", "USOS"
    )
    derived["VRE_TC_ACT"] = ChannelSeries(
        "VRE_TC_ACT", hz, tc_active(tc), "flag", "TCact"
    )

    if fl and fr and rl and rr:
        rake = rake_proxy_mm(
            resample_nearest(fl.data, n),
            resample_nearest(fr.data, n),
            resample_nearest(rl.data, n),
            resample_nearest(rr.data, n),
        )
        derived["VRE_RAKE"] = ChannelSeries("VRE_RAKE", hz, rake, "mm", "Rake")
        # Damper vel at native 200 Hz, then resample for Motec overlay
        for label, ch in (
            ("VRE_DV_LF", fl),
            ("VRE_DV_RF", fr),
            ("VRE_DV_LR", rl),
            ("VRE_DV_RR", rr),
        ):
            vel = damper_velocity_mm_s(ch.data, ch.freq or 200.0)
            derived[label] = ChannelSeries(
                label, hz, resample_nearest(vel, n), "mm/s", label[-4:]
            )

    if wfl and wfr and wrl and wrr:
        spin, lock = wheelspin_lock(
            speed_kmh,
            resample_nearest(wfl.data, n),
            resample_nearest(wfr.data, n),
            resample_nearest(wrl.data, n),
            resample_nearest(wrr.data, n),
        )
        derived["VRE_SPIN"] = ChannelSeries("VRE_SPIN", hz, spin, "flag", "Spin")
        derived["VRE_LOCK"] = ChannelSeries("VRE_LOCK", hz, lock, "flag", "Lock")

    return derived


def _rebuild_with_extra(
    src_path: str,
    extra: dict[str, ChannelSeries],
) -> Any:
    """Clone source ldData, append float32 channels, rebuild pointers for write()."""
    from ldparser import ldChan, ldData  # type: ignore
    import struct

    data = ldData.fromfile(src_path)
    # Materialize all existing channel data
    for ch in data.channs:
        _ = ch.data
        ch._f = None  # detach from source file

    extras: list = []
    for ser in extra.values():
        arr = np.asarray(ser.data, dtype=np.float32)
        chan = ldChan(
            None,
            0,
            0,
            0,
            0,
            len(arr),
            np.float32,
            int(round(ser.freq)) if ser.freq else 60,
            0,
            1,
            1,
            0,
            ser.name[:32],
            (ser.short_name or ser.name)[:8],
            (ser.unit or "")[:12],
        )
        chan._data = arr
        extras.append(chan)

    all_ch = list(data.channs) + extras

    # Pointer layout matching ldData.frompd / write() expectations:
    # head at 0, event at sizeof(head), metas contiguous, then data contiguous.
    from ldparser import ldHead, ldEvent  # type: ignore

    meta_size = struct.calcsize(ldChan.fmt)
    head_size = struct.calcsize(ldHead.fmt)
    event_size = struct.calcsize(ldEvent.fmt)

    # Preserve original event block offset if possible; frompd uses head_size.
    event_ptr = head_size
    meta_ptr0 = head_size + event_size
    # If source had a larger event/venue blob, keep writing a minimal event
    # at head_size so write() stays self-consistent.
    data_ptr0 = meta_ptr0 + len(all_ch) * meta_size

    meta_ptr = meta_ptr0
    data_ptr = data_ptr0
    prev = 0
    for i, ch in enumerate(all_ch):
        next_ptr = meta_ptr + meta_size if i < len(all_ch) - 1 else 0
        ch.meta_ptr = meta_ptr
        ch.prev_meta_ptr = prev
        ch.next_meta_ptr = next_ptr
        ch.data_ptr = data_ptr
        ch.data_len = len(ch.data)
        # Ensure write-friendly scale factors
        if not hasattr(ch, "mul") or ch.mul == 0:
            ch.mul = 1
        if not hasattr(ch, "scale") or ch.scale == 0:
            ch.scale = 1
        if getattr(ch, "shift", None) is None:
            ch.shift = 0
        if getattr(ch, "dec", None) is None:
            ch.dec = 0
        # Force float32 for extras; keep dtype for originals
        if ch.dtype is None:
            ch.dtype = np.float32
        nbytes = np.dtype(ch.dtype).itemsize * ch.data_len
        prev = meta_ptr
        meta_ptr = next_ptr if next_ptr else meta_ptr + meta_size
        data_ptr += nbytes

    head = data.head
    head.meta_ptr = meta_ptr0
    head.data_ptr = data_ptr0
    head.event_ptr = event_ptr
    # Minimal event so write doesn't chase venue into old offsets
    if head.event is None:
        head.event = ldEvent("VRE", "1", "vre_analysis", 0, None)
    else:
        head.event.venue_ptr = 0
        head.event.venue = None
        if not head.event.name:
            head.event.name = "VRE"
        head.event.comment = (head.event.comment or "")[:1000] + " | vre_analysis"

    # Ensure short_comment notes VRE
    note = "VRE analysis overlays"
    if note not in (head.short_comment or ""):
        head.short_comment = ((head.short_comment or "") + " " + note).strip()[:64]

    return ldData(head, all_ch)


def write_analysis_ld(
    src_ld: str,
    out_path: str,
    *,
    best_lap_only: bool = False,
) -> dict[str, Any]:
    """Write vre_analysis .ld + meta JSON next to it. Returns meta dict."""
    channels = load_ld_channels(src_ld)
    derived = compute_derived(channels)

    time_ch = _get(channels, "TIME", "Time")
    laps_ms = time_reset_laps_ms(time_ch.data) if time_ch else []
    # Last TIME segment is the open/incomplete stint end — exclude from best.
    completed = laps_ms[:-1] if len(laps_ms) > 1 else list(laps_ms)
    # Generic GT3 window; avoids out-laps and garage soaks without guessing pace.
    racing = [t for t in completed if 90_000 <= t <= 240_000]
    best_ms = min(racing, default=min(completed, default=None) if completed else None)

    # Optional: zero derived outside best lap window (SPEED timeline)
    if best_lap_only and best_ms and time_ch:
        # Find SPEED-aligned window via TIME resampled to SPEED
        speed = _get(channels, "SPEED")
        assert speed is not None
        n = len(speed.data)
        t_rs = resample_nearest(time_ch.data, n)
        # Best completed lap: locate reset where prev TIME≈best_ms/1000
        edges = [0]
        for i in range(1, n):
            if t_rs[i] < t_rs[i - 1] - 1.0:
                edges.append(i)
        edges.append(n)
        best_start = best_end = None
        for li, start in enumerate(edges[:-1]):
            end = edges[li + 1]
            prev_t = t_rs[end - 1] if end > start else 0.0
            if int(round(prev_t * 1000.0)) == best_ms:
                best_start, best_end = start, end
                break
        if best_start is not None:
            for ser in derived.values():
                masked = [0.0] * n
                for i in range(best_start, min(best_end, n)):
                    masked[i] = ser.data[i]
                ser.data = masked

    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    rebuilt = _rebuild_with_extra(src_ld, derived)
    rebuilt.write(str(out_p))

    # Sidecar CSV (60 Hz SPEED + VRE) for tools that prefer ASCII
    speed = _get(channels, "SPEED")
    assert speed is not None
    n = len(speed.data)
    csv_path = out_p.with_suffix(".csv")
    cols = ["idx", "SPEED_ms"] + list(derived.keys())
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(",".join(cols) + "\n")
        for i in range(n):
            row = [str(i), f"{speed.data[i]:.6g}"]
            for k in derived:
                row.append(f"{derived[k].data[i]:.6g}")
            f.write(",".join(row) + "\n")

    meta = {
        "source_ld": os.path.abspath(src_ld),
        "analysis_ld": os.path.abspath(str(out_p)),
        "analysis_csv": os.path.abspath(str(csv_path)),
        "venue": getattr(rebuilt.head, "venue", ""),
        "laps_ms": laps_ms,
        "best_lap_ms": best_ms,
        "best_lap_only": best_lap_only,
        "vre_channels": sorted(derived.keys()),
        "source_channels": sorted(channels.keys()),
        "evidence": {
            "laps": "GO" if laps_ms else "NO_GO",
            "motec_overlays": "GO",
            "en_star": "PASS_THROUGH",
            "rpy_channels": "NO_GO_UNTIL_UNLOCKED",
        },
    }
    meta_path = out_p.with_name(out_p.stem + "_meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    meta["meta_json"] = os.path.abspath(str(meta_path))
    return meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ACC MoTeC → vre_analysis_*.ld")
    p.add_argument("ld_path", help="Source ACC MoTeC .ld")
    p.add_argument(
        "--out",
        default=None,
        help="Output .ld path (default: /tmp/vre_analysis_<stem>.ld)",
    )
    p.add_argument(
        "--best-lap",
        action="store_true",
        help="Zero VRE overlays outside the best completed lap window",
    )
    args = p.parse_args(argv)
    stem = Path(args.ld_path).stem
    out = args.out or f"/tmp/vre_analysis_{stem}.ld"
    try:
        meta = write_analysis_ld(args.ld_path, out, best_lap_only=args.best_lap)
    except ImportError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print("write_analysis_ld failed: %s" % exc, file=sys.stderr)
        return 1
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
