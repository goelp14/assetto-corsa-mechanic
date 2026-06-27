# ac_app/lib/setup_writer.py
# Python 3.3 compatible — stdlib only

import os
import time

try:
    from ac_paths import enumerate_car_setups_roots, resolve_car_setups_root
except ImportError:
    from .ac_paths import enumerate_car_setups_roots, resolve_car_setups_root


class SetupWriter(object):
    """Clone base ini, merge deltas, write Auto_Tweak.ini."""

    def __init__(self, setup_catalog, car_id="rss_formula_hybrid_x_2026"):
        self.catalog = setup_catalog
        self.car_id = car_id
        self._active_setups_root = None

    def _documents_setups_dir(self):
        if self._active_setups_root and os.path.isdir(self._active_setups_root):
            return self._active_setups_root
        return resolve_car_setups_root(self.car_id)

    def resolve_output_path(self, track_folder):
        return os.path.join(self._documents_setups_dir(), track_folder, "Auto_Tweak.ini")

    @staticmethod
    def read_ini_lines(path):
        with open(path, "r") as fh:
            return fh.readlines()

    @staticmethod
    def write_ini_lines(path, lines):
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            try:
                os.makedirs(parent)
            except OSError:
                if not os.path.isdir(parent):
                    raise
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            fh.writelines(lines)
        try:
            if os.path.isfile(path):
                os.remove(path)
            os.rename(tmp, path)
        except OSError:
            with open(path, "w") as fh:
                fh.writelines(lines)
            if os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    def clone_base(self, base_ini_path, output_path):
        lines = self.read_ini_lines(base_ini_path)
        self.write_ini_lines(output_path, lines)
        return output_path

    def apply_deltas(self, ini_path, deltas, lap=0, reason=""):
        lines = self.read_ini_lines(ini_path)
        sections = {}
        order = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                sec = stripped[1:-1]
                sections[sec] = i
                order.append(sec)

        value_indices = {}
        for sec, start_idx in sections.items():
            for j in range(start_idx + 1, len(lines)):
                if lines[j].strip().startswith("["):
                    break
                if lines[j].strip().upper().startswith("VALUE="):
                    value_indices[sec] = j

        for delta in deltas:
            sec = delta.section
            if sec not in value_indices:
                block = ["\n", "[%s]\n" % sec, "VALUE=%s\n" % delta.new_value]
                lines.extend(block)
                continue
            lines[value_indices[sec]] = "VALUE=%s\n" % (
                int(delta.new_value) if float(delta.new_value) == int(delta.new_value)
                else delta.new_value
            )

        desc = "VRE tweak lap %d: %s" % (lap, reason or "auto")
        if "ABOUT" in value_indices:
            pass
        elif "ABOUT" in sections:
            idx = sections["ABOUT"]
            for j in range(idx + 1, len(lines)):
                if lines[j].strip().startswith("["):
                    lines.insert(j, "DESCRIPTION=%s\n" % desc)
                    break
                if lines[j].strip().upper().startswith("DESCRIPTION="):
                    lines[j] = "DESCRIPTION=%s\n" % desc
                    break

        self.write_ini_lines(ini_path, lines)
        return ini_path

    def write_auto_tweak(self, base_ini_path, track_folder, deltas, lap=0, reason=""):
        out = self.resolve_output_path(track_folder)
        if not os.path.isfile(out):
            self.clone_base(base_ini_path, out)
        return self.apply_deltas(out, deltas, lap=lap, reason=reason)

    def locate_track_folder(self, track_folder):
        """Return (setups_root, folder_path) for this track across all roots."""
        for root in enumerate_car_setups_roots(self.car_id):
            folder = os.path.join(root, track_folder)
            if os.path.isdir(folder):
                self._active_setups_root = root
                return root, folder
            generic = os.path.join(root, "generic")
            if os.path.isdir(generic):
                self._active_setups_root = root
                return root, generic
        return None, None

    def _list_setup_inis(self, folder, include_last=False):
        try:
            names = os.listdir(folder)
        except OSError:
            return []
        out = []
        for name in names:
            low = name.lower()
            if low == "auto_tweak.ini":
                continue
            if not include_last and low == "last.ini":
                continue
            if low.endswith(".ini"):
                out.append(name)
        return out

    def find_base_ini(self, track_folder):
        """Named setup file to clone from — not AC's volatile last.ini snapshot."""
        root, folder = self.locate_track_folder(track_folder)
        if not folder:
            return None

        env_name = os.environ.get("VRE_BASE_SETUP", "").strip()
        if env_name:
            candidate = os.path.join(folder, env_name)
            if os.path.isfile(candidate):
                return candidate

        names = self._list_setup_inis(folder)
        best = None
        best_mtime = -1.0
        for name in names:
            path = os.path.join(folder, name)
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if mtime > best_mtime:
                best_mtime = mtime
                best = path
        if best:
            return best

        last_track = os.path.join(folder, "last.ini")
        if os.path.isfile(last_track):
            return last_track

        if root:
            last_generic = os.path.join(root, "generic", "last.ini")
            if os.path.isfile(last_generic):
                return last_generic
        return None

    def ensure_auto_tweak(self, track_folder):
        """Clone base setup to Auto_Tweak.ini if needed. Returns (path, error)."""
        out_ini = self.resolve_output_path(track_folder)
        if os.path.isfile(out_ini):
            return out_ini, ""
        base_ini = self.find_base_ini(track_folder)
        if not base_ini:
            return "", "no_base_ini"
        try:
            self.clone_base(base_ini, out_ini)
        except (IOError, OSError) as exc:
            return "", "clone_failed:%s" % exc
        if os.path.isfile(out_ini):
            return out_ini, ""
        return "", "clone_missing_after_write"
