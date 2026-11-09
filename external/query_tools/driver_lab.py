#!/usr/bin/env python3
"""Driver lab: root-cause analyses for VRE session laps (stdlib only).

Subcommands
  controls  Pedal/steer calibration from AC controls.ini (check before any technique advice).
  coast     Coasting-while-turning classified by what the car was doing just before it.
  corner    Fast-vs-slow pass comparison for one corner: entry -> rotation -> line -> throttle -> exit.
  lines     Edge-independent line study: lateral position at fixed stations, fast vs slow passes.
  sim       Quasi-steady-state lap sim calibrated on the driver's own envelopes + elevation.
  compare   Pace-first A/B of two lap groups (setup/controls variants) with confound warnings.
  style     Driving-style metrics for these laps, appended to the persistent driver profile.

Car/track agnostic: track from session.jsonl, corners from ac_app/config/tracks/<track>-<layout>.json
(generate with tools/build_track_config.py), geometry from the track's ai/fast_lane.ai.
Session specs accept a lap range: <session>[:<first>-<last>], e.g. 2026-11-08_152731_974_rt_sonoma:6-21.

Examples
  python external/query_tools/driver_lab.py controls
  python external/query_tools/driver_lab.py coast  -s 2026-11-08_170959_076_rt_sonoma
  python external/query_tools/driver_lab.py corner -s <session> [-s <session> ...] --corner "Turn 7 hairpin"
  python external/query_tools/driver_lab.py lines  -s <session> --min-lap 93 --max-lap 100
  python external/query_tools/driver_lab.py sim    -s <session>
  python external/query_tools/driver_lab.py compare -a <session>:1-12 -b <session>:14-30 --max-lap 100
  python external/query_tools/driver_lab.py style  -s <session> --max-lap 100
"""

from __future__ import print_function

import argparse
import glob
import json
import math
import os
import statistics as st
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "ac_app", "lib"))

from fast_lane_parser import parse_fast_lane  # noqa: E402

G = 9.81
AC_ROOT = os.environ.get("VRE_AC_ROOT", "/mnt/c/Program Files (x86)/Steam/steamapps/common/assettocorsa")
SESSIONS_ROOT = os.environ.get("VRE_SESSIONS", AC_ROOT + "/apps/python/VirtualRaceEngineer/data/sessions")
TRACKS_CFG = os.path.join(REPO, "ac_app", "config", "tracks")


# ---------------------------------------------------------------- helpers

def corr(a, b):
    if len(a) < 3:
        return 0.0
    ma, mb = st.mean(a), st.mean(b)
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / den if den else 0.0


def wrap(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


def med(xs, default=0.0):
    xs = list(xs)
    return st.median(xs) if xs else default


# ---------------------------------------------------------------- data context

class Context(object):
    """Laps + track geometry for one car/track combination."""

    def __init__(self, sessions, min_lap, max_lap, track_config=None, layout=None):
        self.specs = [self._parse_spec(s) for s in sessions]
        self.session_dirs = [d for d, _ in self.specs]
        self.track = self._track_id(self.session_dirs[0])
        self.car = self._session_start(self.session_dirs[0]).get("car", "")
        self.cfg_path = track_config or self._find_cfg(self.track, layout)
        with open(self.cfg_path) as fh:
            self.cfg = json.load(fh)
        self.length = float(self.cfg.get("length_m") or 0)
        self.layout = layout or self.cfg.get("layout") or ""
        fl_path = os.path.join(AC_ROOT, "content", "tracks", self.track, self.layout, "ai", "fast_lane.ai")
        if not os.path.exists(fl_path):
            fl_path = os.path.join(AC_ROOT, "content", "tracks", self.track, "ai", "fast_lane.ai")
        self.fl = parse_fast_lane(fl_path)
        self.C, self.LL, self.RL = self.fl["centerline"], self.fl["left_limit"], self.fl["right_limit"]
        self.N = len(self.C)
        if not self.length:
            self.length = self.fl["cumulative_length_m"]
        self.corners = sorted(self.cfg["corners"], key=lambda c: c["spline_start"])
        self.laps = self._load_laps(min_lap, max_lap)
        if not self.laps:
            raise SystemExit("no laps between %.1f and %.1f s in %s" % (min_lap, max_lap, sessions))
        self._tag_positions()
        self.right_sign = self._calibrate_right()

    @staticmethod
    def _resolve(s):
        if os.path.isdir(s):
            return s
        p = os.path.join(SESSIONS_ROOT, s)
        if os.path.isdir(p):
            return p
        raise SystemExit("session not found: %s" % s)

    @classmethod
    def _parse_spec(cls, spec):
        """'<session>[:first-last]' -> (dir, (first, last) or None). Windows drive colons are left alone."""
        rng = None
        head, sep, tail = spec.rpartition(":")
        if sep and tail and "/" not in tail and "\\" not in tail:
            a, _, b = tail.partition("-")
            try:
                rng = (int(a), int(b) if b else 10 ** 6)
                spec = head
            except ValueError:
                rng = None
        return cls._resolve(spec), rng

    @staticmethod
    def _session_start(session_dir):
        path = os.path.join(session_dir, "session.jsonl")
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                first = fh.readline()
            try:
                return json.loads(first)
            except ValueError:
                pass
        return {}

    @classmethod
    def _track_id(cls, session_dir):
        track = cls._session_start(session_dir).get("track")
        return track or os.path.basename(session_dir.rstrip("/")).split("_", 3)[-1]

    @staticmethod
    def _find_cfg(track, layout):
        if layout:
            p = os.path.join(TRACKS_CFG, "%s-%s.json" % (track, layout))
            if os.path.exists(p):
                return p
        cands = sorted(glob.glob(os.path.join(TRACKS_CFG, track + "*.json")))
        if len(cands) == 1:
            return cands[0]
        raise SystemExit("cannot pick a track config for %s (found %s); pass --track-config" % (track, cands))

    def _load_laps(self, lo, hi):
        laps = []
        for d, rng in self.specs:
            for p in sorted(glob.glob(os.path.join(d, "laps", "lap_*.json"))):
                try:
                    with open(p) as fh:
                        L = json.load(fh)
                except ValueError:
                    continue          # lap file still being written by the live app
                if rng and not (rng[0] <= int(L.get("lap", -1)) <= rng[1]):
                    continue
                t = (L.get("lap_time_ms") or 0) / 1000.0
                s = [x for x in L.get("samples") or [] if "pos_x" in x]
                if lo <= t <= hi and len(s) > 50:
                    L["_session"] = os.path.basename(d.rstrip("/"))
                    L["samples"] = s
                    L["_id"] = "%s L%02d" % (os.path.basename(d)[11:17], L.get("lap", 0))
                    laps.append(L)
        return laps

    # geometry ---------------------------------------------------------
    def nearest(self, x, z, hint=None):
        C = self.C
        rng = range(self.N) if hint is None else [(hint + k) % self.N for k in range(-40, 80)]
        return min(rng, key=lambda j: (C[j][0] - x) ** 2 + (C[j][1] - z) ** 2)

    def lateral(self, x, z, i):
        """Offset along the AI-line normal (+ toward the LL side) and both half-widths."""
        cx, cz = self.C[i]
        nx_, nz_ = self.C[(i + 1) % self.N]
        fx, fz = nx_ - cx, nz_ - cz
        f = math.hypot(fx, fz) or 1.0
        nx, nz = -fz / f, fx / f
        off = (x - cx) * nx + (z - cz) * nz
        wl = math.hypot(self.LL[i][0] - cx, self.LL[i][1] - cz)
        wr = math.hypot(self.RL[i][0] - cx, self.RL[i][1] - cz)
        return off, wl, wr

    def curve_sign(self, i, ahead=25):
        """+1 if the AI line bends toward the LL side at index i."""
        cx, cz = self.C[i]
        nx_, nz_ = self.C[(i + 1) % self.N]
        fx, fz = nx_ - cx, nz_ - cz
        f = math.hypot(fx, fz) or 1.0
        nx, nz = -fz / f, fx / f
        j = (i + ahead) % self.N
        return 1 if (self.C[j][0] - cx) * nx + (self.C[j][1] - cz) * nz > 0 else -1

    def _tag_positions(self):
        for L in self.laps:
            hint = None
            for x in L["samples"]:
                hint = self.nearest(x["pos_x"], x["pos_z"], hint)
                x["_i"] = hint
                x["_off"], x["_wl"], x["_wr"] = self.lateral(x["pos_x"], x["pos_z"], hint)
                x["_m"] = x["spline"] * self.length

    def _calibrate_right(self):
        """Edge labels in fast_lane.ai are not reliably left/right: learn which normal side is the driver's right.

        Steering > 0 is a right turn in VRE samples; the path bends toward the driver's right there."""
        score = 0
        for L in self.laps[:5]:
            for x in L["samples"][::3]:
                if abs(x["steer_deg"]) > 5:
                    score += (1 if x["steer_deg"] > 0 else -1) * self.curve_sign(x["_i"])
        return 1 if score >= 0 else -1

    def right_of_line(self, x):
        return x["_off"] * self.right_sign

    def corner(self, name):
        for c in self.corners:
            if name in (c.get("display_name"), c.get("name")):
                return c
        raise SystemExit("unknown corner %r; have %s" % (name, [c.get("display_name", c["name"]) for c in self.corners]))

    def cname(self, c):
        return c.get("display_name", c["name"])

    def corner_at(self, spline):
        for c in self.corners:
            if c["spline_start"] - 0.01 <= spline <= c["spline_end"] + 0.01:
                return self.cname(c)
        return "straight %.3f" % spline

    def direction(self, c):
        """+1 right-hander, -1 left-hander, from steering (track config direction can be wrong)."""
        vals = [x["steer_deg"] for L in self.laps for x in L["samples"]
                if c["spline_start"] <= x["spline"] <= c["spline_end"]]
        return 1 if med(vals) > 0 else -1

    def dt(self, p, q):
        d = (q["spline"] - p["spline"]) * self.length
        return d / max(1.0, p["speed_kmh"] / 3.6) if 0 < d < 40 else 0.0

    def window(self, L, m0, m1):
        return [x for x in L["samples"] if m0 <= x["_m"] <= m1]

    def section_time(self, s):
        return sum(self.dt(p, q) for p, q in zip(s, s[1:]))


# ---------------------------------------------------------------- controls

def _controls_paths():
    env = os.environ.get("VRE_AC_CONTROLS")
    if env:
        return [env]
    pats = ["/mnt/c/Users/*/OneDrive/Documents/Assetto Corsa/cfg/controls.ini",
            "/mnt/c/Users/*/Documents/Assetto Corsa/cfg/controls.ini",
            os.path.expanduser("~/Documents/Assetto Corsa/cfg/controls.ini")]
    out = []
    for p in pats:
        out.extend(glob.glob(p))
    return out


def cmd_controls(args):
    paths = _controls_paths()
    if not paths:
        print("controls.ini not found; set VRE_AC_CONTROLS")
        return 1
    sec, data = None, {}
    with open(paths[0], encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                sec = line[1:-1]
                data[sec] = {}
            elif "=" in line and sec:
                k, v = line.split("=", 1)
                data[sec][k.strip()] = v.strip()
    print("controls: %s" % paths[0])
    for name in ("THROTTLE", "BRAKES", "CLUTCH"):
        d = data.get(name, {})
        try:
            gamma = float(d.get("GAMMA", "1"))
        except ValueError:
            gamma = 1.0
        outs = ", ".join("%d%%->%.0f%%" % (p, 100 * (p / 100.0) ** gamma) for p in (10, 20, 30, 50))
        flag = ""
        if name == "BRAKES" and gamma > 1.2:
            flag = "  <== light brake inputs are swallowed; trail-braking and rotation cues will look like coasting"
        elif gamma < 0.8:
            flag = "  <== front-loaded curve; small inputs are amplified"
        print("  %-8s GAMMA %.2f  (%s)%s" % (name, gamma, outs, flag))
    st_ = data.get("STEER", {})
    print("  STEER    LOCK %s  (match the car's steering lock in-game or use soft lock)" % st_.get("LOCK", "?"))
    return 0


# ---------------------------------------------------------------- coast

COAST_KEYS = {"A": "A rear stepping out, driver catching it", "B": "B front not turning, waiting for rotation",
              "C": "C brake released, gap before throttle", "D": "D lifted off throttle"}


def coast_breakdown(ctx):
    """Coast = brake < 5% and throttle < 5% while steering. Cause is read from the 3 samples before it."""
    cats = {}
    for L in ctx.laps:
        s = L["samples"]
        i = 0
        while i < len(s):
            x = s[i]
            if x["brake"] < 0.05 and x["throttle"] < 0.05 and abs(x["steer_deg"]) > 3:
                j = i
                while j + 1 < len(s) and s[j + 1]["brake"] < 0.05 and s[j + 1]["throttle"] < 0.05:
                    j += 1
                dur = sum(ctx.dt(p, q) for p, q in zip(s[i:j + 1], s[i + 1:j + 2]))
                if dur >= 0.25 and i >= 3:
                    pre, seg, prev = s[i - 3:i], s[i:j + 1], s[i - 1]
                    beta_pre = max(abs(p.get("beta_deg", 0)) for p in pre + seg[:2])
                    beta_rise = abs(seg[0].get("beta_deg", 0)) - abs(pre[0].get("beta_deg", 0))
                    us = med(p.get("delta_us_deg", 0) for p in seg)
                    steer_grow = abs(seg[-1]["steer_deg"]) - abs(seg[0]["steer_deg"])
                    if beta_pre > 7 and beta_rise > 1:
                        cause = COAST_KEYS["A"]
                    elif us > 3 or steer_grow > 4:
                        cause = COAST_KEYS["B"]
                    elif prev["brake"] >= 0.05:
                        cause = COAST_KEYS["C"]
                    else:
                        cause = COAST_KEYS["D"]
                    d = cats.setdefault(cause, {"n": 0, "s": 0.0, "by": {}})
                    d["n"] += 1
                    d["s"] += dur
                    cn = ctx.corner_at(seg[0]["spline"])
                    d["by"][cn] = d["by"].get(cn, 0) + dur
                i = j + 1
            else:
                i += 1
    return cats


def cmd_coast(ctx, args):
    cats = coast_breakdown(ctx)
    n = len(ctx.laps)
    print("coasting while turning (>=0.25 s), %d laps; seconds per lap by cause" % n)
    for k in sorted(cats):
        d = cats[k]
        top = sorted(d["by"].items(), key=lambda kv: -kv[1])[:4]
        print("  %-44s %.2f s/lap (%d events)  top: %s" % (k, d["s"] / n, d["n"], ", ".join("%s %.2f" % (c, v / n) for c, v in top)))
    print("\nread: A is the only stability coast. B and C mean the car stops rotating when no pedal loads an axle;"
          " fix by overlapping brake release with throttle pickup, not by 'throttle earlier'.")
    return 0


# ---------------------------------------------------------------- corner

def corner_passes(ctx, c, pre=100.0, post=150.0):
    d = ctx.direction(c)
    m0, m1 = c["spline_start"] * ctx.length, c["spline_end"] * ctx.length
    rows = []
    for L in ctx.laps:
        s = ctx.window(L, m0 - pre, m1 + post)
        if len(s) < 15:
            continue
        cs = [x for x in s if m0 <= x["_m"] <= m1] or s
        b_on = next((x for x in s if x["brake"] > 0.1), s[0])
        apex = min(cs, key=lambda x: x["speed_kmh"])
        tin = next((x for x in s if x["_m"] > b_on["_m"] and x["steer_deg"] * d > 3), cs[0])
        last_brk = max((x["_m"] for x in s if x["brake"] > 0.05 and x["_m"] <= apex["_m"]), default=b_on["_m"])
        gap = [x for x in s if last_brk < x["_m"] <= apex["_m"] + 60 and x["throttle"] < 0.05]
        after = [x for x in s if x["_m"] >= apex["_m"]]
        commit = None
        for i, x in enumerate(after):
            if x["throttle"] > 0.9 and all(y["throttle"] > 0.85 for y in after[i:i + 10]):
                commit = x
                break
        near = [x for x in after if x["_m"] <= apex["_m"] + 60]
        steer_after = [abs(x["steer_deg"]) for x in near]
        re_steer = max((b - a for a, b in zip(steer_after, steer_after[1:])), default=0.0)
        lifts = sum(1 for a, b in zip(after, after[1:]) if a["throttle"] > 0.6 and b["throttle"] < 0.4)
        h_exit = s[-1]["heading"] if "heading" in s[-1] else 0.0
        i20 = next((k for k, x in enumerate(after) if x["throttle"] > 0.2), None)
        i95 = next((k for k, x in enumerate(after) if x["throttle"] > 0.95 and (i20 is None or k >= i20)), None)
        ramp = ctx.section_time(after[i20:i95 + 1]) if i20 is not None and i95 is not None else 9.0
        rows.append(dict(
            id=L["_id"], t=ctx.section_time(s),
            brake_on_m=b_on["_m"], v_brake_on=b_on["speed_kmh"],
            turn_in_m=tin["_m"], v_turn_in=tin["speed_kmh"], brake_at_turn_in=tin["brake"],
            last_brake_m=last_brk, trail_m=max(0.0, last_brk - tin["_m"]), coast_gap_s=ctx.section_time(gap),
            rear_slide_after_release=max((abs(x.get("beta_deg", 0)) for x in s if last_brk <= x["_m"] <= last_brk + 50), default=0),
            understeer_entry=med(x.get("delta_us_deg", 0) for x in s if tin["_m"] <= x["_m"] <= apex["_m"]),
            vmin=apex["speed_kmh"], vmin_m=apex["_m"],
            lock_max=max(abs(x["steer_deg"]) for x in cs),
            rotation_left_deg=abs(math.degrees(wrap(h_exit - apex.get("heading", 0)))),
            re_steer_deg=re_steer, lifts_after_apex=lifts,
            commit_m_after_apex=(commit["_m"] - apex["_m"]) if commit else 999.0,
            throttle_ramp_s=ramp,
            v_exit=s[-1]["speed_kmh"],
        ))
    return d, rows


def cmd_corner(ctx, args):
    c = ctx.corner(args.corner)
    d, rows = corner_passes(ctx, c, args.pre, args.post)
    if len(rows) < 8:
        print("only %d passes; need >= 8 for fast-vs-slow comparisons" % len(rows))
        return 1
    rows.sort(key=lambda r: r["t"])
    q = max(3, len(rows) // 4)
    F, S = rows[:q], rows[-q:]
    print("%s (%s-hander) n=%d; section time fast quarter %.2f s vs slow quarter %.2f s" % (
        ctx.cname(c), "right" if d > 0 else "left", len(rows), med(r["t"] for r in F), med(r["t"] for r in S)))
    print("  %-26s %9s %9s  %8s %8s  range" % ("metric", "fast", "slow", "r(time)", "r(exit)"))
    for k in rows[0]:
        if k in ("id", "t"):
            continue
        v = [r[k] for r in rows]
        rt = corr(v, [r["t"] for r in rows])
        print("  %-26s %9.2f %9.2f  %+8.2f %+8.2f  %.1f..%.1f%s" % (
            k, med(r[k] for r in F), med(r[k] for r in S), rt, corr(v, [r["v_exit"] for r in rows]),
            min(v), max(v), "  <==" if abs(rt) >= 0.4 else ""))
    print("\nstation profile (median): speed | metres right of AI line | steer | brake | throttle | rear slide | understeer")
    ids_f, ids_s = {r["id"] for r in F}, {r["id"] for r in S}
    m0, m1 = c["spline_start"] * ctx.length - args.pre, c["spline_end"] * ctx.length + args.post
    step = args.step
    for m in range(int(m0), int(m1), step):
        line = "  %5d |" % m
        for ids in (ids_f, ids_s):
            xs = [x for L in ctx.laps if L["_id"] in ids for x in L["samples"] if m <= x["_m"] < m + step]
            if not xs:
                line += " " * 46 + "|"
                continue
            line += " %5.1f %+5.1f %5.1f %4.2f %4.2f %4.1f %+4.1f |" % (
                med(x["speed_kmh"] for x in xs), med(ctx.right_of_line(x) for x in xs), med(abs(x["steer_deg"]) for x in xs),
                med(x["brake"] for x in xs), med(x["throttle"] for x in xs), med(abs(x.get("beta_deg", 0)) for x in xs),
                med(x.get("delta_us_deg", 0) for x in xs))
        print(line)
    print("  (left block = fastest quarter, right block = slowest quarter)")
    return 0


# ---------------------------------------------------------------- lines

def cmd_lines(ctx, args):
    step = args.step
    print("lateral position vs the AI line at fixed %d m stations (+ = driver's right). Reported only when"
          " |r| >= %.2f for >= 3 consecutive stations." % (step, args.r_min))
    for c in ctx.corners:
        if args.corner and args.corner not in (c.get("display_name"), c.get("name")):
            continue
        d = ctx.direction(c)
        m0, m1 = c["spline_start"] * ctx.length - args.pre, c["spline_end"] * ctx.length + args.post
        P = []
        for L in ctx.laps:
            s = ctx.window(L, m0 - 30, m1 + 30)
            prof = {}
            for m in range(int(m0), int(m1), step):
                for p, q in zip(s, s[1:]):
                    if p["_m"] <= m <= q["_m"] and q["_m"] - p["_m"] < 40:
                        f = (m - p["_m"]) / max(1e-6, q["_m"] - p["_m"])
                        prof[m] = (ctx.right_of_line(p) + (ctx.right_of_line(q) - ctx.right_of_line(p)) * f,
                                   p["speed_kmh"] + (q["speed_kmh"] - p["speed_kmh"]) * f)
                        break
            if len(prof) > 0.8 * (m1 - m0) / step:
                P.append((ctx.section_time([x for x in s if m0 <= x["_m"] <= m1]), prof))
        if len(P) < 10:
            continue
        P.sort(key=lambda z: z[0])
        q = max(5, len(P) // 4)
        res = []
        for m in range(int(m0), int(m1), step):
            have = [(t, pr[m]) for t, pr in P if m in pr]
            if len(have) < 10:
                continue
            offs = [h[1][0] for h in have]
            res.append(dict(m=m, r=corr(offs, [h[0] for h in have]), sd=st.pstdev(offs), lo=min(offs), hi=max(offs),
                            fast=med(pr[m][0] for t, pr in P[:q] if m in pr), slow=med(pr[m][0] for t, pr in P[-q:] if m in pr),
                            vf=med(pr[m][1] for t, pr in P[:q] if m in pr), vs=med(pr[m][1] for t, pr in P[-q:] if m in pr)))
        runs, cur = [], []
        for r in res:
            if abs(r["r"]) >= args.r_min and (not cur or (r["m"] - cur[-1]["m"] == step and (r["r"] > 0) == (cur[-1]["r"] > 0))):
                cur.append(r)
            else:
                if len(cur) >= 3:
                    runs.append(cur)
                cur = [r] if abs(r["r"]) >= args.r_min else []
        if len(cur) >= 3:
            runs.append(cur)
        print("\n=== %s (%s-hander) n=%d, fast quarter %.2f s vs slow quarter %.2f s" % (
            ctx.cname(c), "right" if d > 0 else "left", len(P), med(t for t, _ in P[:q]), med(t for t, _ in P[-q:])))
        for run in runs:
            pk = max(run, key=lambda r: abs(r["r"]))
            side = "right" if pk["fast"] > pk["slow"] else "left"
            inside = (side == "right") == (d > 0)
            print("  %5d-%5d m: fast passes %.1f m further %s (%s), r %+.2f; speed fast %.0f vs slow %.0f km/h; your range %+.1f..%+.1f" % (
                run[0]["m"], run[-1]["m"], abs(pk["fast"] - pk["slow"]), side, "toward inside" if inside else "toward outside",
                pk["r"], pk["vf"], pk["vs"], pk["lo"], pk["hi"]))
        if not runs:
            print("  no consistent line difference: time here is speed/commitment, not placement")
        worst = max(res, key=lambda r: r["sd"]) if res else None
        if worst:
            print("  consistency: median spread %.1f m; widest spread %.1f m at %d m" % (med(r["sd"] for r in res), worst["sd"], worst["m"]))
    print("\ncaveat: a position difference that comes with a speed difference can be a consequence of speed."
          " Trust it most where slow passes are both slower AND wider.")
    return 0


# ---------------------------------------------------------------- sim

class LapSim(object):
    DS = 2.0

    def __init__(self, ctx):
        self.ctx = ctx
        fl = ctx.fl
        dist, tot = fl["distance_m"], fl["cumulative_length_m"]
        self.tot = tot
        self.ns = int(tot // self.DS)
        xs = [c[0] for c in fl["centerline"]]
        zs = [c[1] for c in fl["centerline"]]
        ys = fl["elevation_m"]

        def interp(arr, s):
            lo, hi = 0, len(dist) - 1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if dist[mid] <= s:
                    lo = mid
                else:
                    hi = mid
            f = (s - dist[lo]) / max(1e-6, dist[hi] - dist[lo])
            return arr[lo] + (arr[hi] - arr[lo]) * f

        X = [interp(xs, i * self.DS) for i in range(self.ns)]
        Z = [interp(zs, i * self.DS) for i in range(self.ns)]
        Y = [interp(ys, i * self.DS) for i in range(self.ns)]
        n = self.ns

        def smooth(a, w):
            return [sum(a[(i + k) % n] for k in range(-w, w + 1)) / (2 * w + 1) for i in range(n)]

        H = 4
        kap = []
        for i in range(n):
            a, b, c = (i - H) % n, i, (i + H) % n
            d = wrap(math.atan2(Z[c] - Z[b], X[c] - X[b]) - math.atan2(Z[b] - Z[a], X[b] - X[a]))
            kap.append(abs(d) / (H * self.DS))
        self.kap = smooth(kap, 3)
        Ys = smooth(Y, 6)
        self.grade = [(Ys[(i + 3) % n] - Ys[(i - 3) % n]) / (6 * self.DS) for i in range(n)]
        Yv = smooth(Y, 10)
        self.kv = smooth([(Yv[(i + 8) % n] - 2 * Yv[i] + Yv[(i - 8) % n]) / (8 * self.DS) ** 2 for i in range(n)], 4)
        self.acc, self.brk = self._envelopes()

    def idx(self, m):
        return int((m / self.ctx.length) * self.tot / self.DS) % self.ns

    def _envelopes(self):
        acc, brk = {}, {}
        for L in self.ctx.laps:
            s = L["samples"]
            for p, q in zip(s, s[1:]):
                dtt = self.ctx.dt(p, q)
                if dtt <= 0.03:
                    continue
                v = p["speed_kmh"] / 3.6
                a_flat = (q["speed_kmh"] - p["speed_kmh"]) / 3.6 / dtt + G * self.grade[self.idx(p["_m"])]
                straight = abs(p["steer_deg"]) < 4
                if straight and p["throttle"] > 0.95 and q["throttle"] > 0.95 and p["brake"] < 0.02:
                    acc.setdefault(int(v // 5), []).append(a_flat)
                if straight and p["brake"] > 0.6 and q["brake"] > 0.6:
                    brk.setdefault(int(v // 5), []).append(-a_flat)

        def env(b, pct):
            out = {}
            for k, vs in b.items():
                if len(vs) >= 6:
                    vs.sort()
                    out[k] = vs[int(len(vs) * pct)]
            return out
        return env(acc, 0.6), env(brk, 0.9)

    @staticmethod
    def _look(env, v):
        k = int(v // 5)
        keys = sorted(env)
        if k in env:
            return env[k]
        if k <= keys[0]:
            return env[keys[0]]
        if k >= keys[-1]:
            return env[keys[-1]]
        lo = max(x for x in keys if x < k)
        hi = min(x for x in keys if x > k)
        return env[lo] + (env[hi] - env[lo]) * (k - lo) / (hi - lo)

    def grip_map(self, per_corner, default):
        m = [default] * self.ns
        for c in self.ctx.corners:
            nm = self.ctx.cname(c)
            if nm not in per_corner:
                continue
            a, b = self.idx(c["spline_start"] * self.ctx.length), self.idx(c["spline_end"] * self.ctx.length)
            i = a
            while i != b:
                m[i] = per_corner[nm]
                i = (i + 1) % self.ns
        return m

    def run(self, mu, vertical=True, grade=True, brake_scale=1.0):
        n, DS = self.ns, self.DS
        vmax = []
        for i in range(n):
            den = self.kap[i] - mu[i] * (self.kv[i] if vertical else 0.0)
            vmax.append(min(95.0, math.sqrt(mu[i] * G / den)) if den > 1e-5 else 95.0)
        v = vmax[:]

        def avail(i, vv, env, scale):
            nf = 1 + (vv * vv * self.kv[i] / G if vertical else 0)
            lim = mu[i] * G * max(0.2, nf)
            frac = max(0.0, 1 - (vv * vv * self.kap[i] / lim) ** 2) if lim > 0 else 0
            return self._look(env, vv) * scale * math.sqrt(frac)

        for _ in range(2):
            for i in range(n):
                j = (i + 1) % n
                a = avail(i, v[i], self.acc, 1.0) - (G * self.grade[i] if grade else 0)
                v[j] = min(v[j], math.sqrt(max(1.0, v[i] ** 2 + 2 * a * DS)))
            for i in range(n - 1, -1, -1):
                j = (i - 1) % n
                dd = avail(i, v[i], self.brk, brake_scale) + (G * self.grade[j] if grade else 0)
                v[j] = min(v[j], math.sqrt(max(1.0, v[i] ** 2 + 2 * dd * DS)))
        return sum(2 * DS / (v[i] + v[(i + 1) % n]) for i in range(n)), v


def measured_corner_grip(ctx):
    """Lateral g per corner from the driver's own path curvature (v^2 * kappa). The raw acc_g_lat
    channel is inflated by kerbs/compressions and must not be used as a grip ceiling."""
    res = {}
    for c in ctx.corners:
        per_lap = []
        for L in ctx.laps:
            s = [x for x in L["samples"] if c["spline_start"] <= x["spline"] <= c["spline_end"]]
            ays = []
            for a, b, d in zip(s, s[1:], s[2:]):
                dh = wrap(math.atan2(d["pos_z"] - b["pos_z"], d["pos_x"] - b["pos_x"]) -
                          math.atan2(b["pos_z"] - a["pos_z"], b["pos_x"] - a["pos_x"]))
                ds = 0.5 * (math.hypot(b["pos_x"] - a["pos_x"], b["pos_z"] - a["pos_z"]) +
                            math.hypot(d["pos_x"] - b["pos_x"], d["pos_z"] - b["pos_z"]))
                if ds > 0.5:
                    v = b["speed_kmh"] / 3.6
                    ays.append(v * v * abs(dh) / ds / G)
            if len(ays) >= 5:
                ays.sort()
                per_lap.append(ays[int(len(ays) * 0.85)])
        if per_lap:
            res[ctx.cname(c)] = (med(per_lap), max(per_lap))
    return res


def cmd_sim(ctx, args):
    sim = LapSim(ctx)
    times = sorted(L["lap_time_ms"] / 1000.0 for L in ctx.laps)
    grip = measured_corner_grip(ctx)
    base = med(v[1] for v in grip.values())
    print("laps %d | best %.3f | median %.3f" % (len(times), times[0], med(times)))
    print("braking (flat-equivalent m/s2 by km/h): %s" % {int(k * 18): round(v, 1) for k, v in sorted(sim.brk.items())})
    print("full-throttle accel (flat-equivalent):   %s" % {int(k * 18): round(v, 1) for k, v in sorted(sim.acc.items())})
    print("\nlateral g per corner from path curvature (median lap / best lap):")
    for nm, (m, b) in grip.items():
        print("  %-20s %.2f / %.2f" % (nm, m, b))
    t_med, _ = sim.run(sim.grip_map({k: v[0] for k, v in grip.items()}, base))
    t_best, vb = sim.run(sim.grip_map({k: v[1] for k, v in grip.items()}, base))
    t_flat, _ = sim.run(sim.grip_map({k: v[1] for k, v in grip.items()}, base), vertical=False, grade=False)
    loss = med(times) - t_med
    print("\nSIM median-lap grip %.2f s vs real median %.2f s -> transition loss %.2f s/lap (pedal gaps, coasting, rotation waits)"
          % (t_med, med(times), loss))
    print("SIM best-pass grip per corner %.2f s (compare with stitched best sections)" % t_best)
    print("SIM best-pass grip, flat track %.2f s -> elevation worth %.2f s" % (t_flat, t_flat - t_best))
    print("\nvalue of +5% grip, one corner at a time:")
    for nm in grip:
        g2 = {k: v[1] * (1.05 if k == nm else 1.0) for k, v in grip.items()}
        t, _ = sim.run(sim.grip_map(g2, base))
        print("  %-20s %.3f s" % (nm, t_best - t))
    t_up, _ = sim.run(sim.grip_map({k: v[1] * 1.02 for k, v in grip.items()}, base))
    print("\nestimate bands (sim + 0.5-0.8 s transition loss that even fast drivers keep):")
    print("  transitions fixed at current best grip: %.1f-%.1f s" % (t_best + 0.5, t_best + 0.8))
    print("  plus 2%% more grip everywhere:           %.1f-%.1f s" % (t_up + 0.5, t_up + 0.8))
    print("\nvertical load zones at sim speed (|v^2*kv/g| > 8%):")
    cur = None
    for i in range(sim.ns):
        e = vb[i] ** 2 * sim.kv[i] / G
        m = i * sim.DS * ctx.length / sim.tot
        if abs(e) > 0.08:
            if cur and cur["comp"] == (e > 0) and m - cur["end"] < 20:
                cur["end"] = m
                cur["pk"] = max(cur["pk"], abs(e))
            else:
                if cur:
                    _print_zone(ctx, cur)
                cur = {"start": m, "end": m, "comp": e > 0, "pk": abs(e)}
    if cur:
        _print_zone(ctx, cur)
    return 0


def _print_zone(ctx, z):
    print("  %5.0f-%5.0f m  %-11s %+4.0f%% load  near %s" % (
        z["start"], z["end"], "compression" if z["comp"] else "crest", (100 if z["comp"] else -100) * z["pk"],
        ctx.corner_at(z["start"] / ctx.length)))


# ---------------------------------------------------------------- compare

def group_summary(ctx):
    times = [L["lap_time_ms"] / 1000.0 for L in ctx.laps]
    slides, coast, cores = [], [], []
    for L in ctx.laps:
        s = L["samples"]
        slides.append(sum(1 for a, b in zip(s, s[1:]) if abs(a.get("beta_deg", 0)) <= 12 < abs(b.get("beta_deg", 0))))
        coast.append(sum(ctx.dt(p, q) for p, q in zip(s, s[1:])
                         if abs(p["steer_deg"]) > 3 and p["brake"] < 0.05 and p["throttle"] < 0.05))
        core = (L.get("car_state") or {}).get("core_mean")
        if core:
            cores.append(st.mean(core))
    corners = {}
    for c in ctx.corners:
        m0, m1 = c["spline_start"] * ctx.length - 50, c["spline_end"] * ctx.length + 100
        rows = []
        for L in ctx.laps:
            s = ctx.window(L, m0, m1)
            if len(s) < 8:
                continue
            first_half = [x for x in s if x["_m"] <= (m0 + m1) / 2]
            rows.append((ctx.section_time(s), min(x["speed_kmh"] for x in s),
                         max(abs(x.get("beta_deg", 0)) for x in s), med(x.get("delta_us_deg", 0) for x in first_half)))
        if rows:
            corners[ctx.cname(c)] = tuple(med(r[k] for r in rows) for k in range(4))
    order = sorted((L["_session"], int(L.get("lap", 0))) for L in ctx.laps)
    return dict(n=len(times), median=med(times), best=min(times), sd=st.pstdev(times) if len(times) > 1 else 0.0,
                slides=st.mean(slides), coast=st.mean(coast), core=med(cores, None), corners=corners,
                first=order[0], last=order[-1])


def cmd_compare(args):
    A = Context(args.a, args.min_lap, args.max_lap, args.track_config, args.layout)
    B = Context(args.b, args.min_lap, args.max_lap, args.track_config, args.layout)
    a, b = group_summary(A), group_summary(B)
    print("%-26s %10s %10s %9s" % ("", "A", "B", "B-A"))
    for k, lab, fmt in (("n", "clean laps", "%10d"), ("median", "median lap s", "%10.3f"), ("best", "best lap s", "%10.3f"),
                        ("sd", "lap spread s", "%10.3f"), ("slides", "slides >12 deg / lap", "%10.2f"),
                        ("coast", "coast while turning s/lap", "%10.2f")):
        print("%-26s " % lab + fmt % a[k] + " " + fmt % b[k] + "  %+8.3f" % (b[k] - a[k]))
    if a["core"] is not None and b["core"] is not None:
        print("%-26s %10.1f %10.1f  %+8.1f" % ("tyre core temp C", a["core"], b["core"], b["core"] - a["core"]))
    print("\nper corner (median): section time | min speed | max rear slide | entry understeer")
    for nm in a["corners"]:
        if nm not in b["corners"]:
            continue
        ca, cb = a["corners"][nm], b["corners"][nm]
        print("  %-20s %+6.3f s | %+5.1f km/h | %+5.1f deg | %+5.2f deg" % (nm, cb[0] - ca[0], cb[1] - ca[1], cb[2] - ca[2], cb[3] - ca[3]))

    d = b["median"] - a["median"]
    noise = max(0.1, 1.5 * math.sqrt(a["sd"] ** 2 / max(1, a["n"]) + b["sd"] ** 2 / max(1, b["n"])))
    print("\nVERDICT (pace first; stability is a constraint, not the goal):")
    if a["n"] < 5 or b["n"] < 5:
        print("  INCONCLUSIVE: need >= 5 clean laps per variant")
    elif d < -noise:
        print("  B FASTER by %.2f s median (noise %.2f s)%s" % (-d, noise,
              "; also more slides — keep if the driver is comfortable" if b["slides"] > a["slides"] + 0.3 else ""))
    elif d > noise:
        tag = " — MORE STABLE BUT SLOWER: reject; a calmer car that loses time is the wrong direction" \
            if b["slides"] < a["slides"] - 0.2 or b["coast"] < a["coast"] - 0.5 else ""
        print("  B SLOWER by %.2f s median (noise %.2f s)%s" % (d, noise, tag))
    else:
        print("  NO PACE DIFFERENCE (|%.2f| s within noise %.2f s): choose by style fit and driver confidence" % (d, noise))
    warn = []
    if a["core"] is not None and b["core"] is not None and abs(a["core"] - b["core"]) > 8:
        warn.append("tyre temperatures differ by %.0f C (cold-tyre laps bias the cooler group)" % abs(a["core"] - b["core"]))
    if b["first"] > a["last"]:
        warn.append("all B laps came after A: practice effect favours B — confirm with A-B-A")
    elif a["first"] > b["last"]:
        warn.append("all A laps came after B: practice effect favours A — confirm with B-A-B")
    warn.append("confirm controls (gamma, wheel preset) and technique drill were unchanged between groups")
    for w in warn:
        print("  ! " + w)
    return 0


# ---------------------------------------------------------------- style

PROFILE_PATH = os.environ.get("VRE_DRIVER_PROFILE", os.path.join(REPO, "ac_app", "data", "driver_profile.json"))
STYLE_KEYS = ("entry_slide_deg", "slide_helps_r", "brake_at_turn_in", "trail_m", "pedal_gap_s", "v_ratio",
              "throttle_ramp_s", "re_steer_deg", "fast_corner_gap_pct", "slow_corner_gap_pct",
              "coast_rotation_wait_s", "coast_pedal_swap_s", "coast_lift_s", "coast_save_s", "consistency_pct")


def style_metrics(ctx):
    per = {}
    for c in ctx.corners:
        _, rows = corner_passes(ctx, c)
        if len(rows) >= 6:
            rows.sort(key=lambda r: r["t"])
            per[ctx.cname(c)] = (rows, rows[:max(2, len(rows) // 4)])
    if not per:
        raise SystemExit("not enough corner passes for a style profile")

    def agg(key, fast=True):
        return med(med(r[key] for r in (F if fast else rows)) for rows, F in per.values())

    vmins = {nm: med(r["vmin"] for r in rows) for nm, (rows, F) in per.items()}
    split = med(vmins.values())

    def gap_pct(nm):
        rows = per[nm][0]
        best = max(r["vmin"] for r in rows)
        return 100.0 * (best - med(r["vmin"] for r in rows)) / max(1.0, best)

    cats = coast_breakdown(ctx)
    n = len(ctx.laps)

    def cs(key):
        return cats.get(COAST_KEYS[key], {"s": 0.0})["s"] / n

    times = sorted(L["lap_time_ms"] / 1000.0 for L in ctx.laps)
    return dict(
        entry_slide_deg=agg("rear_slide_after_release"),
        slide_helps_r=med(corr([r["rear_slide_after_release"] for r in rows], [r["t"] for r in rows]) for rows, _ in per.values()),
        brake_at_turn_in=agg("brake_at_turn_in"),
        trail_m=agg("trail_m"),
        pedal_gap_s=agg("coast_gap_s", fast=False),
        v_ratio=med(med(r["vmin"] / max(1.0, r["v_turn_in"]) for r in F) for _, F in per.values()),
        throttle_ramp_s=agg("throttle_ramp_s"),
        re_steer_deg=agg("re_steer_deg", fast=False),
        fast_corner_gap_pct=med(gap_pct(nm) for nm in per if vmins[nm] > split),
        slow_corner_gap_pct=med(gap_pct(nm) for nm in per if vmins[nm] <= split),
        coast_rotation_wait_s=cs("B"), coast_pedal_swap_s=cs("C"), coast_lift_s=cs("D"), coast_save_s=cs("A"),
        consistency_pct=100.0 * (med(times) - times[0]) / times[0],
        best_lap_s=times[0], median_lap_s=med(times), laps=n,
    )


def style_labels(m):
    out = []
    if m["entry_slide_deg"] >= 8 and m["slide_helps_r"] <= -0.1:
        out.append("rotation-first entry: rear slide on entry goes with your faster passes")
    elif m["entry_slide_deg"] >= 8:
        out.append("loose entry that is not paying off: slides on entry without a time gain")
    elif m["entry_slide_deg"] < 5:
        out.append("stable-rear entry: rotation comes from the front/steering")
    if m["throttle_ramp_s"] <= 1.2 and m["v_ratio"] <= 0.75:
        out.append("V-shape: sharp rotation, early straight-line throttle")
    elif m["throttle_ramp_s"] >= 2.0:
        out.append("U/flow: progressive throttle through long arcs")
    else:
        out.append("mixed V/U")
    if m["brake_at_turn_in"] >= 0.3:
        out.append("deep trail-braker")
    elif m["brake_at_turn_in"] <= 0.12:
        out.append("brakes, then turns")
    else:
        out.append("light trail-braker")
    if m["fast_corner_gap_pct"] > 1.5 * max(0.1, m["slow_corner_gap_pct"]):
        out.append("holds back in fast corners relative to slow ones")
    elif m["slow_corner_gap_pct"] > 1.5 * max(0.1, m["fast_corner_gap_pct"]):
        out.append("less consistent in slow corners than fast ones")
    if m["coast_rotation_wait_s"] + m["coast_pedal_swap_s"] > 2.0:
        out.append("pedal gaps leave the car unloaded (biggest technique lever)")
    return out


def setup_fit(m, prefs=()):
    """Setup direction that suits the measured style and stated preferences (feeds vre-setup-and-controls)."""
    if m["entry_slide_deg"] >= 8 and m["slide_helps_r"] <= 0:
        fit = ("keep entry rotation: do NOT add diff coast lock, forward brake bias, softer rear bar or rear toe-in to "
               "cure slides; fix pedal gaps first, then look for grip (pressures, camber, gearing, front bar)")
    elif m["entry_slide_deg"] < 5:
        fit = "planted-rear style: rotation aids (rearward bias, less coast lock) may feel nervous; seek front grip"
    else:
        fit = "neutral: judge every change on median pace per corner"
    text = " ".join(prefs).lower()
    if "rotation" in text or "stability" in text:
        fit += " | stated preference: no stability-for-pace trades; keep the car's rotation"
    return fit


def cmd_style(ctx, args):
    m = style_metrics(ctx)
    labels = style_labels(m)
    print("driving style — %s @ %s, %d laps (best %.3f, median %.3f)" % (ctx.car, ctx.track, m["laps"], m["best_lap_s"], m["median_lap_s"]))
    for k in STYLE_KEYS:
        print("  %-24s %8.2f" % (k, m[k]))
    print("labels:")
    for lab in labels:
        print("  - " + lab)
    prof = {"entries": []}
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH) as fh:
            prof = json.load(fh)
    prefs = prof.get("preferences", [])
    for p in args.prefer or []:
        if p not in prefs:
            prefs.append(p)
    if prefs:
        print("\ndriver preferences (stated; setup and coaching must respect these):")
        for p in prefs:
            print("  - " + p)
    fit = setup_fit(m, prefs)
    print("setup fit: " + fit)
    key = sorted(args.session)
    prev = [e for e in prof["entries"] if e.get("sessions") != key]
    same = [e for e in prev if e.get("car") == ctx.car and e.get("track") == ctx.track]
    if same:
        last = same[-1]["metrics"]
        print("\ntrend vs previous %s @ %s entry:" % (ctx.car, ctx.track))
        for k in STYLE_KEYS + ("best_lap_s", "median_lap_s"):
            if k in last:
                print("  %-24s %8.2f -> %8.2f (%+.2f)" % (k, last[k], m[k], m[k] - last[k]))
    if prev:
        counts = {}
        for e in prev + [{"labels": labels}]:
            for lab in e.get("labels", []):
                counts[lab] = counts.get(lab, 0) + 1
        print("\nconstant traits across all cars/tracks (label: sessions):")
        for lab, n in sorted(counts.items(), key=lambda kv: -kv[1])[:6]:
            print("  %2d  %s" % (n, lab))
    if not args.no_save:
        prev.append({"date": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "car": ctx.car,
                     "track": ctx.track, "sessions": key, "metrics": m, "labels": labels, "setup_fit": fit})
        os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
        with open(PROFILE_PATH, "w") as fh:
            json.dump({"preferences": prefs, "entries": prev}, fh, indent=2)
        print("\nsaved to %s (%d entries)" % (PROFILE_PATH, len(prev)))
    return 0


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("controls")
    p = sub.add_parser("compare")
    p.add_argument("-a", action="append", required=True, help="group A session spec (repeatable)")
    p.add_argument("-b", action="append", required=True, help="group B session spec (repeatable)")
    p.add_argument("--min-lap", type=float, default=0.0)
    p.add_argument("--max-lap", type=float, default=1e9)
    p.add_argument("--track-config")
    p.add_argument("--layout")
    for name in ("coast", "corner", "lines", "sim", "style"):
        p = sub.add_parser(name)
        p.add_argument("-s", "--session", action="append", required=True, help="session dir or name (repeatable)")
        p.add_argument("--min-lap", type=float, default=0.0, help="drop laps faster than this (s)")
        p.add_argument("--max-lap", type=float, default=1e9, help="drop laps slower than this (s); exclude spins/offs")
        p.add_argument("--track-config")
        p.add_argument("--layout")
        if name in ("corner", "lines"):
            p.add_argument("--corner", required=(name == "corner"))
            p.add_argument("--pre", type=float, default=100.0)
            p.add_argument("--post", type=float, default=150.0)
            p.add_argument("--step", type=int, default=20 if name == "corner" else 10)
        if name == "lines":
            p.add_argument("--r-min", type=float, default=0.40)
        if name == "style":
            p.add_argument("--no-save", action="store_true", help="print only; don't update the driver profile")
            p.add_argument("--prefer", action="append", help="record a stated driver preference (repeatable)")
    args = ap.parse_args(argv)
    if args.cmd == "controls":
        return cmd_controls(args)
    if args.cmd == "compare":
        return cmd_compare(args)
    ctx = Context(args.session, args.min_lap, args.max_lap, args.track_config, args.layout)
    return {"coast": cmd_coast, "corner": cmd_corner, "lines": cmd_lines, "sim": cmd_sim, "style": cmd_style}[args.cmd](ctx, args)


if __name__ == "__main__":
    sys.exit(main() or 0)
