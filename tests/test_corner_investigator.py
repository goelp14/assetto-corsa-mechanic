import math

from corner_investigator import CornerInvestigator


def _ref_exit(min_spd=100, max_thr=0.2):
    return {
        "phases": {
            "exit": {
                "samples": 10,
                "min_speed_kmh": min_spd,
                "max_throttle": max_thr,
                "peak_ay_g": 0.5,
                "steer_corrections": 0,
                "mean_brake": 0.05,
            },
        },
    }


def test_exit_throttle_under_load(thresholds):
    inv = CornerInvestigator(thresholds)
    summary = {
        "phases": {
            "exit": {
                "samples": 10,
                "min_speed_kmh": 116,
                "max_throttle": 1.0,
                "peak_ay_g": 0.91,
                "steer_corrections": 1,
                "mean_brake": 0.1,
            },
        },
    }
    hit = inv.investigate(summary, _ref_exit(), corner="Sainte Devote")
    assert hit is not None
    assert hit.root_cause_id == "exit_throttle_under_load"
    assert hit.template_key == "root_exit_throttle"
    assert "116" in hit.evidence["evidence_point"]


def test_steer_fight(thresholds):
    inv = CornerInvestigator(thresholds)
    summary = {
        "phases": {
            "exit": {
                "samples": 12,
                "min_speed_kmh": 54,
                "max_throttle": 0.4,
                "peak_ay_g": 1.6,
                "steer_corrections": 8,
                "mean_brake": 0.05,
            },
        },
    }
    hit = inv.investigate(summary, _ref_exit(min_spd=101), corner="Anthony Noghes")
    assert hit is not None
    assert hit.root_cause_id == "steer_fight"


def test_scrubbed_min_speed(thresholds):
    inv = CornerInvestigator(thresholds)
    summary = {
        "phases": {
            "exit": {
                "samples": 10,
                "min_speed_kmh": 67,
                "max_throttle": 0.1,
                "peak_ay_g": 1.1,
                "steer_corrections": 1,
                "mean_brake": 0.2,
            },
        },
    }
    hit = inv.investigate(summary, _ref_exit(min_spd=76), corner="Swimming Pool")
    assert hit is not None
    assert hit.root_cause_id == "scrubbed_min_speed"


def test_loss_of_control_spin(thresholds):
    inv = CornerInvestigator(thresholds)

    class _Yaw(object):
        gate = "LOSS_OF_CONTROL"

    summary = {
        "phases": {
            "exit": {
                "samples": 8,
                "min_speed_kmh": 78,
                "max_throttle": 1.0,
                "peak_ay_g": 0.91,
                "peak_beta_deg": 45.0,
                "steer_corrections": 0,
            },
        },
    }
    hit = inv.investigate(
        summary, _ref_exit(), corner="Sainte Devote", yaw_gate=_Yaw(),
    )
    assert hit is not None
    assert hit.template_key == "root_loss_of_control"
    assert "throttle" in hit.evidence["evidence_point"].lower()


def test_throttle_overlap_casino(thresholds):
    inv = CornerInvestigator(thresholds)
    summary = {
        "phases": {
            "exit": {
                "samples": 10,
                "min_speed_kmh": 230,
                "max_throttle": 1.0,
                "peak_ay_g": 2.4,
                "steer_corrections": 2,
                "mean_brake": 0.05,
            },
        },
    }
    ref = {
        "phases": {
            "exit": {
                "samples": 10,
                "max_throttle": 0.6,
                "peak_ay_g": 2.1,
            },
        },
    }
    hit = inv.investigate(summary, ref, corner="Casino")
    assert hit is not None
    assert hit.root_cause_id == "throttle_under_lateral"
