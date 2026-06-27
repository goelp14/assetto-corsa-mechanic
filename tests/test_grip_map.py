
def test_grip_map_scores_kerb(thresholds):
    from grip_map import GripMapStore, ISSUE_KERB, ZONE_TRAP
    from telemetry_ingest import TelemetryIngest

    gm = GripMapStore(num_buckets=36, thresholds=thresholds)
    gm.track_id = "test"
    for lap in range(3):
        gm.reset_lap()
        for _ in range(5):
            f = TelemetryIngest.frame_from_dict({
                "acc_g": (0.5, 1.0, 0.2),
                "wheel_load": (3000, 3000, 2500, 2500),
                "slip_ratio": (0.12, 0.12, 0.15, 0.15),
                "susp_ratio": (0.9, 0.88, 0.3, 0.3),
            })

            class Bal(object):
                valid = True
                ay_efficiency = 0.85

            gm.observe(10, f, Bal())
        deltas = [0.0] * 36
        deltas[10] = 0.05
        gm.finish_lap(deltas, lap_was_clean=True)

    ref = gm.at_bucket(10)
    assert ref.samples >= 1
    assert ref.rating < 70
    assert ref.issue == ISSUE_KERB
    assert ref.zone in (ZONE_TRAP, "patchy")


def test_grip_map_pit_summary(thresholds):
    from grip_map import GripMapStore

    gm = GripMapStore(num_buckets=360, thresholds=thresholds)
    gm.track_id = "test2"
    for i in (100, 200, 250):
        gm._map[i].rating = 25
        gm._map[i].issue = "kerb"
        gm._map[i].zone = "trap"
        gm._map[i].samples = 5
        gm._map[i].cost_delta_s = 0.08
    summary = gm.pit_summary()
    assert "grip trap" in summary.lower() or "1)" in summary
    assert "kerb" in summary.lower() or "ease" in summary.lower()


def test_grip_map_segments(thresholds):
    from grip_map import GripMapStore, GRIP_SEGMENTS

    gm = GripMapStore(thresholds=thresholds)
    gm._map[0].rating = 90
    gm._map[0].samples = 3
    gm._map[0].zone = "solid"
    segs = gm.segment_ratings()
    assert len(segs) == GRIP_SEGMENTS
    assert segs[0]["learned"] is True
