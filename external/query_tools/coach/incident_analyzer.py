"""Detect loss-of-control incidents from archived lap samples."""

from __future__ import print_function

import json
import os


HYPOTHESIS_LABELS = {
    "throttle_under_lateral": "Power applied while still cornering",
    "kerb_unload": "Kerb or bump unloaded the tyre",
    "steer_fight": "Steering corrections exceeded grip",
    "loss_of_control": "Inputs exceeded the grip envelope",
}


def _t(thresholds, key, default):
    return float(thresholds.get(key, default))


def _sample_fields(s):
    susp = s.get("susp_ratio") or []
    return {
        "spline": round(float(s.get("spline", 0)), 4),
        "throttle": round(float(s.get("throttle", 0)), 3),
        "steer_deg": round(float(s.get("steer_deg", 0)), 1),
        "acc_g_lat": round(float(s.get("acc_g_lat", 0)), 2),
        "speed_kmh": round(float(s.get("speed_kmh", 0)), 1),
        "beta_deg": round(float(s.get("beta_deg", 0)), 1),
        "phase": s.get("phase") or "",
        "susp_min": round(min(susp), 3) if len(susp) == 4 else None,
    }



def _rank_hypotheses(peak_sample, pre_window, thresholds):
    hypotheses = []
    thr = float(peak_sample.get("throttle", 0))
    ay = abs(float(peak_sample.get("acc_g_lat", 0)))
    steer_vals = [abs(p.get("steer_deg", 0)) for p in pre_window]
    steer_delta = (max(steer_vals) - min(steer_vals)) if steer_vals else 0

    if thr > 0.5 and ay > 0.6:
        hypotheses.append(("throttle_under_lateral", 0.85))
    if any(
        p.get("susp_min") is not None
        and _t(thresholds, "PAINTED_KERB_SUSP_LO", 0.45) <= p["susp_min"] <= _t(thresholds, "PAINTED_KERB_SUSP_HI", 0.84)
        for p in pre_window
    ):
        hypotheses.append(("kerb_unload", 0.75))
    if steer_delta > 15:
        hypotheses.append(("steer_fight", 0.7))
    hypotheses.append(("loss_of_control", 0.6))

    seen = set()
    ranked = []
    for hid, conf in sorted(hypotheses, key=lambda x: -x[1]):
        if hid in seen:
            continue
        seen.add(hid)
        ranked.append({"id": hid, "label": HYPOTHESIS_LABELS.get(hid, hid), "confidence": conf})
    return ranked[:3]


def _vs_reference(peak_sample, ref_samples, radius=0.03):
    sp = peak_sample.get("spline", 0)
    ref = None
    best_d = 999
    for rs in ref_samples or []:
        d = abs(float(rs.get("spline", 0)) - sp)
        if d < best_d:
            best_d = d
            ref = rs
    if ref is None or best_d > radius:
        return {}
    return {
        "throttle_delta": round(float(peak_sample.get("throttle", 0)) - float(ref.get("throttle", 0)), 3),
        "speed_delta_kmh": round(float(peak_sample.get("speed_kmh", 0)) - float(ref.get("speed_kmh", 0)), 1),
    }


def detect_incidents_in_samples(samples, lap_num, thresholds, ref_samples=None, pre_window_size=5):
    """Return incident dicts for one lap's sample list."""
    beta_thresh = _t(thresholds, "BETA_TERMINAL_DEG", 35.0)
    beta_lo = _t(thresholds, "BETA_INTENTIONAL_MAX_DEG", 25.0)
    incidents = []
    i = 0
    n = len(samples)
    while i < n:
        beta = abs(float(samples[i].get("beta_deg", 0)))
        if beta < beta_lo:
            i += 1
            continue
        start = i
        peak_i = i
        peak_beta = beta
        while i < n and abs(float(samples[i].get("beta_deg", 0))) >= beta_lo * 0.85:
            b = abs(float(samples[i].get("beta_deg", 0)))
            if b > peak_beta:
                peak_beta = b
                peak_i = i
            i += 1
        if peak_beta < beta_thresh and peak_beta < beta_lo + 3:
            continue
        peak_s = samples[peak_i]
        pre_start = max(start, peak_i - pre_window_size)
        pre_raw = samples[pre_start:peak_i]
        pre_window = [_sample_fields(s) for s in pre_raw]
        peak_fields = _sample_fields(peak_s)
        sp = float(peak_s.get("spline", 0))
        hypotheses = _rank_hypotheses(peak_fields, pre_window, thresholds)
        conf = min(0.95, 0.5 + (peak_beta - beta_lo) / 40.0)
        incidents.append({
            "incident_id": "lap%d_s%.3f" % (lap_num, sp),
            "lap": lap_num,
            "spline": round(sp, 4),
            "spline_start": round(float(samples[start].get("spline", sp)), 4),
            "spline_end": round(float(samples[i - 1].get("spline", sp)), 4),
            "corner": peak_s.get("corner") or "",
            "phase": peak_s.get("phase") or "exit",
            "peak_beta_deg": round(peak_beta, 1),
            "pre_window": pre_window,
            "peak_sample": peak_fields,
            "vs_reference": _vs_reference(peak_fields, ref_samples),
            "hypothesis_ids": [h["id"] for h in hypotheses],
            "hypotheses": hypotheses,
            "template_key": "root_loss_of_control",
            "confidence": round(conf, 2),
        })
    return incidents


def analyze_lap_incidents(lap_data, thresholds, ref_lap_data=None):
    """Analyze one lap JSON payload."""
    lap_num = lap_data.get("lap", 0)
    samples = lap_data.get("samples", [])
    ref_samples = (ref_lap_data or {}).get("samples", [])
    return detect_incidents_in_samples(samples, lap_num, thresholds, ref_samples)


def analyze_session_incidents(lap_paths, thresholds):
    """Scan all laps; use best lap as reference for vs_reference deltas."""
    laps = []
    for path in lap_paths:
        with open(path) as fh:
            laps.append(json.load(fh))
    if not laps:
        return []
    best = min(laps, key=lambda d: d.get("lap_time_ms") or 999999999)
    ref_samples = best.get("samples", [])
    all_incidents = []
    for lap_data in laps:
        all_incidents.extend(
            detect_incidents_in_samples(
                lap_data.get("samples", []),
                lap_data.get("lap", 0),
                thresholds,
                ref_samples,
            )
        )
    all_incidents.sort(key=lambda x: (-x.get("peak_beta_deg", 0), x.get("lap", 0)))
    return all_incidents


def offline_yaw_gate_for_corner(samples, corner, thresholds):
    """Return a YawGateResult-like object if corner shows loss of control offline."""
    import sys
    import os
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    lib = os.path.join(repo, "ac_app", "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from yaw_gates import YawGateResult, GATE_LOSS_OF_CONTROL

    beta_thresh = _t(thresholds, "BETA_TERMINAL_DEG", 35.0)
    peak = 0.0
    for s in samples:
        if s.get("corner") != corner:
            continue
        peak = max(peak, abs(float(s.get("beta_deg", 0))))
    if peak < beta_thresh:
        return None
    conf = min(1.0, peak / beta_thresh)
    return YawGateResult(GATE_LOSS_OF_CONTROL, conf)
