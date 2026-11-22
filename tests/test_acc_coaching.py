"""Habits → fixes → diagnosis on a small synthetic analysis (no replay files needed)."""

from external.query_tools.coach import physics
from external.query_tools.coach.acc_coach import persistent_habits, run
from external.query_tools.coach.distiller import distill
from external.query_tools.coach.habits import detect


def _corner(ramp, vmin, ti, ft, laps=6, rebrake=0.0, iqr=1.0):
    rows = [{"lap_index": i, "section_time_s": 16.0 + 0.1 * i, "brake_ramp_m": ramp, "vmin_kmh": vmin,
             "turn_in_kmh": ti, "full_throttle_m": ft, "rebrake_peak": rebrake} for i in range(laps)]
    cons = {k: {"median": v, "iqr": iqr if k == "vmin_kmh" else 1.0, "n": laps, "r_with_time": 0.1, "matters": False}
            for k, v in (("brake_ramp_m", ramp), ("vmin_kmh", vmin), ("turn_in_kmh", ti), ("full_throttle_m", ft))}
    return {"laps": rows, "consistency": cons, "best_lap": rows[0]}


def _analysis():
    me = {f"C{i}#{i}": _corner(30.0, 58.0, 90.0, 400.0, rebrake=0.4) for i in range(3)}
    ref = {f"C{i}#{i}": _corner(12.0, 63.0, 85.0, 388.0, laps=1) for i in range(3)}
    for k in ref:
        ref[k]["consistency"] = {}
    return {
        "labels": {"me": "You", "ref": "Ref"}, "track": "synthetic",
        "drivers": {"You": {"corners": me, "lap_ms": [140000, 141000]}, "Ref": {"corners": ref, "lap_ms": [136000]}},
        "corner_loss_best_vs_ref": [{"corner": f"C{i}", "index": i, "loss_s": 0.3 + 0.1 * i} for i in range(3)],
        "car_state": {"You": {"mass_kg": 1380, "front_share_under_braking": 0.63}},
        "pack": {"corners": [{"display_name": "C2", "notes": {"cues": ["the 100 m board"]}}]},
    }


def test_habits_detected_with_pace_impact():
    h = {x["id"]: x for x in detect(_analysis())["habits"]}
    assert h["slow_brake_build"]["polarity"] == "weakness" and h["slow_brake_build"]["repeats"] == 3
    assert abs(h["slow_brake_build"]["pace_impact_s"] - 1.2) < 1e-6
    assert "hero_entry" in h and "late_full_throttle" in h and "second_brake_application" in h


def test_distill_caps_fixes_and_cites():
    a = _analysis()
    c = distill(a, detect(a))
    assert 1 <= len(c["fixes"]) <= 2
    groups = [f["group"] for f in c["fixes"]]
    assert len(groups) == len(set(groups))
    f = next(f for f in c["fixes"] if f["mental_model"] == "build_brake_smoothly")
    assert "12 m" in f["drill"] and "30 m" in f["drill"]
    assert f["citations"][0].startswith("analysis.drivers.You.corners.")
    assert f["cues"] == ["the 100 m board"]  # cue from track notes at the worst corner


def test_braking_balance_uses_even_slip_not_load():
    fp = {"estimated": {"brake_slip_front_share": {"value": 0.515, "spread": 0.01}}}
    assert physics.braking_balance_check({}, fp)["lever"] is None       # balanced
    fp["estimated"]["brake_slip_front_share"]["value"] = 0.62
    r = physics.braking_balance_check({}, fp)
    assert r["direction"] == "less front bias"


def test_run_and_persistent_habits(tmp_path, monkeypatch):
    monkeypatch.setenv("VRE_DRIVER_PROFILE", str(tmp_path / "p.json"))
    a = _analysis()
    out = run(a, update_profile=True)
    a2 = dict(a, track="other_track")
    out = run(a2, update_profile=True)
    ids = {p["id"] for p in out["persistent_habits"]}
    assert "slow_brake_build" in ids
    assert out["diagnosis"]["corners"][0]["cause"] == "technique"


def test_landmark_phrasing():
    from external.query_tools.coach.landmarks import car_lengths, compare_event

    corner = {"display_name": "T1", "start_m": 300.0, "apex_m": 380.0, "end_m": 450.0}
    r = compare_event("brake_on_m", 266.0, 268.3, corner, 4.6, "you", "Ref", [corner])
    assert "114 m before the T1 apex" in r["text"] and "half a car length later" in r["text"]
    curated = dict(corner, notes={"boards_m": {"100": 266.0}})
    r = compare_event("brake_on_m", 266.0, 266.5, curated, 4.6, "you", "Ref", [curated])
    assert r["text"].startswith("You start braking at the 100 m board") and "same place" in r["text"]
    assert car_lengths(13.8, 4.6) == "3 car lengths"
