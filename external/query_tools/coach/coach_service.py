"""Orchestrate evidence-grounded coaching Q&A."""

from __future__ import print_function

import json
import os
import re

from coach_tools import CoachTools
from citation_guard import validate_citations
from evidence_pack import build_evidence_pack
from llm_provider import complete
from response_schema import empty_response, normalize_response


QUESTION_PATTERNS = {
    "incident": re.compile(r"\b(spin|spun|crash|lost control|high beta|incident|off track)\b", re.I),
    "technique": re.compile(r"\b(technique|drill|what should|how do i|fix|lose time|time loss|brake|throttle|apex)\b", re.I),
    "mechanism": re.compile(r"\b(why|understeer|oversteer|grip|tyre|tire|aero|balance|mechanism|physics)\b", re.I),
    "stint": re.compile(r"\b(stint|session|summary|debrief|overall)\b", re.I),
}


def classify_question(question):
    q = question or ""
    scores = {k: 0 for k in QUESTION_PATTERNS}
    for kind, pat in QUESTION_PATTERNS.items():
        if pat.search(q):
            scores[kind] += 1
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "technique"


def _system_prompt(question_type):
    base = (
        "You are a race engineer coaching a sim racer. Use ONLY the evidence JSON provided. "
        "Do not invent corners, lap times, or metrics. "
        "Respond with valid JSON only: "
        '{"summary":"...", "what":"...", "why":"...", "how":"...", "drill":"...", '
        '"citations":["evidence_id", ...], "confidence":0.0-1.0}. '
        "Cite evidence_id for every metric. Max 1-2 actionable fixes. "
        "Structure: WHAT happened, WHY (vehicle dynamics mechanism), HOW (one drill). "
        "Tone: direct, technical, actionable — like a real engineer."
    )
    addenda = {
        "incident": " Focus on the pre-window inputs before beta spike. Distinguish driver error from setup.",
        "technique": " Compare to reference phase metrics. One drill per corner.",
        "mechanism": " Explain tyre/load/input physics using evidence numbers only.",
        "stint": " Executive summary then top 2 time-loss corners with drills.",
    }
    return base + addenda.get(question_type, "")


def _deterministic_fallback(pack, question_type):
    incidents = pack.get("incidents") or []
    corners = pack.get("corner_reports") or []
    drills = (pack.get("session_plan") or {}).get("items") or []

    if question_type == "incident" and incidents:
        inc = incidents[0]
        hyp = (inc.get("hypotheses") or [{}])[0]
        return normalize_response({
            "summary": "Loss of control at spline %.3f (lap %s)." % (inc.get("spline", 0), inc.get("lap", "?")),
            "what": "Beta peaked at %.0f° in %s phase." % (
                inc.get("peak_beta_deg", 0), inc.get("phase", "exit"),
            ),
            "why": hyp.get("label", "Inputs exceeded grip envelope."),
            "how": "Ease inputs — separate brake, turn, then power.",
            "drill": "Repeat this corner with 0%% throttle until steering unwinds.",
            "citations": [inc.get("evidence_id")] if inc.get("evidence_id") else [],
            "confidence": inc.get("confidence", 0.7),
            "status": "deterministic",
        })

    if corners:
        c = corners[0]
        return normalize_response({
            "summary": c.get("title") or c.get("what", "")[:120],
            "what": c.get("what", ""),
            "why": c.get("why", ""),
            "how": c.get("action", ""),
            "drill": c.get("action", ""),
            "citations": [c.get("evidence_id")] if c.get("evidence_id") else [],
            "confidence": 0.75,
            "status": "deterministic",
        })

    if drills:
        d = drills[0]
        return normalize_response({
            "summary": "Top drill: %s" % d.get("drill", ""),
            "what": d.get("title", ""),
            "why": "Ranked time loss vs your reference laps.",
            "how": d.get("drill", ""),
            "drill": d.get("drill", ""),
            "citations": [d.get("evidence_id")] if d.get("evidence_id") else [],
            "confidence": 0.65,
            "status": "deterministic",
        })

    return empty_response("insufficient_evidence")


def ask_coach(bundle_dir, question, corner=None, spline=None, lap=None):
    question_type = classify_question(question)
    pack = build_evidence_pack(
        bundle_dir, corner=corner, spline=spline, lap=lap, question_type=question_type,
    )

    if not pack.get("citation_ids"):
        resp = _deterministic_fallback(pack, question_type)
        resp["question_type"] = question_type
        return resp

    system = _system_prompt(question_type)
    user = "Question: %s\n\nEvidence JSON:\n%s" % (
        question, json.dumps(pack, indent=2, default=str),
    )
    raw = complete(system, user)
    if not raw:
        resp = _deterministic_fallback(pack, question_type)
        resp["question_type"] = question_type
        return resp

    try:
        parsed = json.loads(raw)
    except ValueError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        parsed = json.loads(raw[start:end]) if start >= 0 and end > start else {}

    response = normalize_response(parsed)
    ok, issues = validate_citations(response, pack)
    if not ok:
        fallback = _deterministic_fallback(pack, question_type)
        fallback["guard_issues"] = issues
        fallback["question_type"] = question_type
        return fallback

    response["question_type"] = question_type
    response["status"] = "ok"
    return response
