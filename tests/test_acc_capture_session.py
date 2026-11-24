"""Capture session: staged replay copies (never the originals), trouble-spot plan, per-driver passes."""

import json

from external.query_tools import acc_capture_session as cs


def _bundle(tmp_path):
    b = tmp_path / "exports" / "lab_x"
    (b / "frames" / "You").mkdir(parents=True)
    frames = {"t": [i * 0.1 for i in range(1401)], "s_m": [i * 5.0 for i in range(1401)]}   # 50 m/s
    (b / "frames" / "You" / "lap_03.json").write_text(json.dumps(frames))
    (b / "manifest.json").write_text(json.dumps({"track_id": "spa", "drivers": [
        {"label": "You", "rpy_file": "ACC_me.rpy", "best_lap_index": 3, "replay_end_s": 900.0,
         "laps": [{"lap_index": 3, "lap_ms": 140000, "start_s": 500.0, "frames": "frames/You/lap_03.json"}]}]}))
    (b / "analysis.json").write_text(json.dumps({
        "windows": [{"corner": "T1", "index": 0, "s0_m": 200.0, "s1_m": 900.0, "apex_m": 400.0},
                    {"corner": "T5", "index": 4, "s0_m": 3000.0, "s1_m": 3600.0, "apex_m": 3200.0}],
        "corner_loss_best_vs_ref": [{"corner": "T5", "loss_s": 0.5}, {"corner": "T1", "loss_s": 0.2}],
        "drivers": {"You": {"corners": {"T1#0": {"best_lap": {"brake_on_m": 260.0, "turn_in_m": 330.0,
                                                               "vmin_m": 400.0, "full_throttle_m": 430.0}}}}}}))
    (b / "coaching.json").write_text(json.dumps({"fixes": [{"corner": "T1"}]}))
    return b


def test_plan_from_telemetry_ranks_and_merges(tmp_path, monkeypatch):
    _bundle(tmp_path)
    monkeypatch.setattr(cs, "EXPORTS", str(tmp_path / "exports"))
    spots = cs.trouble_spots("lab_x", 3)
    # T5 loses most but both kept (≥ 0.15 s); far apart (T1 ends 630 m, T5 starts ~3000 m) → not merged
    assert [s["corner"] for s in spots] == ["T1", "T5"]
    assert spots[0]["s0_m"] == 210.0 and spots[0]["s1_m"] == 580.0      # whole corner: brake−50 → full throttle+150
    m = json.loads((tmp_path / "exports" / "lab_x" / "manifest.json").read_text())
    passes = cs.driver_plan("lab_x", m["drivers"][0], spots, ["Drivable/Chase", "set1"])
    assert passes[0]["kind"] == "full" and passes[0]["camera"] == "Drivable/Dash"
    t1 = [p for p in passes if p.get("corner") == "T1"]
    assert [p["camera"] for p in t1] == ["Drivable/Chase", "set1"]
    assert t1[0]["window"] == [504.2, 511.6]                              # lap start + s/50 m/s
    # a small loss is ignored; neighbours closer than a separate pass costs are merged
    monkeypatch.setattr(cs, "PASS_OVERHEAD_S", 60.0)
    merged = cs.trouble_spots("lab_x", 3)
    assert len(merged) == 1 and merged[0]["corners"] == ["T1", "T5"] and merged[0]["corner"] == "T1 → T5"
    assert cs.trouble_spots("lab_x", 3, min_loss_s=0.3)[0]["corners"] == ["T5"]


def test_stage_copies_and_unstage_only_removes_copies(tmp_path, monkeypatch):
    _bundle(tmp_path)
    docs = tmp_path / "ACC"
    saved = docs / "Replay" / "Saved"
    saved.mkdir(parents=True)
    (docs / "Setups").mkdir()
    (saved / "ACC_me.rpy").write_bytes(b"replay")
    monkeypatch.setenv("VRE_ACC_DOCUMENTS", str(docs))
    monkeypatch.setattr(cs, "EXPORTS", str(tmp_path / "exports"))
    monkeypatch.setattr(cs, "STAGING", str(tmp_path / "staging.json"))
    out = cs.stage("lab_x")
    assert out[0]["staged"] == "00 VRE 1 - You - spa"
    assert (saved / "00 VRE 1 - You - spa.rpy").read_bytes() == b"replay"
    assert cs.staged_map() == {"00 VRE 1 - You - spa.rpy": "ACC_me.rpy"}
    assert cs.unstage() == 1
    assert sorted(p.name for p in saved.iterdir()) == ["ACC_me.rpy"]


def test_seek_is_relative_to_replay_start(monkeypatch):
    """ACC seeks in seconds from the replay start but reports absolute time (Erik's replay starts at 1714 s)."""
    from external.query_tools import acc_ue4ss

    sent = []
    rc = acc_ue4ss.ReplayControl.__new__(acc_ue4ss.ReplayControl)
    monkeypatch.setattr(rc, "status", lambda: {"start_s": 1714.0, "total_s": 727.0}, raising=False)
    monkeypatch.setattr(rc, "send", lambda verb, arg="", timeout=3.0: sent.append((verb, arg)) or {}, raising=False)
    rc.seek(2376.9)
    assert sent == [("seek", "662")]
