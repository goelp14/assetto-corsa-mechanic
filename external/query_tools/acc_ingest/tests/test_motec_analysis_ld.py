"""Smoke tests for Motec analysis .ld writer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / (
    "Spa-ferrari_296_gt3-10-2026.11.18-20.31.23.ld"
)


@pytest.mark.skipif(not FIXTURE.is_file(), reason="Spa Motec fixture missing")
def test_write_analysis_ld_roundtrip(tmp_path):
    pytest.importorskip("ldparser")
    from motec_analysis_ld import write_analysis_ld, load_ld_channels

    out = tmp_path / "vre_analysis_spa.ld"
    meta = write_analysis_ld(str(FIXTURE), str(out))
    assert out.is_file()
    assert out.stat().st_size > 1000
    assert Path(meta["meta_json"]).is_file()
    assert "VRE_COAST" in meta["vre_channels"]
    assert meta["evidence"]["laps"] == "GO"
    assert meta["best_lap_ms"] is not None
    # best Tomato lap in this file is 139077 (2:19.077)
    assert meta["best_lap_ms"] == 139077

    # Re-open and confirm VRE channel present
    ch = load_ld_channels(str(out))
    assert "VRE_COAST" in ch
    assert "SPEED" in ch
    assert "EN_W" in ch  # pass-through preserved
    assert len(ch["VRE_COAST"].data) == len(ch["SPEED"].data)


@pytest.mark.skipif(not FIXTURE.is_file(), reason="Spa Motec fixture missing")
def test_load_ld_channels_native_rates():
    pytest.importorskip("ldparser")
    from motec_analysis_ld import load_ld_channels

    ch = load_ld_channels(str(FIXTURE))
    assert ch["SPEED"].freq == 60
    assert ch["SUS_TRAVEL_LF"].freq == 200
    assert ch["TIME"].freq == 50
    # native lengths must not be truncated to shortest
    assert len(ch["SUS_TRAVEL_LF"].data) > len(ch["SPEED"].data)
