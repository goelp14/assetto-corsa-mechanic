# ac_app/lib/acd_reader.py
# Python 3.3 compatible — read Assetto Corsa car data (data.acd or unpacked data/ folder).

import os
import struct

_NEW_FORMAT_MAGIC = -1111


def _encryption_key(car_folder_name):
    name = car_folder_name.lower().encode("utf-8")
    n = len(name)
    parts = [sum(bytearray(name))]
    b = bytearray(name)

    num = 0
    for i in range(0, n - 1, 2):
        num = num * b[i] - b[i + 1]
    parts.append(num)

    num = 0
    for i in range(1, n - 3, 3):
        num *= b[i]
        num = int(num / (b[i + 1] + 27))
        num -= 27 + b[i - 1]
    parts.append(num)

    num = 131
    for i in range(1, n):
        num -= b[i]
    parts.append(num)

    num = 66
    for i in range(1, n - 4, 4):
        num = num * (b[i] + 15) * (b[i - 1] + 15) + 22
    parts.append(num)

    num = 101
    for i in range(0, n - 2, 2):
        num -= b[i]
    parts.append(num)

    num = 171
    for i in range(0, n - 2, 2):
        num = num % b[i]
    parts.append(num)

    num = 171
    for i in range(n - 1):
        num = int(num / b[i]) + b[i + 1]
    parts.append(num)

    return bytearray("-".join(str(p % 256) for p in parts).encode("ascii"))


def read_acd(acd_path):
    """Return {filename: text} from a data.acd. Key derives from the car folder name."""
    key = _encryption_key(os.path.basename(os.path.dirname(os.path.abspath(acd_path))))
    klen = len(key)
    with open(acd_path, "rb") as fh:
        blob = fh.read()
    pos = 0
    if len(blob) >= 8 and struct.unpack("<i", blob[:4])[0] == _NEW_FORMAT_MAGIC:
        pos = 8
    out = {}
    while pos + 4 <= len(blob):
        name_len = struct.unpack("<i", blob[pos:pos + 4])[0]
        pos += 4
        name = blob[pos:pos + name_len].decode("utf-8")
        pos += name_len
        val_len = struct.unpack("<i", blob[pos:pos + 4])[0]
        pos += 4
        raw = bytearray(blob[pos:pos + val_len * 4:4])
        pos += val_len * 4
        for i in range(len(raw)):
            raw[i] = (raw[i] - key[i % klen]) % 256
        out[name] = raw.decode("utf-8", "replace")
    return out


def read_car_data(car_dir):
    """Prefer unpacked data/ folder (modders), fall back to data.acd."""
    data_dir = os.path.join(car_dir, "data")
    if os.path.isdir(data_dir):
        out = {}
        for name in os.listdir(data_dir):
            path = os.path.join(data_dir, name)
            if os.path.isfile(path):
                with open(path, "rb") as fh:
                    out[name] = fh.read().decode("utf-8", "replace")
        if out:
            return out
    acd = os.path.join(car_dir, "data.acd")
    if os.path.isfile(acd):
        return read_acd(acd)
    return {}


def parse_ini(text):
    """Minimal AC ini parser: strips ; and // comments, returns {section: {key: value}}."""
    sections = {}
    current = None
    for line in text.splitlines():
        line = line.split(";", 1)[0]
        if "//" in line:
            line = line.split("//", 1)[0]
        line = line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if current is not None and "=" in line:
            k, v = line.split("=", 1)
            sections[current][k.strip()] = v.strip()
    return sections


def parse_lut(text):
    """Parse an AC .lut (x|y per line) into sorted [(x, y)]."""
    points = []
    for line in text.splitlines():
        line = line.split(";", 1)[0].strip()
        if "|" not in line:
            continue
        x, y = line.split("|", 1)
        try:
            points.append((float(x), float(y)))
        except ValueError:
            continue
    points.sort()
    return points
