from track_profile import TrackProfileStore


def test_resolve_monaco():
    store = TrackProfileStore()
    prof = store.resolve("monaco_2020")
    assert prof.profile_id == "monaco_2020"
    assert prof.character["downforce_demand"] == "very_high"
    assert len(prof.bootstrap_hints) >= 2


def test_bootstrap_triggers_when_stuck():
    store = TrackProfileStore()
    prof = store.resolve("monaco_2020")
    assert prof.should_bootstrap(2, 0) is True
    assert prof.should_bootstrap(2, 1) is True
    hint = prof.next_bootstrap_hint()
    assert hint["section"] == "WING_0"
    assert prof.allows_setup_during_learning() is True


def test_monza_low_downforce():
    store = TrackProfileStore()
    prof = store.resolve("monza")
    assert prof.character["downforce_demand"] == "low"
    assert prof.bootstrap_hints[0]["steps"] < 0
