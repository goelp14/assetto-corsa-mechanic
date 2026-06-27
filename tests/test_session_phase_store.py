import os
import tempfile

from session_phase_store import SessionPhaseStore, PHASE_LEARNING, PHASE_TWEAKING


def test_phase_persists_and_infers_from_baseline():
    tmp = tempfile.mkdtemp()
    store = SessionPhaseStore(data_dir=tmp)
    store.save("monaco_2020", PHASE_TWEAKING, 3, 10)
    loaded = store.load("monaco_2020")
    assert loaded["phase"] == PHASE_TWEAKING
    assert loaded["clean_laps"] == 3

    inferred = store.load("spa", baseline_sample_total=600)
    assert inferred["phase"] == PHASE_TWEAKING
    assert os.path.isfile(os.path.join(tmp, "spa.json")) is False
