# ac_app/lib/voice_file_writer.py
# Python 3.3 compatible — stdlib only

import os
import time


class VoiceFileWriter(object):
    """Append SEQ|timestamp|message lines for external TTS daemon."""

    def __init__(self, file_path):
        self.file_path = file_path
        self._seq = 0
        self._load_seq()

    def _load_seq(self):
        if not os.path.isfile(self.file_path):
            return
        try:
            with open(self.file_path, "r") as fh:
                for line in fh:
                    parts = line.strip().split("|", 2)
                    if parts and parts[0].isdigit():
                        self._seq = max(self._seq, int(parts[0]))
        except (IOError, OSError):
            pass

    def append(self, message):
        self._seq += 1
        parent = os.path.dirname(self.file_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        line = "%d|%d|%s\n" % (self._seq, int(time.time()), message)
        with open(self.file_path, "a") as fh:
            fh.write(line)
        return self._seq

    def read_pending(self):
        if not os.path.isfile(self.file_path):
            return []
        lines = []
        with open(self.file_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    lines.append(line)
        return lines

    def truncate_processed(self, through_seq):
        pending = []
        for line in self.read_pending():
            parts = line.split("|", 2)
            if parts and parts[0].isdigit() and int(parts[0]) > through_seq:
                pending.append(line)
        parent = os.path.dirname(self.file_path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(self.file_path, "w") as fh:
            for line in pending:
                fh.write(line + "\n")
