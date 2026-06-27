from session_state import SessionState


class _FakeIndexer(object):
    def corner_name(self, spline):
        if 0.02 <= spline <= 0.08:
            return "Turn 1"
        return ""

    def bin(self, spline):
        return int(spline * 360) % 360


class _FakePhases(object):
    def current_phase(self, corner, frame):
        return "exit" if corner else "straight"


def test_corner_exit_fires_once_per_transition():
    ss = SessionState()
    exits = []
    ss.on_corner_exit(lambda evt, frame: exits.append(evt.corner))
    idx = _FakeIndexer()
    phases = _FakePhases()

    class Frame(object):
        lap = 1
        t = 0.0
        in_pit = False
        spline = 0.05

    f = Frame()
    ss.update(f, idx, phases)
    assert exits == []

    f.spline = 0.10
    ss.update(f, idx, phases)
    assert exits == ["Turn 1"]

    for _ in range(20):
        ss.update(f, idx, phases)
    assert exits == ["Turn 1"]


def test_lap_type_classification():
    from session_state import LAP_FLYING, LAP_IN, LAP_OUT, SessionState

    assert SessionState.classify_lap(False, False, False, False) == LAP_FLYING
    assert SessionState.classify_lap(True, False, True, False) == LAP_OUT
    assert SessionState.classify_lap(False, True, False, False) == LAP_IN
    assert SessionState.classify_lap(False, False, False, True) == LAP_IN


def test_out_lap_detected_on_pit_exit():
    ss = SessionState()
    completed = []
    ss.on_lap_complete(lambda lap, frame, lap_type: completed.append(lap_type))
    idx = _FakeIndexer()
    phases = _FakePhases()

    class Frame(object):
        lap = 0
        t = 0.0
        in_pit = True
        spline = 0.5

    f = Frame()
    ss.update(f, idx, phases)
    f.in_pit = False
    ss.update(f, idx, phases)
    f.lap = 1
    ss.update(f, idx, phases)
    assert completed == ["out_lap"]
