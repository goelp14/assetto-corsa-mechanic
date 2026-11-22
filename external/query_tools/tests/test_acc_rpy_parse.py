"""ACC .rpy metadata parser (vre_rpy package) + telemetry GO flag."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("vre_rpy")

REPO = Path(__file__).resolve().parents[3]
FIX = REPO / "external" / "query_tools" / "acc_rpy" / "fixtures"  # local only (gitignored)


@pytest.fixture
def spa_rpy():
    path = FIX / "ACC_261114-212425_O_ferrari_296_gt3_spa.rpy"
    if not path.is_file():
        pytest.skip("ACC rpy fixture not present locally")
    return path


def test_telemetry_go_flag():
    # arr_30 inputs are file-GO (MoTeC gold |r| >= 0.98 on every input channel).
    from vre_rpy.parse_rpy import RPY_TELEMETRY_GO

    assert RPY_TELEMETRY_GO is True


def test_filename_hints_296_spa(spa_rpy):
    from vre_rpy.parse_rpy import parse_rpy_metadata

    meta = parse_rpy_metadata(spa_rpy)
    assert meta["filename"]["car"] == "ferrari_296_gt3"
    assert meta["filename"]["track"] == "spa"
    assert meta["filename"]["session_type"] == "hotlap"
    assert meta["telemetry_go"] is True
    assert "Tomato" in meta["header"].get("driver_nicks", []) or meta["header"].get("steam_ids")


def test_rpy_to_session_metadata_only(spa_rpy, tmp_path):
    from vre_rpy.parse_rpy import rpy_to_session

    result = rpy_to_session(spa_rpy, sessions_root=tmp_path)
    session_dir = Path(result["session_dir"])
    assert (session_dir / "session.jsonl").is_file()
    assert (session_dir / "rpy_metadata.json").is_file()
    start = json.loads((session_dir / "session.jsonl").read_text().splitlines()[0])
    assert start["game"] == "acc"
    assert start["source"] == "acc_rpy"
    assert start["car"] == "ferrari_296_gt3"


def test_extract_lap_times_matches_motec_gold():
    """Spa gold .rpy current-lap timer stream vs same-stint MoTeC TIME resets."""
    from vre_rpy.parse_rpy import extract_lap_times_ms

    path = FIX / "ACC_261118-203124_O_ferrari_296_gt3_spa.rpy"
    if not path.is_file():
        pytest.skip("ACC Spa gold rpy fixture not present locally")
    laps = extract_lap_times_ms(path.read_bytes())
    # MoTeC TIME-reset flying laps from Spa-ferrari_296_gt3-10-2026.11.18-20.31.23.ld
    motec = [141395, 139880, 140125, 139550, 139723, 139970, 140113, 139077, 139200]
    flying = laps["flying_lap_times_ms"]
    assert laps["best_flying_lap_ms"] == 139072  # 2:19.072 (≤7ms from MoTeC 2:19.077)
    for m in motec:
        assert any(abs(m - r) <= 10 for r in flying), (m, flying)


def test_extract_lap_times_erik_hotlap():
    from vre_rpy.parse_rpy import extract_lap_times_ms

    # Uploaded AOR Spa quali replay (Erik) — path may be absent in CI
    candidates = [FIX / "ACCReplay_240418-223443_Q_Spa_ERIK.rpy"]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        pytest.skip("Erik Spa rpy not present")
    laps = extract_lap_times_ms(path.read_bytes())
    assert laps["best_flying_lap_ms"] is not None
    # User-reported set ~2:15; extractor recovers 2:15.425 / 2:15.595
    best = laps["best_flying_lap_ms"]
    assert 135000 <= best <= 136000, best
    assert any(135000 <= t <= 137500 for t in laps["flying_lap_times_ms"])
