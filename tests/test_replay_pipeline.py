import json
import os
import tempfile

from fast_lane_parser import parse_fast_lane
from telemetry_archive import TelemetryArchive
from telemetry_ingest import TelemetryIngest


def test_fast_lane_parser_monaco():
    ac = "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa"
    path = os.path.join(ac, "content", "tracks", "monaco_2020", "ai", "fast_lane.ai")
    if not os.path.isfile(path):
        return
    data = parse_fast_lane(path)
    assert data["point_count"] > 1000
    assert len(data["centerline"]) == data["point_count"]
    assert len(data["left_limit"]) == data["point_count"]
    cx, cz = data["centerline"][0]
    assert abs(cx) > 100


def test_resolve_session_by_name():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import resolve_session_path, list_sessions, default_sessions_root
    root = default_sessions_root()
    sessions = list_sessions(root)
    if not sessions:
        return
    name = sessions[0][0]
    path = resolve_session_path(name, root)
    assert os.path.isfile(os.path.join(path, "session.jsonl"))


def test_enrich_lap_samples_projects_coords():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import enrich_lap_samples
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    geom_path = os.path.join(repo, "ac_app", "data", "track_geometry", "monaco_2020.json")
    if not os.path.isfile(geom_path):
        return
    with open(geom_path) as fh:
        geometry = json.load(fh)
    samples = [{"spline": 0.05, "speed_kmh": 180}]
    out, projected = enrich_lap_samples(samples, geometry)
    assert projected
    assert out[0]["pos_x"] is not None
    assert out[0].get("pos_projected") is True


def test_normalize_lap_samples_monotonic():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import normalize_lap_samples
    samples = [
        {"spline": 0.10, "speed_kmh": 200},
        {"spline": 0.05, "speed_kmh": 180},
        {"spline": 0.05, "speed_kmh": 220},
        {"spline": 0.11, "speed_kmh": 210},
    ]
    out = normalize_lap_samples(samples)
    splines = [s["spline"] for s in out]
    assert splines == sorted(splines)
    assert all(splines[i] < splines[i + 1] or splines[i] == splines[i + 1] for i in range(len(splines) - 1))


def test_build_time_loss_analysis():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import build_time_loss_analysis, normalize_lap_samples
    from lap_time_analyzer import LapTimeAnalyzer
    from spline_indexer import SplineIndexer

    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    track_cfg_path = os.path.join(repo, "ac_app", "config", "tracks", "monaco_2020.json")
    if not os.path.isfile(track_cfg_path):
        return
    with open(track_cfg_path) as fh:
        track_cfg = json.load(fh)
    spline = SplineIndexer(track_cfg)
    lta = LapTimeAnalyzer(track_length_m=track_cfg.get("length_m", 3337), spline_indexer=spline)

    tmp = tempfile.mkdtemp()
    lap_path = os.path.join(tmp, "lap_01.json")
    samples = []
    for i in range(40):
        sp = i / 39.0
        samples.append({
            "spline": sp,
            "speed_kmh": 160 if i < 20 else 140,
            "corner": spline.corner_name(sp),
            "acc_g_lat": 1.0,
        })
    with open(lap_path, "w") as fh:
        json.dump({"lap": 1, "lap_time_ms": 90000, "samples": samples}, fh)

    for s in samples:
        lta.observe(spline.bin(s["spline"]), s["speed_kmh"], 0.05)
    lta.finish_lap(90000, lta._lap_bucket_speed)

    out = build_time_loss_analysis([lap_path], spline, lta, track_cfg.get("length_m", 3337), 90000, [], [])
    assert "laps" in out
    assert out["potential_gap_s"] >= 0


def test_glob_laps_ignores_decimated():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import glob_laps

    with tempfile.TemporaryDirectory() as tmp:
        laps_dir = os.path.join(tmp, "laps")
        os.makedirs(laps_dir)
        with open(os.path.join(laps_dir, "lap_04.json"), "w") as fh:
            json.dump({"lap": 4}, fh)
        with open(os.path.join(laps_dir, "lap_04_decimated.json"), "w") as fh:
            json.dump({"lap": 4, "decimated": True}, fh)
        paths = glob_laps(tmp)
        assert len(paths) == 1
        assert paths[0].endswith("lap_04.json")


def test_detect_export_channels_lat_coverage():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import detect_export_channels
    tmp = tempfile.mkdtemp()
    lap_path = os.path.join(tmp, "lap_01.json")
    with open(lap_path, "w") as fh:
        json.dump({"samples": [{"speed_kmh": 100}]}, fh)
    ch = detect_export_channels([lap_path], False, True)
    assert ch["acc_g_lat"] is False

    with open(lap_path, "w") as fh:
        json.dump({"samples": [{"speed_kmh": 100, "acc_g_lat": 1.2}] * 20}, fh)
    ch2 = detect_export_channels([lap_path], False, True)
    assert ch2["acc_g_lat"] is True


def test_export_tool_version_constant():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import EXPORT_TOOL_VERSION
    assert EXPORT_TOOL_VERSION


def test_compute_delta_track_length():
    """Delta integral scales with track length (same speeds, 2x length → 2x delta)."""
    spd = max(180 / 3.6, 1)
    ref_spd = max(200 / 3.6, 1)
    ds_frac = 0.5
    d1 = (1 / ref_spd - 1 / spd) * (ds_frac * 3337)
    d2 = (1 / ref_spd - 1 / spd) * (ds_frac * 5000)
    assert abs(d2 / d1 - 5000 / 3337) < 0.01


def test_build_session_plan():
    import sys
    qt = os.path.join(os.path.dirname(__file__), "..", "external", "query_tools")
    if qt not in sys.path:
        sys.path.insert(0, qt)
    from export_replay import build_session_plan
    tl = {
        "potential_gap_s": 0.43,
        "laps": {
            "3": {
                "lap_time_ms": 95000,
                "corners": [
                    {
                        "corner": "t7",
                        "corner_display": "Turn 7",
                        "loss_s": 0.31,
                        "primary_action": "Brake 5m later",
                        "spline_start": 0.42,
                        "spline_end": 0.48,
                    },
                    {
                        "corner": "t3",
                        "corner_display": "Turn 3",
                        "loss_s": 0.12,
                        "primary_action": "Wait for apex",
                        "spline_start": 0.1,
                        "spline_end": 0.15,
                    },
                ],
            },
            "2": {"lap_time_ms": 96000, "corners": []},
        },
    }
    plan = build_session_plan(tl)
    assert plan["potential_gap_s"] == 0.43
    assert len(plan["items"]) == 2
    assert plan["items"][0]["corner"] == "t7"
    assert plan["items"][0]["drill"] == "Brake 5m later"


def test_archive_coords():
    tmp = tempfile.mkdtemp()
    arch = TelemetryArchive(sessions_dir=tmp, subsample_every=1, async_writes=False)
    arch.start_session("monaco_2020", "test_car")
    frame = TelemetryIngest.frame_from_dict({
        "spline": 0.12, "speed_kmh": 180, "brake": 0.0, "throttle": 0.8,
        "steer": 0.05, "acc_g": (0, 1.2, 0), "yaw_rate": 0.1,
        "pos_x": -350.0, "pos_y": -13.0, "pos_z": 200.0, "heading": 1.57,
        "wheel_load": (3000, 3000, 2800, 2800),
        "susp_ratio": (0.2, 0.2, 0.3, 0.3),
    })
    arch.observe_frame(frame, corner="Turn 1", phase="exit")
    arch.flush_lap(1, 81000)
    lap_path = os.path.join(arch.session_dir, "laps", "lap_01.json")
    with open(lap_path) as fh:
        payload = json.load(fh)
    s = payload["samples"][0]
    assert s["pos_x"] == -350.0
    assert s["pos_z"] == 200.0
    assert "heading" in s
    assert "wheel_load" in s
