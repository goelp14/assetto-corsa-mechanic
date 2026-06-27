# external/query_tools/setup_episodes.py
"""Build replay-viewer setup episodes from archived session records."""

from __future__ import print_function

import json
import os


def _corner_region(spline_indexer, corner):
    cfg = spline_indexer.corner_config(corner) if spline_indexer and corner else None
    if not cfg:
        return 0.0, 0.0, 0.0
    start = float(cfg.get("spline_start", 0.0))
    end = float(cfg.get("spline_end", 0.0))
    return (start + end) * 0.5, start, end


def _display_corner(spline_indexer, corner, fallback=""):
    if spline_indexer and corner and hasattr(spline_indexer, "corner_display_name"):
        return spline_indexer.corner_display_name(corner)
    return fallback or corner or ""


def _avg_laps(lap_times, lap, before=True, count=3):
    if before:
        vals = [t for l, t in lap_times if l < lap][-count:]
    else:
        vals = [t for l, t in lap_times if l >= lap][:count]
    if not vals:
        return None
    return int(sum(vals) / len(vals))


def _match_queued(records, section, applied_lap):
    best = None
    for rec in records:
        if rec.get("record_type") != "setup_queued":
            continue
        if rec.get("section") != section:
            continue
        qlap = rec.get("lap", 0)
        if qlap <= applied_lap and (best is None or qlap > best.get("lap", -1)):
            best = rec
    return best


def _lever_display(section, catalog_path=None):
    if not catalog_path or not section:
        return section
    try:
        with open(catalog_path) as fh:
            cfg = json.load(fh)
        for lever in cfg.get("levers", []):
            if lever.get("section") == section:
                return lever.get("name", section)
    except (IOError, ValueError):
        pass
    return section


def build_setup_episodes(records, spline_indexer=None, lap_count=0, catalog_path=None):
    """Merge queued, applied, evaluated setup records into viewer episodes."""
    lap_times = []
    pit_entries = {}
    evaluations = {}
    reverts = {}
    queued_all = []
    episodes = []

    for rec in records:
        rt = rec.get("record_type")
        if rt == "lap_summary":
            lap_times.append((rec.get("lap"), rec.get("lap_time_ms")))
        elif rt == "pit_transition" and rec.get("kind") == "entry":
            pit_entries[rec.get("lap")] = rec.get("spline", 0.0)
        elif rt == "setup_queued":
            queued_all.append(rec)
        elif rt == "setup_evaluation":
            evaluations[rec.get("tweak_id", "")] = rec
        elif rt == "setup_reverted":
            reverts[rec.get("tweak_id", "")] = rec
            reverts[rec.get("parameter", "")] = rec

    for rec in records:
        if rec.get("record_type") != "setup_change":
            continue
        parameter = rec.get("parameter", "")
        applied_lap = rec.get("lap", 0)
        tweak_id = rec.get("tweak_id", "")
        queued = _match_queued(queued_all, parameter, applied_lap)

        corner = rec.get("corner") or (queued.get("corner") if queued else "")
        phase = rec.get("phase") or (queued.get("phase") if queued else "")
        detected_lap = (
            rec.get("queued_lap")
            if rec.get("queued_lap") is not None
            else (queued.get("lap") if queued else applied_lap)
        )
        detected_spline = rec.get("spline")
        if detected_spline is None and queued:
            detected_spline = queued.get("spline")
        mid, start, end = _corner_region(spline_indexer, corner)
        if detected_spline is None:
            detected_spline = mid

        eval_rec = evaluations.get(tweak_id)
        status = eval_rec.get("status", "pending") if eval_rec else "pending"
        eval_lap = eval_rec.get("lap") if eval_rec else None
        active_to = eval_lap if status == "reverted" and eval_lap else lap_count

        detection_what = rec.get("detection_what") or (queued.get("detection_what") if queued else "")
        detection_why = rec.get("detection_why") or rec.get("reason") or (
            queued.get("detection_why") if queued else ""
        )
        if not detection_what:
            sym = (rec.get("symptom") or "setup").replace("_", " ")
            detection_what = "%s — %s" % (
                _display_corner(spline_indexer, corner, parameter), sym,
            )
        if not detection_why and rec.get("symptom"):
            detection_why = "Symptom: %s" % rec.get("symptom", "").replace("_", " ")

        before_ms = _avg_laps(lap_times, applied_lap, before=True)
        after_ms = _avg_laps(lap_times, applied_lap, before=False)

        episode = {
            "episode_id": tweak_id or "setup_%s_L%d" % (parameter, applied_lap),
            "tweak_id": tweak_id,
            "parameter": parameter,
            "parameter_display": _lever_display(parameter, catalog_path),
            "old_value": rec.get("old_value"),
            "new_value": rec.get("new_value"),
            "delta": rec.get("delta"),
            "symptom": rec.get("symptom", ""),
            "reason": rec.get("reason", ""),
            "source": rec.get("source", "eval"),
            "status": status,
            "detected_lap": detected_lap,
            "detected_corner": corner,
            "detected_corner_display": rec.get("corner_display") or _display_corner(
                spline_indexer, corner,
            ),
            "detected_phase": phase,
            "detected_spline": float(detected_spline or 0.0),
            "detected_spline_start": start,
            "detected_spline_end": end,
            "detection_what": detection_what,
            "detection_why": detection_why,
            "verdict": rec.get("verdict", ""),
            "input_score": rec.get("input_score"),
            "output_score": rec.get("output_score"),
            "corner_delta_s": rec.get("corner_delta_s"),
            "queued_lap": detected_lap,
            "applied_lap": applied_lap,
            "applied_at_pit": bool(rec.get("pit_entry") or applied_lap in pit_entries),
            "applied_spline": pit_entries.get(applied_lap, 0.0),
            "active_from_lap": applied_lap,
            "active_to_lap": active_to,
            "evaluation_lap": eval_lap,
            "effectiveness": eval_rec.get("effectiveness") if eval_rec else None,
            "lap_time_delta_ms": eval_rec.get("lap_time_delta_ms") if eval_rec else None,
            "avg_lap_before_ms": before_ms,
            "avg_lap_after_ms": after_ms,
            "action": "Load Auto_Tweak.ini in the setup screen after pit stop.",
        }
        episodes.append(episode)

    for rec in queued_all:
        section = rec.get("section", "")
        if any(ep.get("parameter") == section and ep.get("queued_lap") == rec.get("lap") for ep in episodes):
            continue
        corner = rec.get("corner", "")
        mid, start, end = _corner_region(spline_indexer, corner)
        detected_spline = rec.get("spline", mid)
        episodes.append({
            "episode_id": "queued_%s_L%d" % (section, rec.get("lap", 0)),
            "tweak_id": "",
            "parameter": section,
            "parameter_display": _lever_display(section, catalog_path),
            "old_value": rec.get("old_value"),
            "new_value": rec.get("new_value"),
            "delta": rec.get("delta"),
            "symptom": rec.get("symptom", ""),
            "reason": rec.get("reason", ""),
            "source": rec.get("source", "eval"),
            "status": "queued_only",
            "detected_lap": rec.get("lap"),
            "detected_corner": corner,
            "detected_corner_display": rec.get("corner_display") or _display_corner(
                spline_indexer, corner,
            ),
            "detected_phase": rec.get("phase", ""),
            "detected_spline": float(detected_spline or 0.0),
            "detected_spline_start": start,
            "detected_spline_end": end,
            "detection_what": rec.get("detection_what", ""),
            "detection_why": rec.get("detection_why", rec.get("reason", "")),
            "verdict": rec.get("verdict", ""),
            "input_score": rec.get("input_score"),
            "output_score": rec.get("output_score"),
            "corner_delta_s": rec.get("corner_delta_s"),
            "queued_lap": rec.get("lap"),
            "applied_lap": None,
            "applied_at_pit": False,
            "active_from_lap": None,
            "active_to_lap": None,
            "action": "Queued for next pit stop — not yet applied in this session.",
        })

    episodes.sort(key=lambda ep: (
        ep.get("detected_lap") or 0,
        ep.get("applied_lap") or 999,
        ep.get("parameter") or "",
    ))
    return episodes


def build_setup_timeline(episodes):
    """Backward-compatible slim timeline derived from episodes."""
    out = []
    for ep in episodes:
        if ep.get("status") == "queued_only" and not ep.get("applied_lap"):
            continue
        out.append({
            "lap": ep.get("applied_lap") or ep.get("detected_lap"),
            "tweak_id": ep.get("tweak_id"),
            "parameter": ep.get("parameter"),
            "parameter_display": ep.get("parameter_display"),
            "old_value": ep.get("old_value"),
            "new_value": ep.get("new_value"),
            "symptom": ep.get("symptom"),
            "reason": ep.get("reason"),
            "detection_what": ep.get("detection_what"),
            "detection_why": ep.get("detection_why"),
            "detected_corner": ep.get("detected_corner"),
            "detected_corner_display": ep.get("detected_corner_display"),
            "detected_phase": ep.get("detected_phase"),
            "detected_spline": ep.get("detected_spline"),
            "detected_spline_start": ep.get("detected_spline_start"),
            "detected_spline_end": ep.get("detected_spline_end"),
            "active_from_lap": ep.get("active_from_lap"),
            "active_to_lap": ep.get("active_to_lap"),
            "status": ep.get("status"),
            "effectiveness": ep.get("effectiveness"),
            "avg_lap_before_ms": ep.get("avg_lap_before_ms"),
            "avg_lap_after_ms": ep.get("avg_lap_after_ms"),
        })
    return out
