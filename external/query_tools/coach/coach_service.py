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
    "technique": re.compile(r"\b(technique|drill|what should|how do i|fix|lose time|time loss|brake|throttle|apex|coast\w*|exit)\b", re.I),
    "mechanism": re.compile(r"\b(why|understeer|oversteer|grip|tyre|tire|aero|balance|mechanism|physics)\b", re.I),
    "stint": re.compile(r"\b(stint|session|summary|debrief|overall)\b", re.I),
    "setup": re.compile(r"\b(setup|set-up|bias|diff|anti-?roll|arb|camber|toe|pressure|gearing|gamma|calibrat\w*)\b", re.I),
    "line": re.compile(r"\b(line|turn-?in point|track-?out|more (left|right))\b", re.I),
}


TIE_PRIORITY = ("incident", "setup", "line", "technique", "mechanism", "stint")


def classify_question(question):
    q = question or ""
    scores = {k: (1 if pat.search(q) else 0) for k, pat in QUESTION_PATTERNS.items()}
    best = max(TIE_PRIORITY, key=lambda k: (scores[k], -TIE_PRIORITY.index(k)))
    return best if scores[best] > 0 else "technique"


def _system_prompt(question_type):
    base = (
        "You are a race engineer coaching a sim racer. Use ONLY the evidence JSON provided. "
        "Do not invent corners, lap times, or metrics. "
        "Respond with valid JSON only: "
        '{"summary":"...", "what":"...", "why":"...", "how":"...", "drill":"...", '
        '"citations":["evidence_id", ...], "confidence":0.0-1.0}. '
        "Cite evidence_id for every metric. Max 1-2 actionable fixes. "
        "Structure: WHAT happened, WHY (vehicle dynamics mechanism), HOW (one drill). "
        "Find the root cause: late throttle, coasting and running wide are symptoms; name the upstream input "
        "(pedal gap, brake release, turn-in point) that caused them. Give a visual cue, not a distance. "
        "Tone: direct, technical, actionable — like a real engineer."
    )
    addenda = {
        "incident": " Focus on the pre-window inputs before beta spike. Distinguish driver error from setup.",
        "technique": " Compare to reference phase metrics. One drill per corner. Do not prescribe 'throttle earlier' "
                     "or 'stop coasting' without the cause that makes the driver wait.",
        "mechanism": " Explain tyre/load/input physics using evidence numbers only.",
        "stint": " Executive summary then top 2 time-loss corners with drills.",
        "setup": " Pace first: never recommend a change because it makes the car calmer. Check input calibration "
                 "and technique causes before setup. Prefer grip levers (pressures, camber, gearing) over stability "
                 "levers (forward bias, more diff coast, softer rear bar). One change, judged on >=5 laps.",
        "line": " Judge lines against the driver's own faster passes, not the AI line. Prefer later/wider turn-in "
                "and late apex when slow passes are both slower and wider mid-corner.",
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
