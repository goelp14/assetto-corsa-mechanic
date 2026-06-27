from decision_engine import (
    DecisionEngine, VERDICT_DRIVER_ERROR, VERDICT_INTENTIONAL, VERDICT_NONE,
)
from yaw_gates import YawGateResult, GATE_INTENTIONAL, GATE_NEUTRAL, GATE_LOSS_OF_CONTROL


class _Bal(object):
    valid = True
    delta_us = 0.1
    ay_efficiency = 0.8
    slip_balance = 0.1


def test_driver_error_verdict(thresholds):
    de = DecisionEngine(thresholds)
    yaw = YawGateResult(GATE_NEUTRAL, 0.5)
    dev = {"brake": 0.5, "speed": 10.0, "steer": 0.1}
    result = de.evaluate(yaw, dev, _Bal(), corner="Turn 4", phase="entry")
    assert result.verdict == VERDICT_DRIVER_ERROR


def test_intentional_verdict(thresholds):
    de = DecisionEngine(thresholds)
    yaw = YawGateResult(GATE_INTENTIONAL, 0.9)
    result = de.evaluate(yaw, None, _Bal())
    assert result.verdict == VERDICT_INTENTIONAL


def test_loss_of_control_not_setup_stabilize(thresholds):
    de = DecisionEngine(thresholds)
    yaw = YawGateResult(GATE_LOSS_OF_CONTROL, 0.9)
    result = de.evaluate(yaw, None, _Bal(), corner="Turn 6", phase="mid")
    assert result.verdict == VERDICT_NONE
    assert result.symptom == "loss_of_control"


def test_setup_stabilize_after_two_laps(thresholds):
    from decision_engine import VERDICT_SETUP_STABILIZE, VERDICT_SETUP_FLAW

    de = DecisionEngine(thresholds)
    yaw = YawGateResult(GATE_NEUTRAL, 0.5)
    dev = {"brake": 0.05, "speed": 1.0, "steer": 0.01}
    bal = _Bal()
    bal.ay_efficiency = 0.82
    ctx = {"corner_delta_s": 0.0, "setup_weight": 0.0}
    r1 = de.evaluate(
        yaw, dev, bal, corner="Turn 4", phase="mid",
        symptom="mid_understeer", telemetry_context=ctx,
    )
    assert r1.verdict == VERDICT_SETUP_STABILIZE
    ctx_cost = dict(ctx)
    ctx_cost["corner_delta_s"] = 0.05
    r2 = de.evaluate(
        yaw, dev, bal, corner="Turn 4", phase="mid",
        symptom="mid_understeer", telemetry_context=ctx_cost,
    )
    assert r2.verdict == VERDICT_SETUP_FLAW


def test_marginal_driver_can_trigger_setup_experiment(thresholds):
    from decision_engine import VERDICT_SETUP_STABILIZE, VERDICT_SETUP_FLAW

    de = DecisionEngine(thresholds)
    yaw = YawGateResult(GATE_NEUTRAL, 0.5)
    dev = {"brake": 0.35, "speed": 4.0, "steer": 0.04}
    bal = _Bal()
    bal.ay_efficiency = 0.82
    ctx = {"corner_delta_s": 0.04, "performance_cost": True}
    result = de.evaluate(
        yaw, dev, bal, corner="Turn 6", phase="mid",
        symptom="mid_understeer", telemetry_context=ctx,
    )
    assert result.verdict in (VERDICT_SETUP_STABILIZE, VERDICT_SETUP_FLAW)
