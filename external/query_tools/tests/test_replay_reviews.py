"""Lap Studio review grounding + launcher viewer API (no replay files needed)."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from external.query_tools.coach.reviews import SCHEMA, auto_breakdown, validate

ANALYSIS = {
    "labels": {"me": "Me", "ref": "Ref"},
    "length_m": 7000,
    "windows": [{"corner": "T1", "index": 0, "s0_m": 100.0, "s1_m": 500.0}],
    "corner_loss_best_vs_ref": [{"corner": "T1", "index": 0, "loss_s": 0.42}],
    "drivers": {
        "Me": {"corners": {"T1#0": {"best_lap": {"brake_full_m": 210.0, "brake_ramp_m": 18.0, "vmin_m": 300.0,
                                                   "vmin_kmh": 71.3, "full_throttle_m": 380.0}}}},
        "Ref": {"corners": {"T1#0": {"best_lap": {"brake_full_m": 190.0, "brake_ramp_m": 4.0, "vmin_m": 305.0,
                                                    "vmin_kmh": 76.8, "full_throttle_m": 350.0}}}},
    },
}
COACHING = {"fixes": [{"corner_key": "T1#0", "drill": "Hit peak brake within 5 m of the brake marker."}]}


def sources():
    return {"analysis": ANALYSIS, "coaching": COACHING}


def test_auto_breakdown_is_grounded():
    rv = auto_breakdown(ANALYSIS, COACHING)
    assert rv["schema"] == SCHEMA and rv["scenes"]
    assert validate(rv, sources(), track_length_m=7000) == []


def test_tampered_number_rejected():
    rv = auto_breakdown(ANALYSIS, COACHING)
    rv["scenes"][0]["narration"] = "T1: 0.91 s lost to Ref."
    errs = validate(rv, sources(), track_length_m=7000)
    assert any("0.91" in e for e in errs)


def test_bad_citation_and_window():
    rv = {"schema": SCHEMA, "scenes": [{"title": "x", "s0_m": 500, "s1_m": 100, "citations": ["analysis.nope"]}]}
    errs = validate(rv, sources())
    assert any("s0_m < s1_m" in e for e in errs) and any("citation not found" in e for e in errs)


@pytest.fixture()
def server(tmp_path):
    from external.query_tools import replay_launcher as rl

    b = tmp_path / "lab_x"
    (b / "reviews").mkdir(parents=True)
    (b / "manifest.json").write_text(json.dumps({"schema": "vre.replay_bundle.acc.v2", "session_id": "lab_x"}))
    (b / "analysis.json").write_text(json.dumps(ANALYSIS))
    (b / "coaching.json").write_text(json.dumps(COACHING))
    handler = type("H", (rl.ReplayHTTPRequestHandler,), {"exports_root": str(tmp_path)})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", b
    srv.shutdown()


def _post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_review_save_and_reject(server):
    base, b = server
    rv = auto_breakdown(ANALYSIS, COACHING)
    code, body = _post(f"{base}/api/bundles/lab_x/reviews/coach1", rv)
    assert code == 200 and (b / "reviews" / "coach1.json").is_file()
    rv["scenes"][0]["narration"] = "T1: 3.33 s lost."
    code, body = _post(f"{base}/api/bundles/lab_x/reviews/bad", rv)
    assert code == 422 and body["errors"]
    with urllib.request.urlopen(f"{base}/api/bundles/lab_x/reviews") as r:
        assert json.loads(r.read())["reviews"] == ["coach1"]


def test_commands_and_annotations(server):
    base, b = server
    assert _post(f"{base}/api/viewer/command", {"cmd": "seek", "args": {"s_m": 10}})[0] == 200
    assert _post(f"{base}/api/viewer/command", {"cmd": "nope"})[0] == 400
    code, body = _post(f"{base}/api/bundles/lab_x/annotations", {"annotations": [{"at_m": 200, "text": "hi"}]})
    assert code == 200 and json.loads((b / "annotations.json").read_text())["annotations"][0]["at_m"] == 200


def test_viewer_mcp_protocol():
    from external.query_tools import viewer_mcp as vm

    init = vm.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "vre-viewer"
    tools = vm.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"get_state", "focus_corner", "annotate", "create_review", "get_corner"} <= names
    bad = vm.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}})
    assert bad["error"]["code"] == -32602
    assert vm.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
