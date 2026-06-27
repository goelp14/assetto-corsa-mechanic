#!/usr/bin/env python3
"""Export a VRE session as a portable replay bundle for the web viewer."""

from __future__ import print_function

import argparse
import json
import os
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LIB = os.path.join(REPO, "ac_app", "lib")
CFG = os.path.join(REPO, "ac_app", "config")
EXPORT_TOOL_VERSION = "2"
sys.path.insert(0, LIB)

from spline_indexer import SplineIndexer
from corner_investigator import CornerInvestigator
from pace_opportunity import PaceOpportunityAnalyzer
from gg_envelope import GgEnvelope
from lap_time_analyzer import LapTimeAnalyzer
from analyze_sessions import (
    build_phase_summary,
    load_jsonl,
    load_thresholds,
    SESSIONS_ROOT,
)


def default_sessions_root():
    return os.environ.get("VRE_SESSIONS", SESSIONS_ROOT)


def list_sessions(sessions_root=None):
    root = sessions_root or default_sessions_root()
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, name)
        jsonl = os.path.join(path, "session.jsonl")
        if os.path.isdir(path) and os.path.isfile(jsonl):
            out.append((name, path))
    return out


def resolve_session_path(session_arg, sessions_root=None):
    """Accept full path, folder name, or partial match under SESSIONS_ROOT."""
    root = sessions_root or default_sessions_root()
    arg = (session_arg or "").strip()

    if not arg:
        sessions = list_sessions(root)
        if not sessions:
            raise FileNotFoundError(
                "No session specified and no sessions found under %s" % root
            )
        return sessions[0][1]

    if arg in (".", "latest", "last"):
        sessions = list_sessions(root)
        if not sessions:
            raise FileNotFoundError("No sessions under %s" % root)
        return sessions[0][1]

    expanded = os.path.abspath(os.path.expanduser(arg))
    jsonl = os.path.join(expanded, "session.jsonl")
    if os.path.isfile(jsonl):
        return expanded

    under_root = os.path.join(root, arg)
    if os.path.isfile(os.path.join(under_root, "session.jsonl")):
        return under_root

    if os.path.isdir(root):
        matches = []
        for name, path in list_sessions(root):
            if arg.lower() in name.lower():
                matches.append(path)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            hint = "\n  ".join(os.path.basename(m) for m in matches[:8])
            raise FileNotFoundError(
                "Multiple sessions match %r:\n  %s\nUse the full folder name." % (arg, hint)
            )

    raise FileNotFoundError(
        "Session not found: %r\n"
        "Use a full path, a folder name under:\n  %s\n"
        "or run: python export_replay.py --list" % (arg, root)
    )


def lookup_xy(geometry, spline):
    """Project spline 0–1 to track centerline x/z."""
    smap = geometry.get("spline_map") or geometry.get("centerline")
    if not smap:
        return None, None
    if isinstance(smap, list) and smap and isinstance(smap[0], dict):
        best = smap[0]
        best_d = 999.0
        for pt in smap:
            d = abs(pt.get("spline", 0) - spline)
            if d < best_d:
                best_d = d
                best = pt
        return best.get("x"), best.get("z")
    if isinstance(smap, list) and smap and isinstance(smap[0], (list, tuple)):
        idx = int(spline * (len(smap) - 1))
        idx = max(0, min(idx, len(smap) - 1))
        return smap[idx][0], smap[idx][1]
    return None, None


def normalize_lap_samples(samples):
    """Sort by spline, drop backward jitter, dedupe for monotonic series."""
    rows = sorted(samples, key=lambda s: s.get("spline", 0.0))
    out = []
    for s in rows:
        if not out:
            out.append(s)
            continue
        ds = s.get("spline", 0.0) - out[-1].get("spline", 0.0)
        if ds < -0.003:
            continue
        if ds < 0.00008:
            out[-1] = s
            continue
        out.append(s)
    return out


def attach_annotation_region(ann, spline_indexer):
    """Add spline_start/end so the viewer can highlight coaching regions."""
    corner = ann.get("corner", "")
    cfg = spline_indexer.corner_config(corner) if corner and spline_indexer else None
    if cfg:
        ann["spline_start"] = float(cfg.get("spline_start", 0.0))
        ann["spline_end"] = float(cfg.get("spline_end", 1.0))
    elif ann.get("spline", 0.0) > 0:
        p = float(ann["spline"])
        ann["spline_start"] = max(0.0, p - 0.012)
        ann["spline_end"] = min(1.0, p + 0.012)
    return ann


def stitched_bucket_speed_kmh(lta):
    out = []
    bl = lta.bucket_length_m
    for t in lta._best_bucket_time:
        if t is None or t <= 0:
            out.append(0.0)
        else:
            out.append(bl / t * 3.6)
    return out


def corner_losses_for_lap(samples, spline, stitched_speeds, track_length_m):
    losses = {}
    rows = normalize_lap_samples(samples)
    if not rows:
        return losses
    prev = rows[0].get("spline", 0.0)
    for s in rows:
        sp = float(s.get("spline", 0.0))
        b = spline.bin(sp)
        ref = stitched_speeds[b] if b < len(stitched_speeds) else 0.0
        lap_kmh = max(float(s.get("speed_kmh", 1.0)), 1.0)
        ds = max(0.0, (sp - prev) * track_length_m)
        if ref > 1.0 and ds > 0.0:
            dt = (1.0 / (lap_kmh / 3.6) - 1.0 / (ref / 3.6)) * ds
            if dt > 0.0001:
                corner = s.get("corner") or spline.corner_name(sp)
                if corner:
                    losses[corner] = losses.get(corner, 0.0) + dt
        prev = sp
    return losses


def build_time_loss_analysis(
    lap_paths, spline, lta, track_length_m, best_ms, all_opps, corner_reports,
):
    """Map potential lap gap to corners with coaching fixes."""
    stitched = stitched_bucket_speed_kmh(lta)
    theoretical_ms = lta.theoretical_best_ms()
    pot_gap = (best_ms - theoretical_ms) / 1000.0 if best_ms and theoretical_ms else 0.0

    fixes_by_corner = {}
    for ann in list(all_opps) + list(corner_reports):
        c = ann.get("corner", "")
        if not c:
            continue
        fixes_by_corner.setdefault(c, []).append({
            "category": ann.get("category", "opportunity"),
            "title": ann.get("title", ""),
            "action": ann.get("action", ""),
            "what": ann.get("what", ""),
            "subtype": ann.get("subtype", ""),
            "phase": ann.get("phase", ""),
        })

    laps_out = {}
    for path in lap_paths:
        with open(path) as fh:
            d = json.load(fh)
        lap_num = d.get("lap", 0)
        samples = normalize_lap_samples(d.get("samples", []))
        losses = corner_losses_for_lap(samples, spline, stitched, track_length_m)
        corners = []
        for corner_cfg in spline.corners:
            name = corner_cfg.get("name", "")
            loss = losses.get(name, 0.0)
            if loss < 0.02:
                continue
            fixes = fixes_by_corner.get(name, [])
            primary = fixes[0] if fixes else None
            corners.append({
                "corner": name,
                "corner_display": spline.corner_display_name(name),
                "spline_start": float(corner_cfg.get("spline_start", 0.0)),
                "spline_end": float(corner_cfg.get("spline_end", 1.0)),
                "loss_s": round(loss, 3),
                "fixes": fixes,
                "primary_action": primary.get("action", "") if primary else "",
                "primary_title": primary.get("title", "") if primary else "",
            })
        corners.sort(key=lambda x: x["loss_s"], reverse=True)
        lap_ms = d.get("lap_time_ms", 0)
        lap_pot = max(0.0, (lap_ms - theoretical_ms) / 1000.0) if lap_ms and theoretical_ms else 0.0
        laps_out[str(lap_num)] = {
            "lap": lap_num,
            "lap_time_ms": lap_ms,
            "potential_gap_s": round(lap_pot, 3),
            "corners": corners,
        }

    return {
        "theoretical_best_ms": theoretical_ms,
        "best_lap_ms": best_ms,
        "potential_gap_s": round(pot_gap, 3),
        "track_length_m": track_length_m,
        "num_buckets": lta.num_buckets,
        "stitched_bucket_speed_kmh": [round(v, 2) for v in stitched],
        "laps": laps_out,
    }


def build_session_plan(time_loss):
    """Top-2 corner drills for guided viewer and live pit summary."""
    pot = float(time_loss.get("potential_gap_s", 0) or 0)
    laps = time_loss.get("laps") or {}
    if not laps:
        return {"potential_gap_s": pot, "items": []}
    best_key = sorted(
        laps.keys(),
        key=lambda k: laps[k].get("lap_time_ms", 999999999),
    )[0]
    corners = laps[best_key].get("corners", [])
    items = []
    for c in corners[:2]:
        if c.get("loss_s", 0) < 0.02:
            continue
        items.append({
            "corner": c.get("corner", ""),
            "corner_display": c.get("corner_display", c.get("corner", "")),
            "loss_s": c.get("loss_s", 0),
            "drill": c.get("primary_action") or "",
            "spline_start": c.get("spline_start", 0.0),
            "spline_end": c.get("spline_end", 1.0),
        })
    return {"potential_gap_s": pot, "items": items}


def detect_export_channels(lap_paths, has_gg_envelope, has_time_loss):
    """Which telemetry channels exist in exported laps (for viewer defaults)."""
    all_samples = []
    for path in lap_paths:
        with open(path) as fh:
            all_samples.extend(json.load(fh).get("samples", []))
    n = float(len(all_samples)) if all_samples else 1.0

    def cov(pred):
        return sum(1 for s in all_samples if pred(s)) / n >= 0.08

    has_long = cov(lambda s: s.get("acc_g_long") is not None)
    return {
        "acc_g_lat": cov(lambda s: s.get("acc_g_lat") is not None and abs(s.get("acc_g_lat", 0)) > 0.001),
        "acc_g_long": has_long,
        "beta_deg": cov(lambda s: s.get("beta_deg") is not None),
        "delta_us_deg": cov(lambda s: s.get("delta_us_deg") is not None),
        "yaw_rate": cov(lambda s: s.get("yaw_rate") is not None),
        "wheel_load": cov(lambda s: isinstance(s.get("wheel_load"), list) and len(s.get("wheel_load")) == 4),
        "susp_ratio": cov(lambda s: isinstance(s.get("susp_ratio"), list) and len(s.get("susp_ratio")) == 4),
        "phase": cov(lambda s: bool(s.get("phase"))),
        "gg_envelope": bool(has_gg_envelope),
        "time_loss": bool(has_time_loss),
        "world_coords": False,
        "projected_coords": False,
    }


def enrich_lap_samples(samples, geometry):
    """Add projected pos_x/pos_z for old archives that only have spline telemetry."""
    if not geometry:
        return samples, False
    enriched = []
    added = False
    for s in samples:
        row = dict(s)
        if row.get("pos_x") is None or row.get("pos_z") is None:
            x, z = lookup_xy(geometry, row.get("spline", 0.0))
            if x is not None and z is not None:
                row["pos_x"] = x
                row["pos_z"] = z
                row["pos_projected"] = True
                added = True
        enriched.append(row)
    return enriched, added


def build_corner_reports_offline(lap_paths, spline, thresholds, sector_refs):
    """Replay CornerInvestigator on archived laps (for pre-investigation-export sessions)."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "coach"))
    from incident_analyzer import offline_yaw_gate_for_corner

    inv = CornerInvestigator(thresholds)
    reports = []
    seen = set()
    for path in lap_paths:
        with open(path) as fh:
            d = json.load(fh)
        lap_num = d.get("lap", 0)
        samples = d.get("samples", [])
        for corner_cfg in spline.corners:
            corner = corner_cfg.get("name", "")
            summary = build_phase_summary(samples, corner, thresholds)
            if not summary:
                continue
            ref = sector_refs.get(corner, {})
            landmarks = spline.corner_landmarks(corner)
            display = spline.corner_display_name(corner)
            yaw_gate = offline_yaw_gate_for_corner(samples, corner, thresholds)
            hit = inv.investigate_offline(
                summary, ref, corner=display, landmarks=landmarks, yaw_gate=yaw_gate,
            )
            if hit is None:
                continue
            key = (lap_num, corner, hit.template_key)
            if key in seen:
                continue
            seen.add(key)
            ev = dict(hit.evidence)
            ev["corner_name"] = display
            ev["spline"] = _corner_mid_spline(spline, corner)
            reports.append({
                "id": "off_%s_%s" % (lap_num, corner.replace(" ", "_")),
                "lap": lap_num,
                "spline": ev.get("spline", 0.0),
                "corner": corner,
                "corner_display": display,
                "phase": hit.phase,
                "category": "correction",
                "subtype": hit.template_key,
                "attribution": "driver",
                "title": ev.get("root_cause_label", hit.template_key),
                "what": ev.get("evidence_point", ""),
                "why": ev.get("mechanism", ""),
                "action": ev.get("fix_action", ""),
                "evidence": ev,
                "source": "corner_investigator_offline",
            })
    return reports


def track_id_from_session(records):
    for r in records:
        if r.get("record_type") == "session_start":
            track = r.get("track", "")
            return track.replace(" ", "_").lower() or "unknown"
    return "unknown"


def car_id_from_session(records):
    for r in records:
        if r.get("record_type") == "session_start":
            car = r.get("car", "")
            return car.replace(" ", "_").lower() if car else ""
    return ""


def load_track_config(track_id):
    path = os.path.join(CFG, "tracks", "%s.json" % track_id)
    if not os.path.isfile(path):
        for name in os.listdir(os.path.join(CFG, "tracks")):
            if name.endswith(".json"):
                with open(os.path.join(CFG, "tracks", name)) as fh:
                    cfg = json.load(fh)
                if cfg.get("track_id") == track_id or cfg.get("setup_folder") == track_id:
                    return cfg
        return {}
    with open(path) as fh:
        return json.load(fh)


def investigation_to_annotation(rec, spline_indexer):
    corner = rec.get("corner", "")
    ev = rec.get("evidence", {})
    return {
        "id": "inv_%s_%s" % (rec.get("lap", 0), corner.replace(" ", "_")),
        "lap": rec.get("lap"),
        "spline": ev.get("spline", _corner_mid_spline(spline_indexer, corner)),
        "corner": corner,
        "corner_display": ev.get("corner_name", corner),
        "phase": rec.get("phase", "exit"),
        "category": "correction",
        "subtype": rec.get("template_key", ""),
        "attribution": "driver",
        "title": ev.get("root_cause_label", rec.get("template_key", "")),
        "what": ev.get("evidence_point", ""),
        "why": ev.get("mechanism", ""),
        "action": ev.get("fix_action", ""),
        "evidence": ev,
        "source": "corner_investigator",
    }


def _corner_mid_spline(spline_indexer, corner):
    cfg = spline_indexer.corner_config(corner) if spline_indexer else None
    if not cfg:
        return 0.0
    return (float(cfg.get("spline_start", 0)) + float(cfg.get("spline_end", 0))) * 0.5


def _resolve_record_spline(rec, spline, investigations_by_fb=None):
    """Map archive record to a spline position for map/chart highlighting."""
    sp = rec.get("spline")
    if sp is not None and float(sp) > 0.001:
        return float(sp)
    corner = rec.get("corner") or ""
    if corner:
        return _corner_mid_spline(spline, corner)
    fb_id = rec.get("feedback_id")
    if fb_id and investigations_by_fb and fb_id in investigations_by_fb:
        inv = investigations_by_fb[fb_id]
        if inv.get("corner"):
            return _corner_mid_spline(spline, inv["corner"])
        return float(inv.get("spline") or 0.0)
    bucket = rec.get("spline_bucket")
    if bucket is not None:
        return float(bucket)
    return 0.0


def build_sector_refs(lap_paths, spline, thresholds):
    refs = {}
    for path in lap_paths:
        with open(path) as fh:
            d = json.load(fh)
        t = d.get("lap_time_ms", 0)
        for corner_cfg in spline.corners:
            corner = corner_cfg.get("name", "")
            summary = build_phase_summary(d.get("samples", []), corner, thresholds)
            if not summary:
                continue
            prev = refs.get(corner)
            if prev is None or t < prev[0]:
                refs[corner] = (t, summary)
    return {k: v[1] for k, v in refs.items()}


def build_setup_timeline(records):
    """Legacy helper — prefer build_setup_episodes + build_setup_timeline_from_episodes."""
    from setup_episodes import build_setup_episodes, build_setup_timeline as _from_episodes
    episodes = build_setup_episodes(records, lap_count=0)
    return _from_episodes(episodes)


def export_session(session_dir, output_dir, standalone=False):
    jsonl_path = os.path.join(session_dir, "session.jsonl")
    if not os.path.isfile(jsonl_path):
        raise FileNotFoundError("No session.jsonl in %s" % session_dir)

    records = load_jsonl(jsonl_path)
    track_id = track_id_from_session(records)
    car_id = car_id_from_session(records)
    track_cfg = load_track_config(track_id)
    spline = SplineIndexer(track_cfg)
    thresholds = load_thresholds()

    analysis_dir = os.path.join(output_dir, "analysis")
    laps_dir = os.path.join(output_dir, "laps")
    os.makedirs(analysis_dir, exist_ok=True)
    os.makedirs(laps_dir, exist_ok=True)

    geom_src = os.path.join(REPO, "ac_app", "data", "track_geometry", "%s.json" % track_id)
    geometry = None
    if os.path.isfile(geom_src):
        shutil.copy2(geom_src, os.path.join(output_dir, "geometry.json"))
        with open(geom_src) as fh:
            geometry = json.load(fh)
    else:
        with open(os.path.join(output_dir, "geometry.json"), "w") as fh:
            json.dump({"track_id": track_id, "degraded": True}, fh)

    lap_paths = sorted(
        glob_laps(session_dir),
        key=lambda p: int(os.path.basename(p).replace("lap_", "").replace(".json", "")),
    )
    if not lap_paths:
        raise FileNotFoundError("No lap JSON files in %s/laps/" % session_dir)

    sector_refs = build_sector_refs(lap_paths, spline, thresholds)
    with open(os.path.join(analysis_dir, "sector_bests.json"), "w") as fh:
        json.dump(sector_refs, fh, indent=2)

    best_ms = None
    lap_manifest = []
    any_world_coords = False
    any_projected = False
    for path in lap_paths:
        with open(path) as fh:
            lap_data = json.load(fh)
        lap_num = lap_data.get("lap", 0)
        samples = normalize_lap_samples(lap_data.get("samples", []))
        samples, projected = enrich_lap_samples(samples, geometry)
        if projected:
            any_projected = True
        if any(
            s.get("pos_x") is not None and s.get("pos_z") is not None and not s.get("pos_projected")
            for s in samples
        ):
            any_world_coords = True
        out_lap = os.path.join(laps_dir, "lap_%02d.json" % lap_num)
        payload = dict(lap_data)
        payload["samples"] = samples
        with open(out_lap, "w") as fh:
            json.dump(payload, fh, separators=(",", ":"))
            fh.write("\n")
        lt = lap_data.get("lap_time_ms", 0)
        lap_manifest.append({
            "lap": lap_num,
            "lap_time_ms": lt,
            "file": "laps/lap_%02d.json" % lap_num,
            "has_world_coords": any(s.get("pos_x") is not None for s in samples),
        })
        if best_ms is None or (lt > 0 and lt < best_ms):
            best_ms = lt

    investigations = [r for r in records if r.get("record_type") == "investigation"]
    corner_reports = []
    for rec in investigations:
        corner_reports.append(investigation_to_annotation(rec, spline))
    if not corner_reports:
        corner_reports = build_corner_reports_offline(
            lap_paths, spline, thresholds, sector_refs,
        )
    with open(os.path.join(analysis_dir, "corner_reports.json"), "w") as fh:
        json.dump(corner_reports, fh, indent=2)

    pace_analyzer = PaceOpportunityAnalyzer(thresholds)
    gg = GgEnvelope()
    all_opps = []
    opp_id = 0
    lta = LapTimeAnalyzer(track_length_m=track_cfg.get("length_m", 3337), spline_indexer=spline)
    for path in lap_paths:
        with open(path) as fh:
            d = json.load(fh)
        lap_num = d.get("lap", 0)
        samples = d.get("samples", [])
        for s in samples:
            gg.observe(s.get("speed_kmh", 0), s.get("acc_g_lat", 0))
            lta.observe(spline.bin(s.get("spline", 0)), s.get("speed_kmh", 0), 0.05)
        lta.finish_lap(d.get("lap_time_ms", 0), lta._lap_bucket_speed)
        pot_gap = lta.potential_gap_s(d.get("lap_time_ms", 0))
        line_cfg_map = {c.get("name"): c.get("line") for c in spline.corners}
        opps = pace_analyzer.analyze_lap(
            lap_num, samples, sector_refs, spline, pot_gap, line_cfg_map,
        )
        for opp in opps:
            opp_id += 1
            display = spline.corner_display_name(opp.evidence.get("corner", "")) if hasattr(spline, "corner_display_name") else ""
            corner = ""
            for s in samples:
                if abs(s.get("spline", 0) - opp.spline) < 0.02:
                    corner = s.get("corner", "")
                    break
            all_opps.append(pace_analyzer.export_annotation(
                opp, lap_num, corner, display or corner, opp_id,
            ))

    with open(os.path.join(analysis_dir, "pace_opportunities.json"), "w") as fh:
        json.dump(all_opps, fh, indent=2)
    with open(os.path.join(analysis_dir, "gg_envelope.json"), "w") as fh:
        json.dump(gg.to_dict(), fh, indent=2)

    setup_episodes = []
    try:
        from setup_episodes import build_setup_episodes, build_setup_timeline as episodes_to_timeline
        catalog_path = os.path.join(CFG, "car_rss_fh_x_2026.json")
        setup_episodes = build_setup_episodes(
            records, spline_indexer=spline, lap_count=len(lap_manifest),
            catalog_path=catalog_path,
        )
        setup_timeline = episodes_to_timeline(setup_episodes)
    except Exception:
        setup_timeline = build_setup_timeline(records)
    with open(os.path.join(analysis_dir, "setup_episodes.json"), "w") as fh:
        json.dump(setup_episodes, fh, indent=2)
    with open(os.path.join(analysis_dir, "setup_timeline.json"), "w") as fh:
        json.dump(setup_timeline, fh, indent=2)

    theoretical_ms = lta.theoretical_best_ms()
    stint_summary = {
        "best_lap_ms": best_ms,
        "theoretical_best_ms": theoretical_ms,
        "potential_gap_s": round((best_ms - theoretical_ms) / 1000.0, 3) if best_ms and theoretical_ms else 0,
        "lap_count": len(lap_manifest),
        "investigation_count": len(investigations),
        "opportunity_count": len(all_opps),
    }
    with open(os.path.join(analysis_dir, "stint_summary.json"), "w") as fh:
        json.dump(stint_summary, fh, indent=2)

    annotations = list(corner_reports)
    investigations_by_fb = {}
    for inv in investigations:
        fb_id = inv.get("feedback_id")
        if fb_id:
            investigations_by_fb[fb_id] = inv

    for rec in records:
        if rec.get("record_type") == "feedback":
            sp = _resolve_record_spline(rec, spline, investigations_by_fb)
            annotations.append({
                "id": rec.get("feedback_id", ""),
                "lap": rec.get("lap", 0),
                "spline": sp,
                "category": "correction",
                "subtype": rec.get("type", ""),
                "title": rec.get("headline", ""),
                "what": rec.get("headline", ""),
                "action": rec.get("action", ""),
                "source": "feedback",
            })
        if rec.get("record_type") == "corner_event" and rec.get("verdict") in (
            "SETUP_FLAW", "SETUP_STABILIZE",
        ):
            corner = rec.get("corner", "")
            sp = _resolve_record_spline(rec, spline)
            mid, start, end = sp, sp, sp
            cfg = spline.corner_config(corner) if corner else None
            if cfg:
                start = float(cfg.get("spline_start", sp))
                end = float(cfg.get("spline_end", sp))
            sym = rec.get("symptom", "setup")
            annotations.append({
                "id": "setup_det_%s_%s" % (rec.get("lap"), corner.replace(" ", "_")),
                "lap": rec.get("lap"),
                "spline": sp,
                "spline_start": start,
                "spline_end": end,
                "corner": corner,
                "corner_display": spline.corner_display_name(corner) if corner else "",
                "phase": rec.get("phase"),
                "category": "setup",
                "subtype": "setup_detection",
                "title": sym.replace("_", " "),
                "what": "%s (%s)" % (
                    spline.corner_display_name(corner) if corner else "Corner",
                    rec.get("phase", ""),
                ),
                "why": "Balance issue detected (output %.2f, input %.2f)" % (
                    rec.get("output_score", 0), rec.get("input_score", 0),
                ),
                "evidence": rec.get("evidence", {}),
                "source": "corner_event",
            })
        if rec.get("record_type") == "corner_event" and rec.get("verdict") == "DRIVER_ERROR":
            annotations.append({
                "id": "ce_%s_%s" % (rec.get("lap"), rec.get("corner", "").replace(" ", "_")),
                "lap": rec.get("lap"),
                "spline": _corner_mid_spline(spline, rec.get("corner", "")),
                "corner": rec.get("corner"),
                "phase": rec.get("phase"),
                "category": "correction",
                "subtype": rec.get("symptom", ""),
                "title": rec.get("symptom", ""),
                "evidence": rec.get("evidence", {}),
                "source": "corner_event",
            })
    for opp in all_opps:
        annotations.append(attach_annotation_region(opp, spline))
    for ep in setup_episodes:
        sp = float(ep.get("detected_spline") or 0.0)
        annotations.append({
            "id": "setup_%s" % ep.get("episode_id", ep.get("tweak_id", "")),
            "lap": ep.get("detected_lap") or ep.get("applied_lap"),
            "spline": sp,
            "spline_start": ep.get("detected_spline_start", sp),
            "spline_end": ep.get("detected_spline_end", sp),
            "corner": ep.get("detected_corner"),
            "corner_display": ep.get("detected_corner_display"),
            "phase": ep.get("detected_phase"),
            "category": "setup",
            "subtype": "setup_applied" if ep.get("applied_lap") else "setup_queued",
            "title": "%s: %s → %s" % (
                ep.get("parameter_display") or ep.get("parameter"),
                ep.get("old_value"), ep.get("new_value"),
            ),
            "what": ep.get("detection_what", ""),
            "why": ep.get("detection_why", ep.get("reason", "")),
            "action": ep.get("action", ""),
            "evidence": ep,
            "source": "setup_episode",
        })
    for ev in setup_timeline:
        if any(a.get("id", "").endswith(str(ev.get("tweak_id", ""))) for a in annotations if ev.get("tweak_id")):
            continue
        sp = float(ev.get("detected_spline") or 0.0)
        annotations.append({
            "id": "setup_%s" % ev.get("tweak_id", ""),
            "lap": ev.get("lap"),
            "spline": sp,
            "spline_start": ev.get("detected_spline_start", sp),
            "spline_end": ev.get("detected_spline_end", sp),
            "corner": ev.get("detected_corner"),
            "corner_display": ev.get("detected_corner_display"),
            "category": "setup",
            "subtype": "setup_change",
            "title": "%s: %s → %s" % (ev.get("parameter"), ev.get("old_value"), ev.get("new_value")),
            "what": ev.get("detection_what", ev.get("reason", "")),
            "why": ev.get("detection_why", ""),
            "evidence": ev,
            "source": "setup_timeline",
        })

    annotations = [attach_annotation_region(a, spline) for a in annotations]

    with open(os.path.join(analysis_dir, "annotations.json"), "w") as fh:
        json.dump(annotations, fh, indent=2)

    exported_lap_paths = sorted(
        glob_laps(output_dir),
        key=lambda p: int(os.path.basename(p).replace("lap_", "").replace(".json", "")),
    )
    time_loss = build_time_loss_analysis(
        exported_lap_paths, spline, lta, track_cfg.get("length_m", 3337),
        best_ms, all_opps, corner_reports,
    )
    with open(os.path.join(analysis_dir, "time_loss.json"), "w") as fh:
        json.dump(time_loss, fh, indent=2)

    session_plan = build_session_plan(time_loss)
    with open(os.path.join(analysis_dir, "session_plan.json"), "w") as fh:
        json.dump(session_plan, fh, indent=2)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "coach"))
    from incident_analyzer import analyze_session_incidents
    incidents = analyze_session_incidents(exported_lap_paths, thresholds)
    with open(os.path.join(analysis_dir, "incidents.json"), "w") as fh:
        json.dump(incidents, fh, indent=2)

    for path in exported_lap_paths:
        with open(path) as fh:
            lap_data = json.load(fh)
        samples = lap_data.get("samples", [])
        if len(samples) > 400:
            step = max(1, len(samples) // 400)
            dec = samples[::step]
            dec_path = path.replace(".json", "_decimated.json")
            with open(dec_path, "w") as fh:
                json.dump({"lap": lap_data.get("lap"), "decimated": True, "samples": dec}, fh)

    try:
        from narrate_stint import write_narratives
        write_narratives(output_dir, use_llm=bool(os.environ.get("OPENAI_API_KEY")))
    except Exception as exc:
        print("Note: narrative export skipped (%s)" % exc)

    channel_availability = detect_export_channels(
        exported_lap_paths, bool(gg.to_dict().get("peak_ay")), True,
    )
    channel_availability["world_coords"] = any_world_coords
    channel_availability["projected_coords"] = any_projected and not any_world_coords

    manifest = {
        "session_id": os.path.basename(session_dir),
        "track_id": track_id,
        "track_display": track_cfg.get("display_name", track_id),
        "track_length_m": track_cfg.get("length_m", 3337),
        "car_id": car_id,
        "laps": lap_manifest,
        "best_lap_ms": best_ms,
        "theoretical_best_ms": theoretical_ms,
        "geometry": "geometry.json",
        "analysis": "analysis/",
        "has_world_coords": any_world_coords,
        "has_projected_coords": any_projected and not any_world_coords,
        "channel_availability": channel_availability,
        "export_tool_version": EXPORT_TOOL_VERSION,
        "archive_note": (
            "Racing lines projected from spline + track geometry (pre-coord-capture archive)"
            if any_projected and not any_world_coords
            else (
                "Racing lines from archived carCoordinates"
                if any_world_coords
                else "Spline-only archive"
            )
        ),
    }
    coach_notes_path = os.path.join(analysis_dir, "coach_notes.json")
    if os.path.isfile(coach_notes_path):
        manifest["coach_notes"] = "analysis/coach_notes.json"
    with open(os.path.join(output_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    if standalone:
        viewer_dist = os.path.join(REPO, "replay-viewer", "dist")
        if os.path.isdir(viewer_dist):
            for name in os.listdir(viewer_dist):
                src = os.path.join(viewer_dist, name)
                dst = os.path.join(output_dir, name)
                if os.path.isdir(src):
                    if os.path.isdir(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            shutil.copy2(os.path.join(viewer_dist, "index.html"), os.path.join(output_dir, "index.html"))
        else:
            print("Warning: replay-viewer/dist not built — run npm run build in replay-viewer/", file=sys.stderr)

    return manifest


def glob_laps(session_dir):
    laps_dir = os.path.join(session_dir, "laps")
    if not os.path.isdir(laps_dir):
        return []
    out = []
    for f in os.listdir(laps_dir):
        if not f.endswith(".json"):
            continue
        if "_decimated" in f:
            continue
        out.append(os.path.join(laps_dir, f))
    return out


def session_source_mtime(session_dir):
    """Latest modification time of session source files."""
    latest = 0.0
    jsonl = os.path.join(session_dir, "session.jsonl")
    if os.path.isfile(jsonl):
        latest = max(latest, os.path.getmtime(jsonl))
    for lap in glob_laps(session_dir):
        latest = max(latest, os.path.getmtime(lap))
    return latest


def export_needs_refresh(session_dir, export_dir):
    manifest_path = os.path.join(export_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        return True
    try:
        with open(manifest_path) as fh:
            manifest = json.load(fh)
        if manifest.get("export_tool_version") != EXPORT_TOOL_VERSION:
            return True
        export_mtime = os.path.getmtime(manifest_path)
    except OSError:
        return True
    return session_source_mtime(session_dir) > export_mtime


def sync_session(session_dir, exports_root, force=False):
    """Export session if missing or stale. Returns manifest dict."""
    session_id = os.path.basename(session_dir.rstrip(os.sep))
    out_dir = os.path.join(exports_root, session_id)
    if force or export_needs_refresh(session_dir, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        return export_session(session_dir, out_dir, standalone=False)
    with open(os.path.join(out_dir, "manifest.json")) as fh:
        return json.load(fh)


def sync_all_sessions(exports_root=None, sessions_root=None, force=False, quiet=False):
    """Export every VRE session under sessions_root (incremental). Returns API index."""
    exports_root = exports_root or os.path.join(REPO, "exports")
    sessions_root = sessions_root or default_sessions_root()
    os.makedirs(exports_root, exist_ok=True)

    sessions = list_sessions(sessions_root)
    index = []
    for name, path in sessions:
        if not glob_laps(path):
            if not quiet:
                print("Skip %s (no lap files)" % name)
            continue
        if not quiet:
            print("Sync %s..." % name, end=" ", flush=True)
        try:
            manifest = sync_session(path, exports_root, force=force)
            if not quiet:
                print("ok (%.3fs best)" % (manifest.get("best_lap_ms", 0) / 1000.0))
            index.append({
                "id": name,
                "track": manifest.get("track_display", manifest.get("track_id", "")),
                "track_id": manifest.get("track_id", ""),
                "best_lap_ms": manifest.get("best_lap_ms"),
                "theoretical_best_ms": manifest.get("theoretical_best_ms"),
                "lap_count": len(manifest.get("laps", [])),
                "bundle_url": "/bundles/%s" % name,
                "archive_note": manifest.get("archive_note", ""),
                "has_world_coords": manifest.get("has_world_coords", False),
                "has_projected_coords": manifest.get("has_projected_coords", False),
            })
        except Exception as exc:
            if not quiet:
                print("FAILED: %s" % exc, file=sys.stderr)
            else:
                print("Sync failed for %s: %s" % (name, exc), file=sys.stderr)

    payload = {
        "sessions": index,
        "sessions_root": sessions_root,
        "exports_root": exports_root,
        "latest_id": index[0]["id"] if index else None,
        "count": len(index),
    }
    index_path = os.path.join(exports_root, "sessions_index.json")
    with open(index_path, "w") as fh:
        json.dump(payload, fh, indent=2)
    return payload


def main():
    parser = argparse.ArgumentParser(
        description="Export VRE session for replay viewer",
        epilog=(
            "Examples:\n"
            "  %(prog)s --list\n"
            "  %(prog)s latest -o exports/latest --standalone\n"
            "  %(prog)s 2026-06-24_004349_monaco_2020 --standalone\n"
            "  %(prog)s \"$VRE_SESSIONS/2026-06-24_004349_monaco_2020\""
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "session_dir",
        nargs="?",
        default="",
        help="Session folder, name under sessions dir, 'latest', or full path",
    )
    parser.add_argument("--output", "-o", default="", help="Output directory")
    parser.add_argument("--standalone", action="store_true", help="Bundle built viewer")
    parser.add_argument(
        "--sessions-dir",
        default="",
        help="VRE sessions root (default: VRE_SESSIONS env or AC install path)",
    )
    parser.add_argument("--list", action="store_true", help="List available sessions and exit")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Export every session under --sessions-dir into exports/",
    )
    args = parser.parse_args()

    sessions_root = args.sessions_dir or default_sessions_root()

    if args.list:
        sessions = list_sessions(sessions_root)
        if not sessions:
            print("No sessions under %s" % sessions_root, file=sys.stderr)
            return 1
        print("Sessions (%s):" % sessions_root)
        for name, path in sessions:
            print("  %s" % name)
        return 0

    if args.all:
        payload = sync_all_sessions(
            exports_root=os.path.join(REPO, "exports"),
            sessions_root=sessions_root,
            force=False,
        )
        for entry in payload["sessions"]:
            print("  %s — %s (%.3fs)" % (
                entry["id"], entry["track"],
                (entry.get("best_lap_ms") or 0) / 1000.0,
            ))
        print("Synced %d sessions to exports/" % payload["count"])
        return 0

    try:
        session_dir = resolve_session_path(args.session_dir, sessions_root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out = args.output or os.path.join(
        REPO, "exports", os.path.basename(session_dir),
    )
    os.makedirs(out, exist_ok=True)
    manifest = export_session(session_dir, out, standalone=args.standalone)
    print("Exported to %s (%d laps, best %.3fs)" % (
        out, len(manifest["laps"]),
        manifest.get("best_lap_ms", 0) / 1000.0,
    ))
    if manifest.get("has_projected_coords"):
        print("Note: old archive — racing lines projected from spline (not live carCoordinates)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
