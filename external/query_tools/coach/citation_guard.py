"""Validate LLM responses against evidence pack citations."""

from __future__ import print_function

import re


_NUMERIC = re.compile(r"\b\d+(?:\.\d+)?\b")


def _extract_numbers(text):
    if not text:
        return set()
    return set(_NUMERIC.findall(text))


def _pack_numbers(pack):
    """Collect numeric strings present in the evidence pack."""
    nums = set()
    for key in ("stint_summary", "sector_bests", "gg_envelope"):
        blob = pack.get(key)
        if blob:
            nums.update(_extract_numbers(str(blob)))
    for section in (
        "incidents", "corner_reports", "annotations", "time_loss_corners",
        "pace_opportunities", "sample_window",
    ):
        for item in pack.get(section) or []:
            nums.update(_extract_numbers(str(item)))
    plan = pack.get("session_plan") or {}
    for item in plan.get("items") or []:
        nums.update(_extract_numbers(str(item)))
    return nums


def validate_citations(response, pack):
    """
    Return (ok, issues).
    Every cited evidence_id must exist; numeric claims should appear in pack.
    """
    issues = []
    valid_ids = set(pack.get("citation_ids") or [])
    cited = response.get("citations") or []
    for cid in cited:
        if cid not in valid_ids:
            issues.append("unknown citation: %s" % cid)

    pack_nums = _pack_numbers(pack)
    text = " ".join([
        response.get("summary", ""),
        response.get("what", ""),
        response.get("why", ""),
        response.get("how", ""),
        response.get("drill", ""),
    ])
    for num in _extract_numbers(text):
        if num not in pack_nums and float(num) > 2:
            issues.append("ungrounded number: %s" % num)

    return len(issues) == 0, issues
