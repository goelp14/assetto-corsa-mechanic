from volatility_buffer import VolatilityBuffer, WelfordState, PHASE_LEARNING, PHASE_BASELINE_READY


def test_welford_variance():
    w = WelfordState()
    for v in [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]:
        w.observe(v)
    assert w.n == 8
    assert abs(w.mean - 5.0) < 0.01
    assert w.variance() > 0


def test_volatility_phase_transition(thresholds):
    vb = VolatilityBuffer(num_buckets=4, thresholds=thresholds)
    target = int(thresholds.get("LEARNING_LAPS", 3))
    for lap in range(10):
        vb.reset_lap(lap)
        for _ in range(3):
            for b in range(4):
                vb.observe(b, 200.0 + b, 0.1, 0.0)
        vb.finish_lap()
    assert vb.clean_laps >= target
    assert vb.phase in (PHASE_BASELINE_READY, "TWEAKING")


def test_messy_lap_does_not_reset_clean_count(thresholds):
    vb = VolatilityBuffer(num_buckets=4, thresholds=thresholds)
    vb.reset_lap(1)
    for _ in range(3):
        for b in range(4):
            vb.observe(b, 200.0, 0.1, 0.0)
    vb.finish_lap()
    before = vb.clean_laps
    assert before >= 1

    vb.reset_lap(2)
    for _ in range(3):
        for b in range(4):
            vb.observe(b, 80.0 + b * 30.0, 0.7, 0.0)
    vb.finish_lap()
    assert vb.clean_laps >= before


def test_reset_lap_clears_bucket_variance(thresholds):
    vb = VolatilityBuffer(num_buckets=4, thresholds=thresholds)
    vb.reset_lap(1)
    for _ in range(5):
        vb.observe(0, 100.0, 0.5, 0.0)
    vb.finish_lap()
    assert vb._bins[0].speed.n == 5

    vb.reset_lap(2)
    assert vb._bins[0].speed.n == 0
    vb.observe(0, 200.0, 0.1, 0.0)
    vb.observe(0, 200.0, 0.1, 0.0)
    vb.observe(0, 200.0, 0.1, 0.0)
    vb.finish_lap()
    assert vb.clean_laps >= 1


def test_early_coaching_unlock(thresholds):
    vb = VolatilityBuffer(num_buckets=4, thresholds=thresholds)
    assert not vb.coaching_allowed()
    vb.total_laps = 2
    assert vb.coaching_allowed()
