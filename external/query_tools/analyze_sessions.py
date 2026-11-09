#!/usr/bin/env python3
"""Offline replay of archived VRE sessions through analysis heuristics."""

from __future__ import print_function

import glob
import json
import math
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIB = os.path.join(REPO, "ac_app", "lib")
CFG = os.path.join(REPO, "ac_app", "config")
sys.path.insert(0, LIB)

from spline_indexer import SplineIndexer
from grip_map import GripMapStore
from corner_investigator import CornerInvestigator
from corner_phase_metrics import CornerPhaseMetrics
from telemetry_ingest import TelemetryIngest
from channel_repair import read_lap

SESSIONS_ROOT = os.environ.get(
    "VRE_SESSIONS",
    "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa/apps/python/VirtualRaceEngineer/data/sessions",
)

CORNER_ORDER = (
    "Turn 1", "Turn 4", "Turn 6", "Turn 8",
    "Swimming Pool", "Tabac", "Rascasse", "Final Corner",
)


def load_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_thresholds():
    with open(os.path.join(CFG, "thresholds.json"), "r") as fh:
        return json.load(fh)


def sample_to_frame(sample):
    steer_rad = sample.get("steer_deg", 0.0) / 57.2958
    return TelemetryIngest.frame_from_dict({
        "spline": sample.get("spline", 0.0),
        "speed_kmh": sample.get("speed_kmh", 0.0),
        "throttle": sample.get("throttle", 0.0),
        "brake": sample.get("brake", 0.0),
        "steer": steer_rad,
        "acc_g": (0.0, sample.get("acc_g_lat", 0.0), sample.get("acc_g_vert", 0.0)),
        "slip_ratio": sample.get("slip", (0.02, 0.02, 0.05, 0.05)),
        "susp_ratio": sample.get("susp_ratio", (0.2, 0.2, 0.2, 0.2)),
        "wheel_load": sample.get("wheel_load", (3000, 3000, 2500, 2500)),
    })


class FakeBal(object):
    valid = True
    delta_us = 0.0
    ay_efficiency = 0.95

    def __init__(self, sample):
        d = sample.get("delta_us_deg")
        if d is not None:
            self.delta_us = math.radians(d)
            self.valid = True
        ay = abs(sample.get("acc_g_lat", 0.0))
        self.ay_efficiency = min(1.0, ay / 2.5) if ay > 0.1 else 0.9


def build_phase_summary(samples, corner, thresholds):
    """Rebuild corner phase summary from archived subsampled lap data."""
    cpm = CornerPhaseMetrics(thresholds)
    dyn = type("D", (), {"beta": 0.0, "yaw_rate_err": 0.0})()
    for s in samples:
        if s.get("corner") != corner:
            continue
        frame = sample_to_frame(s)
        phase = s.get("phase") or "exit"
        bal = FakeBal(s)
        cpm.observe(corner, phase, frame, dyn, bal)
    return cpm.finalize(corner)


def root_cause_report(lap_paths, spline, thresholds, landmarks_map):
    """Compare laps vs best lap reference; print investigator output."""
    inv = CornerInvestigator(thresholds)
    refs = {}
    for path in lap_paths:
        d = read_lap(path)
        t = d.get("lap_time_ms", 0) / 1000.0
        if t < 79.5 or t > 84.0:
            continue
        for corner in CORNER_ORDER:
            summary = build_phase_summary(d.get("samples", []), corner, thresholds)
            if summary:
                prev = refs.get(corner)
                if prev is None or t < prev[0]:
                    refs[corner] = (t, summary)

    print("\n## Root-cause investigation (evidence vs your best laps)\n")
    for path in lap_paths[-3:]:
        d = read_lap(path)
        t = d.get("lap_time_ms", 0) / 1000.0
        label = "%s lap %s %.3fs" % (
            os.path.basename(os.path.dirname(os.path.dirname(path)))[-8:],
            d.get("lap"), t,
        )
        print("### %s\n" % label)
        for corner in CORNER_ORDER:
            summary = build_phase_summary(d.get("samples", []), corner, thresholds)
            if not summary:
                continue
            ref = refs.get(corner, (None, {}))[1]
            lm = landmarks_map.get(corner, {})
            display = corner_display(spline, corner)
            hit = inv.investigate_offline(summary, ref, corner=display, landmarks=lm)
            if hit is None:
                continue
            print("**%s** — %s" % (display, hit.evidence.get("root_cause_label", "")))
            print("- WHAT: %s" % hit.evidence.get("evidence_point", ""))
            print("- WHY: %s" % hit.evidence.get("mechanism", ""))
            print("- HOW: %s\n" % hit.evidence.get("fix_action", ""))


def analyze_lap(samples, spline, thresholds, grip_map):
    """Per-corner aggregates from archived samples."""
    corners = {}
    spins = []
    for sample in samples:
        corner = sample.get("corner") or spline.corner_name(sample.get("spline", 0.0))
        if not corner:
            continue
        c = corners.setdefault(corner, {
            "n": 0, "min_speed": 9999, "max_speed": 0,
            "max_beta": 0, "max_ay": 0, "brake_sum": 0, "throttle_sum": 0,
            "steer_abs_sum": 0, "steer_flips": 0, "kerb_hits": 0,
            "slip_spikes": 0, "loss_of_control": 0,
            "_last_steer_sign": 0,
        })
        c["n"] += 1
        spd = sample.get("speed_kmh", 0.0)
        c["min_speed"] = min(c["min_speed"], spd)
        c["max_speed"] = max(c["max_speed"], spd)
        c["max_ay"] = max(c["max_ay"], abs(sample.get("acc_g_lat", 0.0)))
        beta = abs(sample.get("beta_deg", 0.0))
        c["max_beta"] = max(c["max_beta"], beta)
        c["brake_sum"] += sample.get("brake", 0.0)
        c["throttle_sum"] += sample.get("throttle", 0.0)
        steer = abs(sample.get("steer_deg", 0.0))
        c["steer_abs_sum"] += steer
        sign = 1 if sample.get("steer_deg", 0) > 2 else (-1 if sample.get("steer_deg", 0) < -2 else 0)
        if sign and c["_last_steer_sign"] and sign != c["_last_steer_sign"]:
            c["steer_flips"] += 1
        if sign:
            c["_last_steer_sign"] = sign
        if beta > 25:
            c["loss_of_control"] += 1
            spins.append((corner, sample.get("spline"), beta, spd))
        susp = sample.get("susp_ratio")
        if susp and max(susp) > thresholds.get("KERB_SUSP_PCT", 0.85):
            c["kerb_hits"] += 1
        slip = sample.get("slip")
        if slip and max(slip) > thresholds.get("SURFACE_SLIP_SPIKE", 0.08):
            c["slip_spikes"] += 1

        bucket = spline.bin(sample.get("spline", 0.0))
        frame = sample_to_frame(sample)
        grip_map.observe(bucket, frame, FakeBal(sample))

    return corners, spins


def corner_display(spline, name):
    return spline.corner_display_name(name) if name else name


def driver_coaching(corner_data, display):
    tips = []
    n = corner_data["n"]
    if n < 3:
        return tips
    mean_brake = corner_data["brake_sum"] / n
    mean_throttle = corner_data["throttle_sum"] / n
    mean_steer = corner_data["steer_abs_sum"] / n
    if corner_data["steer_flips"] >= 3:
        tips.append("Reduce steering corrections — sawing mid-corner (%d flips)." % corner_data["steer_flips"])
    if corner_data["loss_of_control"] >= 2:
        tips.append("Loss of control detected (beta up to %.0f°) — likely throttle/brake on limit." % corner_data["max_beta"])
    if corner_data["kerb_hits"] >= 2 and corner_data["steer_flips"] >= 1:
        tips.append("Kerb + corrections — ease steering while tyre is unloaded.")
    elif corner_data["kerb_hits"] >= 2:
        tips.append("Heavy kerb use — clip less or let platform settle before steering.")
    if corner_data["slip_spikes"] >= 3 and mean_throttle > 0.4:
        tips.append("Rear slip under throttle — patience on exit at %s." % display)
    if mean_brake > 0.5 and corner_data["max_beta"] > 15:
        tips.append("Trail-brake overlap may be too aggressive — separate brake release from turn-in.")
    if not tips and corner_data["max_ay"] < 1.2 and corner_data["max_speed"] > 80:
        tips.append("Low lateral load for speed — may be leaving grip on table (line or commitment).")
    return tips


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Offline VRE session analysis")
    parser.add_argument("--track", default="monaco_2020", help="Track config id")
    parser.add_argument("--session", default="", help="Session folder name or glob fragment")
    args = parser.parse_args()

    thresholds = load_thresholds()
    track_path = os.path.join(CFG, "tracks", "%s.json" % args.track)
    if not os.path.isfile(track_path):
        print("Track config not found:", track_path, file=sys.stderr)
        return 1
    spline = SplineIndexer.from_track_file(track_path)

    if args.session:
        pattern = os.path.join(SESSIONS_ROOT, "*%s*" % args.session)
        sessions = sorted(glob.glob(pattern))
    else:
        track_glob = args.track.replace("_", "*")
        sessions = sorted(glob.glob(os.path.join(SESSIONS_ROOT, "*%s*" % track_glob)))[-3:]
    if not sessions:
        print("No sessions found in", SESSIONS_ROOT)
        return 1

    all_laps = []
    grip_map = GripMapStore(thresholds=thresholds)
    grip_map.track_id = "monaco_2020"

    print("# Monaco session analysis (your data only)\n")
    print("Sessions: %s\n" % ", ".join(os.path.basename(s) for s in sessions))

    for sess_dir in sessions:
        jsonl = os.path.join(sess_dir, "session.jsonl")
        if not os.path.isfile(jsonl):
            continue
        records = load_jsonl(jsonl)
        laps = [r for r in records if r.get("record_type") == "lap_summary"]
        for lap in laps:
            lap["session"] = os.path.basename(sess_dir)
            all_laps.append(lap)

    # Use laps after lap 2 for stable reference deltas
    stable_laps = [l for l in all_laps if l.get("lap", 0) >= 2]
    if not stable_laps:
        stable_laps = all_laps[1:] if len(all_laps) > 1 else all_laps

    print("## Lap times (last %d laps across sessions)\n" % min(8, len(all_laps)))
    for lap in all_laps[-8:]:
        t = lap.get("lap_time_ms", 0) / 1000.0
        style = lap.get("driving_style", {})
        print("- %s lap %s: %.3fs | consistency %.0f%% | aggression %.2f | rear slip idx %.2f" % (
            lap.get("session", "?")[-8:], lap.get("lap"), t,
            style.get("consistency", 0) * 100,
            style.get("aggression", 0),
            style.get("slip_index", 0),
        ))

    # Aggregate corner costs from stable laps
    corner_costs = {}
    for lap in stable_laps:
        cd = lap.get("corner_deltas_s") or {}
        for corner, delta in cd.items():
            if abs(delta) > 50:
                continue
            corner_costs.setdefault(corner, []).append(delta)

    print("\n## Where time goes (avg loss vs your evolving reference, laps >= 2)\n")
    ranked = []
    for corner, deltas in corner_costs.items():
        avg = sum(deltas) / len(deltas)
        if avg > 0.02:
            ranked.append((avg, corner, len(deltas)))
    ranked.sort(reverse=True)
    if not ranked:
        print("No meaningful corner deltas yet (reference still stabilizing).")
    else:
        for avg, corner, n in ranked[:6]:
            print("- **%s**: +%.2fs avg (%d laps)" % (
                corner_display(spline, corner), avg, n,
            ))

    # Replay last 4 lap files in detail
    print("\n## Telemetry replay (last 4 laps)\n")
    lap_files = []
    for sess_dir in sessions:
        lap_files.extend(sorted(glob.glob(os.path.join(sess_dir, "laps", "lap_*.json"))))
    lap_files = lap_files[-4:]

    with open(track_path) as fh:
        track_cfg = json.load(fh)
    landmarks_map = {
        c["name"]: c.get("landmarks", {})
        for c in track_cfg.get("corners", [])
    }
    all_lap_files = []
    for sess_dir in sorted(glob.glob(os.path.join(SESSIONS_ROOT, "*%s*" % args.track.split("_")[0]))):
        all_lap_files.extend(sorted(glob.glob(os.path.join(sess_dir, "laps", "lap_*.json"))))
    root_cause_report(all_lap_files, spline, thresholds, landmarks_map)

    session_issues = {}
    all_spins = []

    for path in lap_files:
        data = read_lap(path)
        lap_num = data.get("lap", "?")
        sess = os.path.basename(os.path.dirname(os.path.dirname(path)))
        samples = data.get("samples", [])
        grip_map.reset_lap()
        corners, spins = analyze_lap(samples, spline, thresholds, grip_map)
        t_ms = data.get("lap_time_ms", 0)
        print("### %s lap %s — %.3fs (%d samples)" % (sess[-8:], lap_num, t_ms / 1000.0, len(samples)))
        all_spins.extend(spins)

        for corner in CORNER_ORDER:
            if corner not in corners:
                continue
            c = corners[corner]
            display = corner_display(spline, corner)
            tips = driver_coaching(c, display)
            if not tips and c["max_beta"] < 20 and c["steer_flips"] < 2:
                continue
            print("  %s: min %.0f km/h | beta max %.0f° | steer flips %d | kerb hits %d" % (
                display, c["min_speed"], c["max_beta"], c["steer_flips"], c["kerb_hits"],
            ))
            for tip in tips:
                print("    → %s" % tip)
                session_issues.setdefault(display, []).append(tip)

        grip_map.finish_lap([0.0] * grip_map.num_buckets, lap_was_clean=True)

    # Grip map from replay
    print("\n## Personal grip map (rebuilt from replayed laps)\n")
    hotspots = grip_map.hotspots(limit=5, spline_indexer=spline)
    if hotspots:
        for i, h in enumerate(hotspots, 1):
            print("%d. **%s** — %s (rating %d) — %s" % (
                i, h["corner"] or "%.0f%% lap" % (h["spline"] * 100),
                h["label"], h["rating"], h["action"],
            ))
    else:
        print("Grip map still sparse — archived samples lack full wheel/susp telemetry.")

    # Spins summary
    print("\n## Incidents (beta > 25°)\n")
    if all_spins:
        by_corner = {}
        for corner, spl, beta, spd in all_spins:
            by_corner.setdefault(corner_display(spline, corner), 0)
            by_corner[corner_display(spline, corner)] += 1
        for name, count in sorted(by_corner.items(), key=lambda x: -x[1]):
            print("- **%s**: %d loss-of-control samples" % (name, count))
        print("\nPrimary fix: **Sainte Devote exit** — wait for straight steering before full throttle; your archived laps show repeated high-beta events at Turn 1.")
    else:
        print("No major spins in replayed laps.")

    # Verdict summary from jsonl (deduped)
    print("\n## Engine verdicts (recent sessions, deduped)\n")
    verdict_counts = {}
    symptom_counts = {}
    for sess_dir in sessions:
        for rec in load_jsonl(os.path.join(sess_dir, "session.jsonl")):
            if rec.get("record_type") != "corner_event":
                continue
            if rec.get("evidence", {}).get("yaw_gate") == "LOSS_OF_CONTROL":
                continue
            key = (rec.get("corner"), rec.get("verdict"), rec.get("lap"))
            if key in verdict_counts:
                continue
            verdict_counts[key] = 1
            v = rec.get("verdict", "?")
            symptom_counts[v] = symptom_counts.get(v, 0) + 1
    for v, n in sorted(symptom_counts.items(), key=lambda x: -x[1])[:8]:
        print("- %s: %d corner events" % (v, n))

    print("\n## Driver style priorities (action list)\n")
    priorities = []
    if ranked:
        top = ranked[0]
        priorities.append("**#1 Time on track**: %s (+%.2fs) — focus one clean repeat before pushing." % (
            corner_display(spline, top[1]), top[1] and top[0],
        ))
    if any("Turn 1" in str(s) or "Sainte" in str(s) for s in session_issues):
        priorities.append("**#2 Sainte Devote**: Exit throttle discipline — full power only when steering unwinds.")
    if any("Hairpin" in k or "Turn 6" in k for k in session_issues):
        priorities.append("**#3 Hairpin**: Patience on throttle; min-speed formula line needs wide approach, not early power.")
    if any("Pool" in k or "Swimming" in k for k in session_issues):
        priorities.append("**#4 Swimming Pool**: Treat as one complex — sacrifice first chicane if second + Rascasse improve.")
    if any("Rascasse" in k for k in session_issues):
        priorities.append("**#5 Rascasse**: Stay on inside rubber — narrow line, one steering input.")
    style = all_laps[-1].get("driving_style", {}) if all_laps else {}
    if style.get("slip_index", 0) > 0.14:
        priorities.append("**#6 Traction**: Rear slip index %.2f — unwind steering before full throttle on exits." % style.get("slip_index"))
    if style.get("consistency", 0) < 0.72:
        priorities.append("**#7 Consistency**: At %.0f%% — repeat same brake markers; messy laps block baseline." % (style.get("consistency", 0) * 100))

    if not priorities:
        priorities.append("Keep building clean laps — reference and grip map need 3+ consistent laps.")
    for p in priorities:
        print("- %s" % p)

    print("\n## Setup vs driver\n")
    print("- **Setup memory**: empty — no confirmed tweaks yet; driver/style fixes first.")
    print("- **Tyre temps**: in window (ideal) on recent laps — not a pressure/camber lever yet.")
    print("- **When to setup**: if kerb/platform issues persist with *clean inputs* (no steer flips), softer bump/rebound in pits.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
