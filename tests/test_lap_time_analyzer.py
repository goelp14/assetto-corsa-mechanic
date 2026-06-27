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
