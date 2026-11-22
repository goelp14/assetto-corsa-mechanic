from lap_time_analyzer import LapTimeAnalyzer


def test_lap_delta_scales_with_dt(monza_indexer):
    lta = LapTimeAnalyzer(num_buckets=10, track_length_m=1000.0, spline_indexer=monza_indexer)
    speeds = [200.0] * 10
    lta.finish_lap(90000, speeds)
    lta.reset_lap(1)
    for _ in range(100):
        lta.observe(0, 180.0, 0.016)
    delta = lta.current_lap_delta_s()
    assert abs(delta) < 5.0


def test_theoretical_best(monza_indexer):
    lta = LapTimeAnalyzer(num_buckets=10, track_length_m=1000.0, spline_indexer=monza_indexer)
    speeds = [200.0] * 10
    lta.finish_lap(90000, speeds)
    speeds2 = [180.0] * 10
    lta.finish_lap(95000, speeds2)
    tb = lta.theoretical_best_ms()
    assert tb > 0


def test_theoretical_best_sparse_logs_is_sane():
    """ACC MoTeC-ingested laps are ~2.7 Hz: most buckets empty. Old stitching gave 0.9 s 'best'."""
    from lap_time_analyzer import LapTimeAnalyzer

    lta = LapTimeAnalyzer(num_buckets=360, track_length_m=7000.0)
    lap_times = [140000, 141000, 139500]
    for k, lap_ms in enumerate(lap_times):
        lta.reset_lap(k + 1)
        n = 380  # samples per lap, evenly spaced in time
        dt = lap_ms / 1000.0 / n
        for i in range(n):
            b = int(i / n * 360)
            if i % 3 == 0:  # sparse: only a third of the samples land
                lta.observe(b, 180.0 + 20 * ((b + k) % 7), dt)
        lta.finish_lap(lap_ms, lta._lap_bucket_speed)
    theo = lta.theoretical_best_ms()
    assert 0.9 * min(lap_times) <= theo <= min(lap_times)
    assert lta.potential_gap_s(140000) >= 0.0


def test_theoretical_best_withheld_when_buckets_missing():
    from lap_time_analyzer import LapTimeAnalyzer

    lta = LapTimeAnalyzer(num_buckets=100, track_length_m=1000.0)
    lta.reset_lap(1)
    lta.observe(5, 100.0, 0.1)  # one sample: far too little coverage
    lta.finish_lap(60000, lta._lap_bucket_speed)
    assert lta.theoretical_best_ms() == 0
