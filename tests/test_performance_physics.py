import math
import os

from corner_phase_metrics import CornerPhaseMetrics, _PhaseStats
from symptom_detector import SymptomDetector
from setup_constraints import SetupConstraints
from gg_envelope import GgEnvelope
from session_analyst import SessionAnalyst
from telemetry_ingest import TelemetryIngest
from lap_time_analyzer import LapTimeAnalyzer


class _Dyn(object):
    beta = 0.05
    yaw_rate_err = 0.1
    alpha_f = 0.02
    alpha_r = 0.01


class _Bal(object):
    valid = True
    delta_us = math.radians(3.0)
    load_balance = 0.1


def _frame(speed=120, throttle=0.0, brake=0.5, slip_rear=0.05):
    return TelemetryIngest.frame_from_dict({
        "speed_kmh": speed,
        "throttle": throttle,
        "brake": brake,
        "acc_g": (0.0, 1.2, 0.0),
        "slip": (0.02, 0.02, slip_rear, slip_rear),
        "slip_ratio": (0.02, 0.02, slip_rear, slip_rear),
        "wheel_load": (3000, 3000, 2500, 2500),
        "susp_ratio": (0.3, 0.3, 0.3, 0.3),
    })


def test_phase_stats_entry_understeer():
    stats = _PhaseStats()
    for _ in range(5):
        stats.observe(_frame(brake=0.4), _Dyn(), _Bal())
    assert stats.mean_delta_us_deg() > 2.0


def test_corner_metrics_finalize():
    cpm = CornerPhaseMetrics()
    dyn, bal = _Dyn(), _Bal()
    for _ in range(8):
        cpm.observe("Turn 6", "entry", _frame(brake=0.4), dyn, bal)
    summary = cpm.finalize("Turn 6")
    assert summary is not None
    assert "entry" in summary["phases"]


def test_symptom_detector_exit_wheelspin(thresholds):
    det = SymptomDetector(thresholds)
    summary = {
        "corner": "Rascasse",
        "phases": {
            "exit": {
                "samples": 5,
                "max_throttle": 0.8,
                "max_rear_slip": 0.2,
                "mean_delta_us_deg": 0.0,
            },
        },
    }
    hits = det.detect_corner(summary, "low")
    symptoms = [h.symptom for h in hits]
    assert "exit_wheelspin" in symptoms


def test_setup_constraints_tyre_block():
    sc = SetupConstraints(SetupConstraints.default_path())
    blocked, reason = sc.is_blocked(
        "WING_0", "mid_understeer",
        {"tyre_axles": set(["front"]), "speed_class": "medium"},
    )
    assert blocked
    assert "tyre" in reason


def test_gg_envelope_grip_left():
    gg = GgEnvelope()
    for _ in range(20):
        gg.observe(100.0, 2.5)
    left = gg.grip_left_pct(100.0, 1.5)
    assert left > 10


def test_session_analyst_potential_gap():
    la = LapTimeAnalyzer()
    la._lap_times_ms = [82000]
    la._best_bucket_time = [0.5] * 360
    analyst = SessionAnalyst()
    digest = analyst.summarize_lap(
        82000, la, {"aggression": 0.5, "consistency": 0.7},
        {"Turn 6": 0.12}, True,
    )
    assert digest is not None
    assert float(digest["potential_gap_s"]) >= 0.0


def test_setup_tradeoff_at_limit():
    from setup_catalog import SetupCatalog
    from setup_detector import SetupFlawDetector, SetupDelta
    from decision_engine import DecisionResult, VERDICT_SETUP_FLAW

    cat = SetupCatalog()
    cat.load_car_config(cat.default_paths()[0])
    cat.load_symptom_map(cat.default_paths()[1])
    cat.load_tradeoffs(os.path.join(
        os.path.dirname(__file__), "..", "ac_app", "config", "setup_tradeoffs.json",
    ))
    det = SetupFlawDetector(cat)
    decision = DecisionResult(
        VERDICT_SETUP_FLAW, 0.1, 0.8, "mid_oversteer", "Turn 6", "mid",
    )
    values = {"WING_1": 20, "WING_0": 15, "ARB_REAR": 50000}
    deltas = det.detect(decision, values, laps_persisting=5)
    assert len(deltas) >= 1
    assert deltas[0].section in ("WING_0", "ARB_REAR", "FRONT_BIAS", "DIFF_PRELOAD")


def test_line_analyzer_wide_needed(thresholds):
    from line_analyzer import LineAnalyzer

    la = LineAnalyzer(thresholds)
    summary = {
        "phases": {
            "entry": {"steer_corrections": 3, "mean_steer_abs": 0.12, "samples": 5},
            "mid": {"min_speed_kmh": 110, "steer_corrections": 0, "samples": 5},
        },
    }
    ref = {"phases": {"entry": {"mean_steer_abs": 0.05}, "mid": {"min_speed_kmh": 118}}}
    corner_cfg = {
        "name": "Turn 6",
        "line": {"profile": "late_apex", "width_bias": "wide"},
    }
    issue = la.analyze("Turn 6", summary, ref, {}, corner_cfg=corner_cfg)
    assert issue is not None
    assert issue.template_key == "line_wide_needed"


def test_line_strategy_tight_rubber_no_wide_penalty(thresholds):
    from line_strategy import LineStrategyEngine

    engine = LineStrategyEngine(thresholds)
    summary = {
        "phases": {
            "entry": {"steer_corrections": 1, "mean_steer_abs": 0.04, "samples": 5},
            "mid": {"min_speed_kmh": 115, "steer_corrections": 0, "samples": 5},
        },
    }
    ref = {"phases": {"entry": {"mean_steer_abs": 0.06}, "mid": {"min_speed_kmh": 118}}}
    corner_cfg = {
        "name": "Rascasse",
        "line": {"profile": "tight_rubber", "width_bias": "narrow"},
    }
    result = engine.analyze("Rascasse", summary, ref, corner_cfg)
    assert result is None


def test_line_strategy_too_wide_on_rubber(thresholds):
    from line_strategy import LineStrategyEngine

    engine = LineStrategyEngine(thresholds)
    summary = {
        "phases": {
            "entry": {"steer_corrections": 1, "mean_steer_abs": 0.14, "samples": 5},
            "mid": {"min_speed_kmh": 110, "steer_corrections": 0, "samples": 5},
        },
    }
    ref = {"phases": {"entry": {"mean_steer_abs": 0.06}, "mid": {"min_speed_kmh": 118}}}
    corner_cfg = {
        "name": "Rascasse",
        "line": {
            "profile": "tight_rubber",
            "width_bias": "narrow",
            "grip_note": "Stay on inside rubber",
        },
    }
    result = engine.analyze("Rascasse", summary, ref, corner_cfg)
    assert result is not None
    assert result.template_key == "line_too_wide"


def test_line_strategy_compromise_suppressed(thresholds):
    from line_strategy import LineStrategyEngine

    engine = LineStrategyEngine(thresholds)
    summary = {
        "phases": {
            "entry": {"steer_corrections": 1, "mean_steer_abs": 0.08, "samples": 5},
            "mid": {"min_speed_kmh": 105, "steer_corrections": 1, "samples": 5},
        },
    }
    ref = {"phases": {"entry": {"mean_steer_abs": 0.06}, "mid": {"min_speed_kmh": 115}}}
    corner_cfg = {
        "name": "Swimming Pool",
        "line": {
            "profile": "compromise_setup",
            "chain": "harbour_s3",
            "chain_role": "setup",
            "chain_payoff": "Rascasse",
        },
    }
    chain_deltas = {"harbour_s3": {"Swimming Pool": 0.12, "Rascasse": 0.03}}
    result = engine.analyze(
        "Swimming Pool", summary, ref, corner_cfg, chain_deltas,
    )
    assert result is None


def test_line_strategy_chain_summary(thresholds):
    from line_strategy import LineStrategyEngine

    engine = LineStrategyEngine(thresholds)
    meta = {
        "id": "harbour_s3",
        "corners": ["Swimming Pool", "Rascasse"],
        "goal": "Harbour chain exit",
    }
    digest = engine.chain_summary(
        "harbour_s3", meta,
        {"Swimming Pool": 0.05, "Rascasse": 0.15},
        None,
    )
    assert digest is not None
    assert float(digest["total_delta_s"]) == 0.20
    assert digest["worst_corner"] == "Rascasse"


def test_phase_pace_always_finds_gain(thresholds):
    from phase_pace import PhasePaceCoach

    coach = PhasePaceCoach(thresholds)
    summary = {"phases": {"mid": {"samples": 5, "peak_ay_g": 2.0, "min_speed_kmh": 115}}}
    ref = {"phases": {"mid": {"peak_ay_g": 2.5, "min_speed_kmh": 120}}}
    gain = coach.next_gain(summary, ref, "Hairpin", 0.05)
    assert gain is not None
    assert float(gain["gain_s"]) > 0


def test_surface_kerb_grip_loss(thresholds):
    from surface_event_detector import SurfacePhaseStats, primary_surface_symptom

    stats = SurfacePhaseStats()
    prev_load = 12000.0
    for i in range(5):
        frame = _frame(speed=100, brake=0.2)
        frame.susp_ratio = (0.9, 0.88, 0.3, 0.3)
        frame.wheel_load = (2800, 2800, 2800, 2800) if i < 2 else (2200, 2200, 2200, 2200)
        frame.slip_ratio = (0.15, 0.15, 0.18, 0.18)
        frame.acc_g = (0.5, 1.0, 0.3)
        stats.observe(frame, _Dyn(), _Bal(), thresholds)
    surf = stats.to_dict()
    hit = primary_surface_symptom(surf, thresholds)
    assert hit is not None
    assert hit[0] in ("kerb_grip_loss", "kerb_overload", "platform_hop")


def test_line_defaults_infer_chains():
    from line_defaults import LineDefaults

    corners = [
        {"name": "A", "spline_start": 0.1, "spline_end": 0.15},
        {"name": "B", "spline_start": 0.16, "spline_end": 0.20},
        {"name": "C", "spline_start": 0.50, "spline_end": 0.55},
    ]
    chains = LineDefaults.infer_chains(corners, gap=0.05)
    assert len(chains) == 1
    assert chains[0]["corners"] == ["A", "B"]


def test_line_defaults_generic_profile():
    from line_defaults import LineDefaults

    line = LineDefaults.infer(None, "medium", {"downforce_class": "high"})
    assert line["profile"] == "late_apex"
    assert line["width_bias"] == "wide"

    gt = LineDefaults.infer(None, "low", {"line_bias": "v_line_exit"})
    assert gt["profile"] in ("v_line", "geometric")

