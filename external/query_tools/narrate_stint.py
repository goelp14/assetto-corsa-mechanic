#!/usr/bin/env python3
"""Stint narrative from structured coaching evidence (deterministic + optional LLM)."""

from __future__ import print_function

import argparse
import json
import os
import sys

try:
    from urllib import request as urllib_request
    from urllib import error as urllib_error
except ImportError:
    import urllib2 as urllib_request  # type: ignore
    import urllib2 as urllib_error  # type: ignore


def _load_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path) as fh:
        return json.load(fh)


def collect_evidence(bundle_dir):
    """Load analysis artifacts — delegates to coach.evidence_pack when available."""
    try:
        coach_dir = os.path.join(os.path.dirname(__file__), "coach")
        if coach_dir not in sys.path:
            sys.path.insert(0, coach_dir)
        from evidence_pack import collect_evidence as _collect
        return _collect(bundle_dir)
    except ImportError:
        pass
    analysis = os.path.join(bundle_dir, "analysis")
    return {
        "stint_summary": _load_json(os.path.join(analysis, "stint_summary.json"), {}),
        "time_loss": _load_json(os.path.join(analysis, "time_loss.json"), {}),
        "corner_reports": _load_json(os.path.join(analysis, "corner_reports.json"), []),
        "pace_opportunities": _load_json(os.path.join(analysis, "pace_opportunities.json"), []),
        "setup_timeline": _load_json(os.path.join(analysis, "setup_timeline.json"), []),
        "annotations": _load_json(os.path.join(analysis, "annotations.json"), []),
    }


def _fmt_corner_block(ann):
    lines = []
    title = ann.get("title") or ann.get("subtype") or "Coaching note"
    where = ann.get("corner_display") or ann.get("corner") or ""
    if where:
        lines.append("### %s — %s" % (where, title))
    else:
        lines.append("### %s" % title)
    if ann.get("phase"):
        lines.append("*Phase: %s*" % ann.get("phase"))
    if ann.get("what"):
        lines.append("**What happened:** %s" % ann.get("what"))
    if ann.get("why"):
        lines.append("**Why it matters:** %s" % ann.get("why"))
    if ann.get("action"):
        lines.append("**What to do:** %s" % ann.get("action"))
    ev = ann.get("evidence") or {}
    if ev:
        compact = {k: ev[k] for k in sorted(ev.keys()) if ev[k] not in ("", None, [], {})}
        if compact:
            lines.append("**Evidence:** `%s`" % json.dumps(compact, separators=(",", ":")))
    lines.append("")
    return "\n".join(lines)


def build_deterministic_narrative(bundle_dir):
    ev = collect_evidence(bundle_dir)
    stint = ev["stint_summary"] or {}
    lines = ["# Stint technical debrief\n"]

    best = stint.get("best_lap_ms")
    pot = stint.get("theoretical_best_ms")
    if best and pot:
        lines.append(
            "Best lap **%.3fs**. Stitched sector potential **%.3fs** "
            "(**%.3fs** still on the table in your own data).\n\n" % (
                best / 1000.0, pot / 1000.0, stint.get("potential_gap_s", 0),
            )
        )

    time_loss = ev.get("time_loss") or {}
    best_lap_key = None
    if time_loss.get("laps"):
        best_lap_key = sorted(
            time_loss["laps"].keys(),
            key=lambda k: time_loss["laps"][k].get("lap_time_ms", 999999999),
        )[0]
    loss_corners = []
    if best_lap_key and time_loss.get("laps", {}).get(best_lap_key):
        loss_corners = time_loss["laps"][best_lap_key].get("corners", [])

    if loss_corners:
        lines.append("## Where you lost time (ranked)\n")
        for c in loss_corners[:8]:
            if c.get("loss_s", 0) < 0.02:
                continue
            lines.append(
                "### %s — +%.2fs\n" % (c.get("corner_display", c.get("corner", "?")), c.get("loss_s", 0))
            )
            if c.get("primary_action"):
                lines.append("**Drill:** %s\n" % c["primary_action"])
            elif c.get("primary_title"):
                lines.append("**Issue:** %s\n" % c["primary_title"])
        lines.append("")

    corrections = [a for a in ev["annotations"] if a.get("category") == "correction" and a.get("spline", 0) > 0]
    opportunities = [a for a in ev["annotations"] if a.get("category") == "opportunity"]
    setup = [a for a in ev["annotations"] if a.get("category") == "setup"]

    if not corrections and ev["corner_reports"]:
        corrections = ev["corner_reports"]
    if not opportunities and ev["pace_opportunities"]:
        opportunities = ev["pace_opportunities"]

    if corrections:
        lines.append("## Driver corrections (fix these first)\n")
        lines.append(
            "Highlighted **orange** on telemetry. Each item is derived from phase telemetry "
            "(speed, G, steering, inputs) vs your personal reference.\n\n"
        )
        for ann in corrections[:12]:
            lines.append(_fmt_corner_block(ann))

    if opportunities:
        lines.append("## Limit-pushing opportunities\n")
        lines.append(
            "Highlighted **cyan** on telemetry. These are places you were clean but left time "
            "vs your own best sector phases — not mistakes, missed grip/speed.\n\n"
        )
        for ann in opportunities[:12]:
            lines.append(_fmt_corner_block(ann))

    if setup:
        lines.append("## Setup changes\n")
        for ann in setup:
            lines.append(_fmt_corner_block(ann))

    if not corrections and not opportunities:
        lines.append("No corner-specific coaching was exported for this stint.\n")

    lines.append(
        "---\n*Regions on charts match `spline_start`–`spline_end` per corner. "
        "Click a chip above the charts or a map pin to jump there.*\n"
    )
    return "\n".join(lines)


def build_llm_narrative(bundle_dir, model=None):
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None

    model = model or os.environ.get("VRE_NARRATIVE_MODEL", "gpt-4o-mini")
    evidence = collect_evidence(bundle_dir)

    system = (
        "You are a race engineer writing a stint debrief for a sim racer. "
        "Use ONLY the JSON evidence provided. Do not invent corners, times, or causes. "
        "Structure: Executive summary (2-3 sentences), then corner-by-corner coaching "
        "using WHAT / WHY / HOW from the evidence, then opportunities, then setup if any. "
        "Reference specific metrics from evidence objects when present. "
        "Tone: direct, technical, actionable — like a real engineer, not generic motivational talk."
    )
    user = "Evidence JSON:\n" + json.dumps(evidence, indent=2)

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.35,
    }).encode("utf-8")

    req = urllib_request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib_request.urlopen(req, timeout=90)
        payload = json.loads(resp.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"]
    except Exception as exc:
        print("LLM narrative failed: %s" % exc, file=sys.stderr)
        return None


def build_narrative_sections(bundle_dir):
    """Structured sections for corner-filtered debrief in the viewer."""
    ev = collect_evidence(bundle_dir)
    sections = []
    time_loss = ev.get("time_loss") or {}
    laps = time_loss.get("laps") or {}
    if not laps:
        return sections
    best_key = sorted(
        laps.keys(),
        key=lambda k: laps[k].get("lap_time_ms", 999999999),
    )[0]
    for c in laps[best_key].get("corners", [])[:8]:
        if c.get("loss_s", 0) < 0.02:
            continue
        parts = ["**Loss:** +%.2fs" % c.get("loss_s", 0)]
        if c.get("primary_title"):
            parts.append("**Issue:** %s" % c["primary_title"])
        if c.get("primary_action"):
            parts.append("**Drill:** %s" % c["primary_action"])
        sections.append({
            "corner_id": c.get("corner"),
            "heading": c.get("corner_display", c.get("corner", "")),
            "body": "\n".join(parts),
        })
    return sections


def write_narratives(bundle_dir, use_llm=False):
    analysis = os.path.join(bundle_dir, "analysis")
    os.makedirs(analysis, exist_ok=True)

    det = build_deterministic_narrative(bundle_dir)
    det_path = os.path.join(analysis, "narrative.md")
    with open(det_path, "w") as fh:
        fh.write(det)

    combined = det
    if use_llm:
        llm = build_llm_narrative(bundle_dir)
        if llm:
            llm_path = os.path.join(analysis, "narrative_llm.md")
            with open(llm_path, "w") as fh:
                fh.write("# AI engineer debrief\n\n")
                fh.write(llm)
                fh.write("\n\n---\n*Generated from exported coaching evidence. Verify against charts.*\n")
            combined = (
                "# Stint debrief\n\n"
                "## Engineer analysis (AI)\n\n" + llm +
                "\n\n---\n\n## Structured evidence (source)\n\n" + det
            )

    json_path = os.path.join(analysis, "narrative.json")
    sections = build_narrative_sections(bundle_dir)
    with open(json_path, "w") as fh:
        json.dump({"markdown": combined, "has_llm": use_llm, "sections": sections}, fh, indent=2)

    return det_path


def build_narrative(bundle_dir):
    return build_deterministic_narrative(bundle_dir)


def main():
    parser = argparse.ArgumentParser(description="Generate stint narrative from replay bundle")
    parser.add_argument("bundle_dir", help="Exported replay folder")
    parser.add_argument("--output", "-o", default="", help="Output markdown path (deterministic only)")
    parser.add_argument("--llm", action="store_true", help="Also call OpenAI API (OPENAI_API_KEY)")
    args = parser.parse_args()

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(build_deterministic_narrative(args.bundle_dir))
        print("Wrote %s" % args.output)
    else:
        path = write_narratives(args.bundle_dir, use_llm=args.llm or bool(os.environ.get("OPENAI_API_KEY")))
        print("Wrote %s" % path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
