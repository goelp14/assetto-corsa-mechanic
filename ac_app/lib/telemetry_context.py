# ac_app/lib/telemetry_context.py
# Fuse driver inputs + car telemetry for setup vs coaching decisions.

SURFACE_SYMPTOMS = frozenset((
    "kerb_grip_loss", "painted_kerb_slip", "kerb_overload",
    "platform_hop", "bump_unsettled", "kerb_instability",
))


def _surface_severity(surface, thresholds):
    if not surface:
        return 0.0
    t = thresholds or {}
    score = 0.0
    score += surface.get("kerb_grip_loss", 0) * float(t.get("SURFACE_WEIGHT_KERB_GRIP", 0.28))
    score += surface.get("platform_hops", 0) * float(t.get("SURFACE_WEIGHT_HOP", 0.22))
    score += surface.get("painted_kerb_slip", 0) * float(t.get("SURFACE_WEIGHT_PAINTED", 0.18))
    score += surface.get("kerb_overload", 0) * float(t.get("SURFACE_WEIGHT_OVERLOAD", 0.15))
    score += surface.get("bump_hits", 0) * float(t.get("SURFACE_WEIGHT_BUMP", 0.12))
    if surface.get("max_susp_pct", 0) > float(t.get("KERB_SUSP_PCT", 0.85)):
        score += 0.1
    return min(score, 1.0)


def _phase_steer_corrections(summary):
    if not summary:
        return 0
    total = 0
    for pdata in summary.get("phases", {}).values():
        total += pdata.get("steer_corrections", 0)
    return total


def symptom_metric(summary, balance):
    return _symptom_metric(summary, balance)


def _symptom_metric(summary, balance):
    metric = 0.0
    if summary:
        surf = summary.get("surface", {})
        metric += surf.get("kerb_grip_loss", 0) * 0.25
        metric += surf.get("platform_hops", 0) * 0.2
        metric += surf.get("bump_hits", 0) * 0.08
        for pdata in summary.get("phases", {}).values():
            metric += pdata.get("max_rear_slip", 0) * 0.15
            metric += pdata.get("max_front_slip", 0) * 0.1
    if balance is not None and getattr(balance, "valid", False):
        import math
        metric += abs(math.degrees(balance.delta_us)) * 0.05
        metric += (1.0 - balance.ay_efficiency) * 0.5
    return metric


def build(summary, balance, input_deviation, corner_delta_s=0.0,
          symptom_hit=None, speed_class="medium", setup_memory=None,
          thresholds=None):
    """Single telemetry bundle for decision + setup + effectiveness tracking."""
    thresholds = thresholds or {}
    surface = summary.get("surface", {}) if summary else {}
    symptom = symptom_hit.symptom if symptom_hit else ""
    is_surface = symptom in SURFACE_SYMPTOMS

    inp_brake = (input_deviation or {}).get("brake", 0.0)
    inp_speed = (input_deviation or {}).get("speed", 0.0)
    inp_steer = (input_deviation or {}).get("steer", 0.0)
    input_score = min(1.0, (inp_brake + inp_speed / 5.0 + inp_steer / 0.05) / 3.0)

    clean_thresh = float(thresholds.get("INPUT_SCORE_CLEAN", 0.3))
    driver_thresh = float(thresholds.get("INPUT_SCORE_DRIVER", 0.6))
    input_clean = input_score < clean_thresh

    surface_severity = _surface_severity(surface, thresholds)
    steer_corr = _phase_steer_corrections(summary)

    car_struggling = surface_severity > 0.2
    if balance is not None and balance.valid:
        import math
        if abs(math.degrees(balance.delta_us)) > float(thresholds.get("MID_US_DEG", 2.0)):
            car_struggling = True
        if balance.ay_efficiency < float(thresholds.get("AY_EFFICIENCY_MIN", 0.92)):
            car_struggling = True

    min_delta = float(thresholds.get("CORNER_DELTA_SETUP_S", 0.03))
    performance_cost = corner_delta_s >= min_delta

    best_weight = 0.0
    if setup_memory is not None:
        best_weight = setup_memory.best_weight_for_symptom(symptom)

    driver_from_surface = (
        is_surface
        and (input_score > driver_thresh or steer_corr >= 2)
    )
    setup_from_surface = (
        is_surface
        and input_clean
        and not driver_from_surface
        and (performance_cost or surface_severity >= 0.35)
    )

    return {
        "surface": surface,
        "surface_severity": surface_severity,
        "surface_symptoms": [symptom] if is_surface else [],
        "corner_delta_s": corner_delta_s,
        "performance_cost": performance_cost,
        "input_score": input_score,
        "input_clean": input_clean,
        "car_struggling": car_struggling,
        "steer_corrections": steer_corr,
        "speed_class": speed_class,
        "symptom_metric": _symptom_metric(summary, balance),
        "setup_weight": best_weight,
        "driver_from_surface": driver_from_surface,
        "setup_from_surface": setup_from_surface,
        "symptom_confidence": getattr(symptom_hit, "confidence", 0.0) if symptom_hit else 0.0,
    }
