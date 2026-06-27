# ac_app/lib/decision_engine.py
# Python 3.3 compatible — stdlib only

try:
    from yaw_gates import GATE_INTENTIONAL, GATE_LOSS_OF_CONTROL, GATE_NEUTRAL
except ImportError:
    from .yaw_gates import GATE_INTENTIONAL, GATE_LOSS_OF_CONTROL, GATE_NEUTRAL

VERDICT_DRIVER_ERROR = "DRIVER_ERROR"
VERDICT_SETUP_FLAW = "SETUP_FLAW"
VERDICT_SETUP_STABILIZE = "SETUP_STABILIZE"
VERDICT_INTENTIONAL = "INTENTIONAL"
VERDICT_NONE = "NONE"


class DecisionResult(object):
    __slots__ = (
        "verdict", "input_score", "output_score", "symptom",
        "corner", "phase", "evidence",
    )

    def __init__(self, verdict, input_score, output_score, symptom=None,
                 corner="", phase="", evidence=None):
        self.verdict = verdict
        self.input_score = input_score
        self.output_score = output_score
        self.symptom = symptom
        self.corner = corner
        self.phase = phase
        self.evidence = evidence or {}


class DecisionEngine(object):
    """Three-way classifier: driver error vs setup flaw vs intentional."""

    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {}
        self._symptom_counts = {}

    def _thresh(self, key, default):
        return self.thresholds.get(key, default)

    @staticmethod
    def _clamp01(value):
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    def compute_input_score(self, input_deviation):
        if input_deviation is None:
            return 0.0
        brake = input_deviation.get("brake", 0.0)
        speed = input_deviation.get("speed", 0.0) / 5.0
        steer = input_deviation.get("steer", 0.0) / 0.05
        score = (brake + speed + steer) / 3.0
        return self._clamp01(score)

    def compute_output_score(self, balance_state):
        if balance_state is None or not balance_state.valid:
            return 0.0
        import math
        delta_us = abs(math.degrees(balance_state.delta_us)) / 3.0
        ay_loss = 1.0 - balance_state.ay_efficiency
        slip = abs(balance_state.slip_balance) / 0.05
        score = (delta_us + ay_loss + slip) / 3.0
        return self._clamp01(score)

    def _track_symptom(self, key):
        self._symptom_counts[key] = self._symptom_counts.get(key, 0) + 1
        return self._symptom_counts[key]

    def evaluate(self, yaw_gate, input_deviation, balance_state,
                 corner="", phase="", symptom=None, lap=0, telemetry_context=None):
        input_score = self.compute_input_score(input_deviation)
        output_score = self.compute_output_score(balance_state)
        ctx = telemetry_context or {}
        if ctx.get("surface_severity", 0) > 0:
            output_score = max(output_score, min(1.0, ctx["surface_severity"]))
        if ctx.get("symptom_metric", 0) > 0:
            output_score = max(output_score, min(1.0, ctx["symptom_metric"] * 0.4))

        evidence = {
            "input_score": input_score,
            "output_score": output_score,
            "yaw_gate": yaw_gate.gate,
            "yaw_confidence": yaw_gate.confidence,
            "corner_delta_s": ctx.get("corner_delta_s", 0.0),
            "surface_severity": ctx.get("surface_severity", 0.0),
            "performance_cost": ctx.get("performance_cost", False),
        }

        if yaw_gate.gate == GATE_INTENTIONAL:
            return DecisionResult(
                VERDICT_INTENTIONAL, input_score, output_score,
                symptom, corner, phase, evidence,
            )

        # ponytail: spin is not a setup flaw — do not queue stabilization tweaks
        if yaw_gate.gate == GATE_LOSS_OF_CONTROL:
            return DecisionResult(
                VERDICT_NONE, input_score, output_score,
                symptom or "loss_of_control", corner, phase, evidence,
            )

        driver_thresh = self._thresh("INPUT_SCORE_DRIVER", 0.6)
        clean_thresh = self._thresh("INPUT_SCORE_CLEAN", 0.3)
        setup_thresh = self._thresh("OUTPUT_SCORE_SETUP", 0.5)
        stabilize_thresh = self._thresh("OUTPUT_SCORE_STABILIZE", 0.35)
        persist_laps = int(self._thresh("SETUP_PERSIST_LAPS", 3))
        stabilize_persist = int(self._thresh("SETUP_STABILIZE_PERSIST_LAPS", 2))
        experiment_persist = int(self._thresh("SETUP_EXPERIMENT_PERSIST_LAPS", 1))
        input_margin = float(self._thresh("SETUP_EXPERIMENT_INPUT_MARGIN", 0.15))
        surface_persist = int(self._thresh("SURFACE_SETUP_PERSIST_LAPS", 2))
        min_delta = float(self._thresh("CORNER_DELTA_SETUP_S", 0.03))
        has_cost = ctx.get("corner_delta_s", 0.0) >= min_delta
        perf_cost = ctx.get("performance_cost", False)

        if ctx.get("driver_from_surface"):
            return DecisionResult(
                VERDICT_DRIVER_ERROR, input_score, output_score,
                symptom, corner, phase, evidence,
            )

        if input_score > driver_thresh:
            setup_explains = (
                output_score > stabilize_thresh
                and (has_cost or perf_cost or output_score > setup_thresh)
            )
            if setup_explains and input_score <= driver_thresh + input_margin:
                sym = symptom or "mid_understeer"
                count = self._track_symptom("%s:%s:%s" % (corner, phase, sym))
                if count >= experiment_persist or has_cost or perf_cost:
                    verdict = (
                        VERDICT_SETUP_FLAW if output_score > setup_thresh
                        else VERDICT_SETUP_STABILIZE
                    )
                    return DecisionResult(
                        verdict, input_score, output_score,
                        sym, corner, phase, evidence,
                    )
            return DecisionResult(
                VERDICT_DRIVER_ERROR, input_score, output_score,
                symptom, corner, phase, evidence,
            )

        if input_score < clean_thresh and output_score > stabilize_thresh:
            sym = symptom or "mid_understeer"
            count = self._track_symptom("%s:%s:%s" % (corner, phase, sym))
            is_surface = sym in (
                "kerb_grip_loss", "painted_kerb_slip", "kerb_overload",
                "platform_hop", "bump_unsettled", "kerb_instability",
            )
            needed = surface_persist if is_surface else persist_laps
            has_memory = ctx.get("setup_weight", 0.0) > float(
                self._thresh("SETUP_MEMORY_MIN_WEIGHT", 0.15),
            )
            if output_score > setup_thresh and (
                count >= needed or has_cost or has_memory or ctx.get("setup_from_surface")
            ):
                return DecisionResult(
                    VERDICT_SETUP_FLAW, input_score, output_score,
                    sym, corner, phase, evidence,
                )
            if count >= stabilize_persist or has_cost or ctx.get("setup_from_surface"):
                return DecisionResult(
                    VERDICT_SETUP_STABILIZE, input_score, output_score,
                    sym, corner, phase, evidence,
                )

        if input_score < clean_thresh and output_score < setup_thresh:
            return DecisionResult(
                VERDICT_NONE, input_score, output_score,
                symptom, corner, phase, evidence,
            )

        return DecisionResult(
            VERDICT_NONE, input_score, output_score,
            symptom, corner, phase, evidence,
        )

    def reset_lap_counts(self):
        self._symptom_counts = {}
