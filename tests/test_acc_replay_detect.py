"""Which replay ACC loaded: UE log load line + .rpy last-access time + bundle rpy_file."""

import datetime as dt
import json
import os

from external.query_tools import acc_replay_detect as det

LOG = """[2026.11.23-23.46.31:660][423]LogKsOnlineServices: Display: UOnlineServices::RequestHotlapData(trackname=spa, take=6, skip=0)
[2026.11.23-23.46.31:661][423]LogKsPhysics: replay loading, playercarModel 32
[2026.11.23-23.46.31:672][423]LogKsReplay: Replay loaded successfully
[2026.11.23-23.46.31:674][423]LogKsUI: Create WDG_ReplayInGame_C_2147481472
"""


def test_detects_loaded_replay_and_bundle(tmp_path, monkeypatch):
    docs = tmp_path / "ACC"
    saved = docs / "Replay" / "Saved"
    saved.mkdir(parents=True)
    (docs / "Setups").mkdir()
    load = dt.datetime(2026, 11, 23, 23, 46, 31, 672000, tzinfo=dt.timezone.utc).timestamp()
    for name, at in (("ACC_a_spa.rpy", load - 5.0), ("ACC_b_spa.rpy", load + 0.0), ("ACC_c_imola.rpy", load - 5.0)):
        p = saved / name
        p.write_bytes(b"x")
        os.utime(p, (at, at))
    log = tmp_path / "AC2.log"
    log.write_text(LOG)
    exports = tmp_path / "exports" / "lab_x"
    exports.mkdir(parents=True)
    (exports / "manifest.json").write_text(json.dumps({"drivers": [
        {"label": "You", "rpy_file": "ACC_b_spa.rpy", "best_lap_index": 17}]}))
    monkeypatch.setenv("VRE_ACC_DOCUMENTS", str(docs))
    monkeypatch.setattr(det, "ue_log_path", lambda: str(log))
    monkeypatch.setattr(det, "EXPORTS", str(tmp_path / "exports"))
    out = det.detect()
    assert out["in_replay"] and out["file"] == "ACC_b_spa.rpy"
    assert (out["bundle"], out["driver"], out["best_lap_index"]) == ("lab_x", "You", 17)
    assert out["track"] == "spa" and out["car_model"] == 32
    log.write_text(LOG + "[2026.11.23-23.50.00:000][900]LogKsUI: Remove WDG_ReplayInGame_C_2147481472\n")
    assert det.detect()["in_replay"] is False
