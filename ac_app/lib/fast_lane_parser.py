# ac_app/lib/fast_lane_parser.py
# Parse Assetto Corsa fast_lane.ai (version 7) — stdlib only.

import math
import struct


AI_POINT_SIZE = 20
AI_POINT_EXTRA_SIZE = 72


def _read_vec3(data, offset):
    return struct.unpack_from("<3f", data, offset)


def parse_fast_lane(path):
    """Return centerline points and left/right track limits from fast_lane.ai."""
    with open(path, "rb") as fh:
        data = fh.read()

    if len(data) < 16:
        raise ValueError("fast_lane.ai too small")

    version, point_count, _lap_time, _sample_count = struct.unpack("<4i", data[:16])
    if version != 7:
        raise ValueError("Unsupported fast_lane.ai version %d (need 7)" % version)

    offset = 16
    points = []
    for _ in range(point_count):
        x, y, z = _read_vec3(data, offset)
        length = struct.unpack_from("<f", data, offset + 12)[0]
        point_id = struct.unpack_from("<i", data, offset + 16)[0]
        points.append({
            "x": x, "y": y, "z": z,
            "length": length, "id": point_id,
        })
        offset += AI_POINT_SIZE

    if offset + 4 > len(data):
        raise ValueError("fast_lane.ai truncated before extra count")

    extra_count = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    extras = []
    for _ in range(extra_count):
        chunk = data[offset:offset + AI_POINT_EXTRA_SIZE]
        if len(chunk) < AI_POINT_EXTRA_SIZE:
            break
        vals = struct.unpack("<18f", chunk[:72])
        extras.append({
            "speed": vals[0],
            "side_left": vals[5],
            "side_right": vals[6],
            "forward": (vals[12], vals[13], vals[14]),
        })
        offset += AI_POINT_EXTRA_SIZE

    n = min(len(points), len(extras))
    centerline = []
    left_limit = []
    right_limit = []
    distance_m = []
    elevation_m = []
    ai_speed = []
    cumulative = 0.0

    for i in range(n):
        pt = points[i]
        ex = extras[i]
        cx, cy, cz = pt["x"], pt["y"], pt["z"]
        if i > 0:
            prev = points[i - 1]
            cumulative += math.sqrt(
                (cx - prev["x"]) ** 2 + (cy - prev["y"]) ** 2 + (cz - prev["z"]) ** 2,
            )
        fx, fy, fz = ex["forward"]
        flen = math.sqrt(fx * fx + fz * fz)
        if flen < 0.001:
            if i > 0:
                prev = points[i - 1]
                fx = cx - prev["x"]
                fz = cz - prev["z"]
                flen = math.sqrt(fx * fx + fz * fz) or 1.0
            else:
                fx, fz, flen = 1.0, 0.0, 1.0
        nx = -fz / flen
        nz = fx / flen
        sl = ex["side_left"]
        sr = ex["side_right"]
        centerline.append([round(cx, 2), round(cz, 2)])
        left_limit.append([round(cx + nx * sl, 2), round(cz + nz * sl, 2)])
        right_limit.append([round(cx - nx * sr, 2), round(cz - nz * sr, 2)])
        distance_m.append(cumulative)
        elevation_m.append(cy)
        ai_speed.append(ex["speed"])

    return {
        "version": version,
        "point_count": n,
        "centerline": centerline,
        "left_limit": left_limit,
        "right_limit": right_limit,
        "cumulative_length_m": round(cumulative, 1),
        "distance_m": distance_m,
        "elevation_m": elevation_m,
        "ai_speed": ai_speed,
    }
