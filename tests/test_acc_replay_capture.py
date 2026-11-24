"""Replay video sync: broadcasting samples → per-lap lap-time ↔ video-time tables → bundle laps."""

import struct

from external.query_tools import acc_broadcast as ab
from external.query_tools.acc_replay_capture import lap_tables, match_laps


def _samples(lap_ms=(138525, 139235), start_lap_t=100.0, pause=None):
    """Replay at 1×: recording starts 100 s into lap 3; optional pause (video runs, lap clock frozen)."""
    out, v, laps, cur = [], 0.0, 3, start_lap_t
    durations = list(lap_ms)
    lap_len = 140.0
    while v < 360.0:
        if pause and pause[0] <= v < pause[1]:
            pass
        else:
            cur += 0.05
        if cur * 1000 >= (durations[0] if laps == 4 else durations[1] if laps == 5 else lap_len * 1000):
            done = durations[0] if laps == 4 else durations[1] if laps == 5 else int(lap_len * 1000)
            cur -= done / 1000.0
            laps += 1
            last = done
        else:
            last = 0 if laps == 3 else last
        out.append({"v": v, "car": 0, "laps": laps, "cur_ms": int(cur * 1000), "last_ms": last})
        v += 0.05
    return out


def test_lap_tables_map_lap_time_to_video_time():
    tables = {t["laps"]: t for t in lap_tables(_samples())}
    lap4 = tables[4]
    assert lap4["complete"] and lap4["lap_ms"] == 138525
    m = lap4["map"]
    assert m[0][0] == 0.0 and abs(m[0][1] - 40.0) < 0.06          # lap 4 starts 40 s into the video
    assert abs(m[-1][0] - 138.525) < 1e-6 and abs(m[-1][1] - 178.525) < 0.06
    assert len(m) <= 4                                              # 1× playback thins to a line
    assert not tables[3]["complete"] and tables[3]["lap_ms"] == 140000


def test_pause_keeps_table_monotonic():
    tables = {t["laps"]: t for t in lap_tables(_samples(pause=(80.0, 90.0)))}
    m = tables[4]["map"]
    assert all(b[0] > a[0] and b[1] >= a[1] for a, b in zip(m, m[1:]))
    # lap time 50 s is reached 10 s later in the video than without the pause
    def at(t):
        for a, b in zip(m, m[1:]):
            if a[0] <= t <= b[0]:
                return a[1] + (t - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
    assert abs(at(50.0) - 100.0) < 0.1


def test_match_laps_identifies_driver_and_lap():
    tables = lap_tables(_samples())
    manifest = {"drivers": [
        {"label": "Erik", "laps": [{"lap_index": 1, "lap_ms": 135425}]},
        {"label": "You", "laps": [{"lap_index": 17, "lap_ms": 138525}, {"lap_index": 2, "lap_ms": 139235}]},
    ]}
    assert match_laps(tables, manifest) == "You"
    by = {t["laps"]: t.get("lap_index") for t in tables}
    assert by[4] == 17 and by[5] == 2


def _w(s):
    b = s.encode()
    return struct.pack("<H", len(b)) + b


def _lapinfo(ms):
    return struct.pack("<iHHB", ms, 0, 0, 0) + bytes([0, 1, 0, 0])


def test_parse_broadcast_messages():
    rt = (bytes([ab.R_REALTIME]) + struct.pack("<HHBBff", 0, 0, 0, 2, 0.0, 0.0) + struct.pack("<i", 3)
          + _w("set1") + _w("CameraTV3a") + _w("Replay") + bytes([1]) + struct.pack("<ff", 61500.0, 1000.0))
    r = ab.parse_realtime(rt)
    assert r.replay and r.replay_time_s == 61.5 and r.focused_car == 3 and r.camera == "CameraTV3a"
    car = (bytes([ab.R_CAR]) + struct.pack("<HHBB", 3, 0, 1, 6) + struct.pack("<fff", 1.0, 2.0, 0.5)
           + bytes([1]) + struct.pack("<HHHHfHi", 210, 1, 1, 1, 0.42, 7, 0)
           + _lapinfo(138525) + _lapinfo(139000) + _lapinfo(61234))
    c = ab.parse_car(car)
    assert (c.car_index, c.gear, c.kmh, c.laps) == (3, 4, 210, 7)
    assert c.current.ms == 61234 and c.last.ms == 139000 and abs(c.spline - 0.42) < 1e-6


def test_launcher_streams_video_with_ranges(tmp_path):
    import json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    from external.query_tools import replay_launcher as rl

    b = tmp_path / "lab_x"
    b.mkdir()
    (b / "manifest.json").write_text(json.dumps({"drivers": []}))
    video = tmp_path / "rec.mp4"
    video.write_bytes(bytes(range(256)) * 40)
    (b / "videos.json").write_text(json.dumps({"videos": [{"id": "v1", "driver": "You", "file": str(video),
                                                             "offset_s": 0, "laps": []}]}))
    handler = type("H", (rl.ReplayHTTPRequestHandler,), {"exports_root": str(tmp_path)})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    try:
        lst = json.load(urllib.request.urlopen(base + "/api/bundles/lab_x/videos"))
        assert lst["videos"][0]["available"] and "file" not in lst["videos"][0]
        req = urllib.request.Request(base + "/api/bundles/lab_x/video/v1", headers={"Range": "bytes=256-511"})
        r = urllib.request.urlopen(req)
        assert r.status == 206 and r.headers["Content-Range"] == "bytes 256-511/10240" and r.read() == bytes(range(256))
        req = urllib.request.Request(base + "/api/bundles/lab_x/videos/v1", data=b'{"offset_s": 0.0167}',
                                     headers={"Content-Type": "application/json"}, method="POST")
        assert json.load(urllib.request.urlopen(req))["offset_s"] == 0.017
        assert json.load(urllib.request.urlopen(base + "/api/bundles/lab_x/capture"))["state"] == "idle"
    finally:
        srv.shutdown()


def test_saved_replay_sync_uses_time_remaining():
    """ACC freezes 'replay time' in saved replays; 'remaining' counts down and ends with the decoder clock."""
    import math

    from external.query_tools.acc_replay_capture import replay_lap_tables

    end = 2591.22
    laps = [{"lap_index": 4, "lap_ms": 139587, "start_s": 478.147}, {"lap_index": 5, "lap_ms": 139755, "start_s": 617.742}]
    # recording starts at decoder 470 s; paused 10 s at video 60-70 s
    samples, v, dec = [], 0.0, 470.0
    while dec < 700.0:
        samples.append({"v": round(v, 3), "remaining": float(round(end - dec))})   # ACC rounds to whole seconds
        v += 0.05
        if not (60.0 <= v < 70.0):
            dec += 0.05
    tabs = {t["lap_index"]: t for t in replay_lap_tables(samples, laps, end)}
    assert tabs[4]["complete"] and not tabs[5]["complete"]
    m = tabs[4]["map"]
    assert abs(m[0][1] - (8.147 + m[0][0])) < 0.06              # lap 4 starts ~8.15 s into the video
    def at(t):
        for a, b in zip(m, m[1:]):
            if a[0] <= t <= b[0]:
                return a[1] + (t - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
    assert abs(at(100.0) - (8.147 + 100.0 + 10.0)) < 0.1          # after the pause the video is 10 s later
