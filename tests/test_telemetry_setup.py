
def test_telemetry_context_surface_setup(thresholds):
    from telemetry_context import build, SURFACE_SYMPTOMS

    class Hit(object):
        symptom = "kerb_grip_loss"
        confidence = 0.85

    summary = {
        "phases": {"mid": {"steer_corrections": 0, "samples": 5}},
        "surface": {"kerb_grip_loss": 2, "max_load_drop_pct": 18.0},
    }
    ctx = build(
        summary, None, {"brake": 0.05, "speed": 1.0, "steer": 0.01},
        corner_delta_s=0.05, symptom_hit=Hit(), setup_memory=None,
        thresholds=thresholds,
    )
    assert ctx["setup_from_surface"] is True
    assert ctx["performance_cost"] is True
    assert "kerb_grip_loss" in SURFACE_SYMPTOMS


def test_decision_surface_setup_with_cost(thresholds):
    from decision_engine import DecisionEngine, VERDICT_SETUP_FLAW
    from yaw_gates import YawGateResult, GATE_NEUTRAL

    de = DecisionEngine(thresholds)

    class Bal(object):
        valid = True
        delta_us = 0.05
        ay_efficiency = 0.88
        slip_balance = 0.04

    ctx = {
        "corner_delta_s": 0.06,
        "surface_severity": 0.5,
        "symptom_metric": 0.4,
        "performance_cost": True,
        "setup_from_surface": True,
        "input_clean": True,
    }
    result = de.evaluate(
        YawGateResult(GATE_NEUTRAL, 0.5),
        {"brake": 0.05, "speed": 1.0, "steer": 0.01},
        Bal(), corner="Swimming Pool", phase="mid",
        symptom="kerb_grip_loss", telemetry_context=ctx,
    )
    assert result.verdict == VERDICT_SETUP_FLAW


def test_setup_detector_performance_gate(thresholds):
    from setup_catalog import SetupCatalog
    from setup_detector import SetupFlawDetector, SetupDelta
    from decision_engine import DecisionResult, VERDICT_SETUP_FLAW

    cat = SetupCatalog()
    cat.load_car_config(cat.default_paths()[0])
    cat.load_symptom_map(cat.default_paths()[1])
    det = SetupFlawDetector(cat, thresholds=thresholds)
    decision = DecisionResult(
        VERDICT_SETUP_FLAW, 0.1, 0.7, "kerb_grip_loss", "Turn 8", "mid",
        evidence={"corner_delta_s": 0.0, "performance_cost": False},
    )
    assert det.detect(decision, {}, laps_persisting=1, context={}) == []
    decision.evidence["corner_delta_s"] = 0.05
    ctx = {"corner_delta_s": 0.05}
    values = {"DAMP_BUMP_LF": 5, "DAMP_BUMP_RF": 5, "DAMP_REBOUND_LF": 5}
    deltas = det.detect(decision, values, laps_persisting=1, context=ctx)
    assert len(deltas) >= 1
