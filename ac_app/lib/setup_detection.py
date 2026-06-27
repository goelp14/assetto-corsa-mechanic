# ac_app/lib/setup_detection.py
# Python 3.3 compatible — stdlib only

try:
    from decision_engine import VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE
except ImportError:
    from .decision_engine import VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE


def build_detection_record(
    result,
    corner,
    corner_display,
    phase,
    spline,
    symptom,
    telem_ctx=None,
    source="eval",
    reason="",
):
    """Human-readable detection context for archive + replay export."""
    telem_ctx = telem_ctx or {}
    corner_delta = float(telem_ctx.get("corner_delta_s", 0.0))
    sym = (symptom or "balance").replace("_", " ")
    phase_label = phase or "corner"
    corner_label = corner_display or corner or "track"
    what = "%s (%s) — %s" % (corner_label, phase_label, sym)
    why_parts = []

    verdict = getattr(result, "verdict", "") if result else ""
    input_score = getattr(result, "input_score", 0.0) if result else 0.0
    output_score = getattr(result, "output_score", 0.0) if result else 0.0

    if verdict in (VERDICT_SETUP_FLAW, VERDICT_SETUP_STABILIZE):
        why_parts.append("balance output score %.2f" % output_score)
        if input_score < 0.35:
            why_parts.append("inputs relatively clean (%.2f)" % input_score)
        elif input_score < 0.75:
            why_parts.append(
                "marginal inputs (%.2f) — trying setup tweak" % input_score
            )
        else:
            why_parts.append("inputs noisy (%.2f)" % input_score)
        if corner_delta >= 0.03:
            why_parts.append("costing %.2fs at this corner" % corner_delta)
    elif source == "bootstrap":
        what = "Track bootstrap — %s" % (reason or sym)
        why_parts.append("Starting setup baseline for this track")
    elif source == "tyre":
        why_parts.append("Tyre temperature/window outside ideal")
    elif reason:
        why_parts.append(reason)

    return {
        "corner": corner or "",
        "corner_display": corner_label,
        "phase": phase or "",
        "symptom": symptom or "",
        "spline": round(float(spline), 4),
        "verdict": verdict,
        "input_score": round(float(input_score), 3),
        "output_score": round(float(output_score), 3),
        "corner_delta_s": round(corner_delta, 3),
        "detection_what": what,
        "detection_why": "; ".join(why_parts) if why_parts else (reason or ""),
        "source": source,
    }
