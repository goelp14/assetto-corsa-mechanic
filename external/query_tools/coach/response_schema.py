"""Structured coaching response schema."""

from __future__ import print_function


def empty_response(reason="insufficient_evidence"):
    return {
        "summary": "",
        "what": "",
        "why": "",
        "how": "",
        "drill": "",
        "citations": [],
        "confidence": 0.0,
        "status": reason,
    }


def normalize_response(data):
    """Ensure response dict has required keys."""
    base = empty_response("ok")
    if not isinstance(data, dict):
        return base
    for key in ("summary", "what", "why", "how", "drill"):
        base[key] = str(data.get(key) or "")
    base["citations"] = list(data.get("citations") or [])
    base["confidence"] = float(data.get("confidence") or 0.0)
    base["status"] = data.get("status") or "ok"
    return base
