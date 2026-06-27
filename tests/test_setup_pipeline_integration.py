import os
import shutil
import tempfile

from setup_catalog import SetupCatalog
from setup_detector import SetupDelta
from setup_writer import SetupWriter


def test_clone_and_apply_writes_auto_tweak(car_catalog):
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "generic_last.ini")
    tmpdir = tempfile.mkdtemp()
    track_dir = os.path.join(tmpdir, "monaco_2020")
    os.makedirs(track_dir)
    base = os.path.join(track_dir, "monaco 2026.ini")
    shutil.copy(fixture, base)
    try:
        writer = SetupWriter(car_catalog)
        out = os.path.join(track_dir, "Auto_Tweak.ini")
        writer.clone_base(base, out)
        writer.apply_deltas(
            out,
            [SetupDelta("WING_0", 2, "Monaco downforce", old_value=29, new_value=31)],
            lap=2, reason="bootstrap",
        )
        assert os.path.isfile(out)
        values = car_catalog.read_current_values(out)
        assert values["WING_0"] == 31
    finally:
        shutil.rmtree(tmpdir)
