"""Build citation-tagged evidence packs for the coaching agent."""

from __future__ import print_function

import json
import os


def _load_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path) as fh:
        return json.load(fh)


def collect_evidence(bundle_dir):
    """Load all analysis artifacts from an exported replay bundle."""
    analysis = os.path.join(bundle_dir, "analysis")
    return {
        "stint_summary": _load_json(os.path.join(analysis, "stint_summary.json"), {}),
        "time_loss": _load_json(os.path.join(analysis, "time_loss.json"), {}),
        "corner_reports": _load_json(os.path.join(analysis, "corner_reports.json"), []),
        "pace_opportunities": _load_json(os.path.join(analysis, "pace_opportunities.json"), []),
        "setup_timeline": _load_json(os.path.join(analysis, "setup_timeline.json"), []),
        "annotations": _load_json(os.path.join(analysis, "annotations.json"), []),
        "incidents": _load_json(os.path.join(analysis, "incidents.json"), []),
        "session_plan": _load_json(os.path.join(analysis, "session_plan.json"), {}),
        "sector_bests": _load_json(os.path.join(analysis, "sector_bests.json"), {}),
        "gg_envelope": _load_json(os.path.join(analysis, "gg_envelope.json"), {}),
    }


def _cite(prefix, idx, item, source_file, extra=None):
    cid = "%s_%d" % (prefix, idx)
    out = dict(item)
    out["evidence_id"] = cid
    out["source_file"] = source_file
    if extra:
        out.update(extra)
    return out


def _load_manifest(bundle_dir):
    return _load_json(os.path.join(bundle_dir, "manifest.json"), {})


def _load_geometry(bundle_dir):
    manifest = _load_manifest(bundle_dir)
    geom_path = manifest.get("geometry", "geometry.json")
    return _load_json(os.path.join(bundle_dir, geom_path), {})


def load_lap_samples(bundle_dir, lap):
    return _load_lap_samples(bundle_dir, lap)


def _load_lap_samples(bundle_dir, lap):
    laps_dir = os.path.join(bundle_dir, "laps")
    path = os.path.join(laps_dir, "lap_%02d.json" % lap)
    data = _load_json(path, {})
    return data.get("samples", [])


def _corner_landmarks(geometry, corner_id):
    for c in geometry.get("corners", []):
        if c.get("id") == corner_id or c.get("display_name") == corner_id:
            return {
                "corner_id": c.get("id"),
                "display_name": c.get("display_name"),
                "spline_start": c.get("spline_start"),
                "spline_end": c.get("spline_end"),
            }
    return {}


def _filter_by_scope(items, corner=None, lap=None, spline=None, corner_key="corner"):
    out = list(items)
    if corner:
        out = [
            x for x in out
            if x.get(corner_key) == corner
            or x.get("corner_display") == corner
            or x.get("corner_id") == corner
        ]
    if lap is not None:
        out = [x for x in out if x.get("lap") == lap]
    if spline is not None:
        out = [
            x for x in out
            if abs(float(x.get("spline", -1)) - spline) < 0.05
            or (x.get("spline_start") is not None and x.get("spline_end") is not None
                and float(x["spline_start"]) <= spline <= float(x["spline_end"]))
        ]
    return out


def build_evidence_pack(bundle_dir, corner=None, spline=None, lap=None, question_type=None):
    """Merge bundle analysis into a scoped, citation-tagged evidence pack."""
    raw = collect_evidence(bundle_dir)
    geometry = _load_geometry(bundle_dir)
    manifest = _load_manifest(bundle_dir)

    citations = []
    idx = 0

    def add(prefix, items, source):
        nonlocal idx
        tagged = []
        for item in items:
            tagged.append(_cite(prefix, idx, item, source))
            idx += 1
        citations.extend(tagged)
        return tagged

    incidents = _filter_by_scope(raw.get("incidents") or [], corner, lap, spline)
    corners = _filter_by_scope(raw.get("corner_reports") or [], corner, lap, spline)
    annotations = _filter_by_scope(raw.get("annotations") or [], corner, lap, spline)
    opportunities = _filter_by_scope(raw.get("pace_opportunities") or [], corner, lap, spline)

    time_loss_corners = []
    tl = raw.get("time_loss") or {}
    for lap_key, lap_data in (tl.get("laps") or {}).items():
        if lap is not None and int(lap_key) != lap:
            continue
        for c in lap_data.get("corners", []):
            if corner and c.get("corner") != corner and c.get("corner_display") != corner:
                continue
            time_loss_corners.append(c)

    session_plan_items = (raw.get("session_plan") or {}).get("items") or []
    if corner:
        session_plan_items = [i for i in session_plan_items if i.get("corner") == corner]

    sample_window = []
    if lap is not None and spline is not None:
        samples = _load_lap_samples(bundle_dir, lap)
        for s in samples:
            if abs(float(s.get("spline", 0)) - spline) <= 0.02:
                sample_window.append(s)

    pack = {
        "bundle_dir": bundle_dir,
        "session_id": manifest.get("session_id"),
        "track_id": manifest.get("track_id"),
        "track_display": manifest.get("track_display"),
        "car_id": manifest.get("car_id"),
        "question_type": question_type,
        "scope": {"corner": corner, "spline": spline, "lap": lap},
        "stint_summary": raw.get("stint_summary"),
        "time_loss_corners": add("timeloss", time_loss_corners, "analysis/time_loss.json"),
        "incidents": add("incident", incidents, "analysis/incidents.json"),
        "corner_reports": add("corner", corners, "analysis/corner_reports.json"),
        "annotations": add("annotation", annotations, "analysis/annotations.json"),
        "pace_opportunities": add("opportunity", opportunities, "analysis/pace_opportunities.json"),
        "session_plan": {
            "potential_gap_s": (raw.get("session_plan") or {}).get("potential_gap_s"),
            "items": add("drill", session_plan_items, "analysis/session_plan.json"),
        },
        "sector_bests": raw.get("sector_bests"),
        "gg_envelope": raw.get("gg_envelope"),
        "track_landmarks": _corner_landmarks(geometry, corner) if corner else {},
        "sample_window": add("sample", sample_window, "laps/lap_%02d.json" % (lap or 0)),
        "citations": citations,
        "citation_ids": [c["evidence_id"] for c in citations],
    }
    return pack
