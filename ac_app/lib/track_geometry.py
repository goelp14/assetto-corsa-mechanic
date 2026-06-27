# ac_app/lib/track_geometry.py
# Build track_geometry.json from fast_lane.ai + VRE track config.

import json
import os


def _surface_polygon(left_limit, right_limit):
    poly = list(left_limit)
    for pt in reversed(right_limit):
        poly.append(pt)
    return poly


def _spline_map(centerline, track_length_m):
    n = len(centerline)
    if n < 2:
        return []
    out = []
    cumulative = 0.0
    for i, (x, z) in enumerate(centerline):
        if i > 0:
            px, pz = centerline[i - 1]
            cumulative += ((x - px) ** 2 + (z - pz) ** 2) ** 0.5
        spline = cumulative / max(track_length_m, 1.0)
        out.append({
            "spline": round(min(1.0, spline), 5),
            "distance_m": round(cumulative, 1),
            "x": x,
            "z": z,
        })
    return out


def _corner_zones(corners, spline_map, track_length_m):
    zones = []
    for corner in corners:
        s0 = float(corner.get("spline_start", 0.0))
        s1 = float(corner.get("spline_end", 1.0))
        d0 = s0 * track_length_m
        d1 = s1 * track_length_m
        indices = []
        for i, pt in enumerate(spline_map):
            d = pt["distance_m"]
            if d0 <= d <= d1:
                indices.append(i)
        if not indices:
            mid = int(len(spline_map) * (s0 + s1) * 0.5) % max(len(spline_map), 1)
            indices = [mid]
        i0, i1 = indices[0], indices[-1]
        label = spline_map[(i0 + i1) // 2]
        zones.append({
            "id": corner.get("name", ""),
            "display_name": corner.get("display_name", corner.get("name", "")),
            "spline_start": s0,
            "spline_end": s1,
            "centerline_range": [i0, i1],
            "label_xy": [label["x"], label["z"]],
        })
    return zones


def build_track_geometry(fast_lane_data, track_config, source_path="fast_lane.ai"):
    track_id = track_config.get("track_id", "unknown")
    length_m = float(track_config.get("length_m", fast_lane_data.get("cumulative_length_m", 5000)))
    centerline = fast_lane_data["centerline"]
    left = fast_lane_data["left_limit"]
    right = fast_lane_data["right_limit"]
    spline_map = _spline_map(centerline, length_m)
    corners = track_config.get("corners", [])
    return {
        "source": source_path,
        "track_id": track_id,
        "display_name": track_config.get("display_name", track_id),
        "length_m": length_m,
        "centerline": centerline,
        "left_limit": left,
        "right_limit": right,
        "surface_polygon": _surface_polygon(left, right),
        "spline_map": spline_map,
        "corners": _corner_zones(corners, spline_map, length_m),
    }


def load_track_config(config_dir, track_id):
    path = os.path.join(config_dir, "tracks", "%s.json" % track_id)
    with open(path, "r") as fh:
        return json.load(fh)


def write_track_geometry(output_path, geometry):
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(output_path, "w") as fh:
        json.dump(geometry, fh, indent=2)
        fh.write("\n")
