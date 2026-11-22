// Lap Studio data layer: bundle loading, lap resampling on a shared distance grid, time delta, colour maps.
import type { Annotation, LabBundle, LabManifest, LapFrames, LapRow, Review, Slot } from "./types";

async function getJson<T>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export function bundleIdFromBase(base: string): string {
  return base.replace(/\/$/, "").split("/").pop() || "";
}

export async function loadBundle(base: string): Promise<LabBundle> {
  const root = base.replace(/\/$/, "");
  const manifest = await getJson<LabManifest>(`${root}/manifest.json`);
  if (!manifest) throw new Error(`No manifest at ${root}/manifest.json`);
  const f = manifest.files || {};
  const [analysis, coaching, setup, limits, track, ann, rv] = await Promise.all([
    getJson<LabBundle["analysis"]>(`${root}/${f.analysis || "analysis.json"}`),
    getJson<LabBundle["coaching"]>(`${root}/${f.coaching || "coaching.json"}`),
    getJson<LabBundle["setup"]>(`${root}/${f.setup || "setup.json"}`),
    getJson<LabBundle["limits"]>(`${root}/${f.limits || "track_limits.json"}`),
    getJson<LabBundle["track"]>(`${root}/${f.track || "track.json"}`),
    getJson<{ annotations: Annotation[] }>(`${root}/${f.annotations || "annotations.json"}`),
    getJson<{ reviews: string[] }>(`/api/bundles/${bundleIdFromBase(root)}/reviews`),
  ]);
  return {
    base: root,
    manifest,
    analysis,
    coaching,
    setup,
    limits: limits && !(limits as { error?: string }).error ? limits : limits,
    track,
    annotations: ann?.annotations ?? [],
    reviews: rv?.reviews ?? ["auto"],
  };
}

export async function loadReview(base: string, name: string): Promise<Review | null> {
  return getJson<Review>(`${base.replace(/\/$/, "")}/reviews/${name}.json`);
}

const lapCache = new Map<string, Promise<LapFrames | null>>();

export function loadLap(base: string, row: LapRow): Promise<LapFrames | null> {
  const key = `${base}/${row.frames}`;
  if (!lapCache.has(key)) lapCache.set(key, getJson<LapFrames>(`${base.replace(/\/$/, "")}/${row.frames}`));
  return lapCache.get(key)!;
}

export function lapRow(m: LabManifest, slot: Slot | null): LapRow | null {
  if (!slot) return null;
  const d = m.drivers.find((x) => x.label === slot.driver);
  return d?.laps.find((l) => l.lap_index === slot.lap) ?? null;
}

/** Best usable lap: valid, flying, not partial, synced; falls back progressively. */
export function bestLap(m: LabManifest, driver: string): number | null {
  const d = m.drivers.find((x) => x.label === driver);
  if (!d || !d.laps.length) return null;
  const tiers = [
    (l: LapRow) => l.valid !== false && l.flying !== false && !l.partial && l.sync_ok !== false,
    (l: LapRow) => !l.partial && l.sync_ok !== false,
    () => true,
  ];
  for (const ok of tiers) {
    const c = d.laps.filter(ok);
    if (c.length) return c.reduce((a, b) => (b.lap_ms < a.lap_ms ? b : a)).lap_index;
  }
  return null;
}

/** Resolve a review lap spec ("best", a lap number) for a role. */
export function resolveLapSpec(m: LabManifest, role: "me" | "ref", spec: string | number | undefined, fallback: Slot | null): Slot | null {
  const d = m.drivers.find((x) => x.role === role) ?? (role === "ref" ? null : m.drivers[0]);
  if (!d) return fallback;
  if (spec === undefined || spec === "best") {
    const b = bestLap(m, d.label);
    return b === null ? fallback : { driver: d.label, lap: b };
  }
  const n = Number(spec);
  return d.laps.some((l) => l.lap_index === n) ? { driver: d.label, lap: n } : fallback;
}

// ---------- numerics ----------

/** Linear interpolation on monotonically increasing xs (binary search). */
export function interp(xs: ArrayLike<number>, ys: ArrayLike<number>, x: number): number {
  const n = xs.length;
  if (n === 0) return NaN;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[n - 1]) return ys[n - 1];
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  const f = (x - xs[lo]) / (xs[hi] - xs[lo] || 1);
  return ys[lo] + f * (ys[hi] - ys[lo]);
}

/** Interpolate an angle in degrees (shortest path). */
export function interpAngle(xs: ArrayLike<number>, ys: ArrayLike<number>, x: number): number {
  const n = xs.length;
  if (n === 0) return 0;
  if (x <= xs[0]) return ys[0];
  if (x >= xs[n - 1]) return ys[n - 1];
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  const f = (x - xs[lo]) / (xs[hi] - xs[lo] || 1);
  let d = ys[hi] - ys[lo];
  if (d > 180) d -= 360;
  if (d < -180) d += 360;
  return ys[lo] + f * d;
}

/** Index of the last sample with xs[i] <= x. */
export function indexAt(xs: ArrayLike<number>, x: number): number {
  let lo = 0;
  let hi = xs.length - 1;
  if (x <= xs[0]) return 0;
  if (x >= xs[hi]) return hi;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= x) lo = mid;
    else hi = mid;
  }
  return lo;
}

export const CHANNELS = ["t", "speed_kmh", "throttle", "brake", "steer_deg", "gear", "rpm", "g_lat", "g_lon", "g_vert", "lat_m", "y", "slip_deg"] as const;
export type Channel = (typeof CHANNELS)[number];

/** A lap prepared for analysis: monotone distance, channels on that distance, plus a shared-grid copy. */
export interface PreparedLap {
  slot: Slot;
  frames: LapFrames;
  s: Float64Array; // monotone distance per frame (m from S/F)
  ch: Record<Channel, Float64Array>; // per frame
  lapS: number; // lap time (s)
}

export function prepareLap(slot: Slot, f: LapFrames): PreparedLap {
  const n = f.s_m.length;
  const keep: number[] = [];
  let last = -Infinity;
  for (let i = 0; i < n; i++) {
    const s = f.s_m[i];
    if (s > last + 1e-6) {
      keep.push(i);
      last = s;
    }
  }
  const s = new Float64Array(keep.map((i) => f.s_m[i]));
  const ch = {} as Record<Channel, Float64Array>;
  for (const c of CHANNELS) {
    const src = (f as unknown as Record<string, (number | null)[]>)[c];
    ch[c] = new Float64Array(keep.map((i) => (src && src[i] != null ? (src[i] as number) : 0)));
  }
  return { slot, frames: f, s, ch, lapS: f.meta.lap_ms / 1000 };
}

/** Elapsed lap time at distance s, with the S/F crossing as t=0. */
export function timeAtS(p: PreparedLap, s: number): number {
  return interp(p.s, p.ch.t, s);
}

/** Distance reached at elapsed lap time t. */
export function sAtTime(p: PreparedLap, t: number): number {
  return interp(p.ch.t, p.s, t);
}

export interface Grid {
  step: number;
  s: Float64Array;
  a: Record<Channel, Float64Array>;
  b: Record<Channel, Float64Array> | null;
  delta: Float64Array | null; // tA - tB at s (positive = A slower so far)
  deltaRate: Float64Array | null; // d(delta)/ds per 100 m, smoothed (positive = A losing here)
}

export function buildGrid(a: PreparedLap, b: PreparedLap | null, length: number, step = 2): Grid {
  const n = Math.floor(length / step) + 1;
  const s = new Float64Array(n);
  for (let i = 0; i < n; i++) s[i] = i * step;
  const sample = (p: PreparedLap) => {
    const out = {} as Record<Channel, Float64Array>;
    for (const c of CHANNELS) {
      const arr = new Float64Array(n);
      for (let i = 0; i < n; i++) arr[i] = interp(p.s, p.ch[c], s[i]);
      out[c] = arr;
    }
    return out;
  };
  const A = sample(a);
  const B = b ? sample(b) : null;
  let delta: Float64Array | null = null;
  let deltaRate: Float64Array | null = null;
  if (B) {
    delta = new Float64Array(n);
    for (let i = 0; i < n; i++) delta[i] = A.t[i] - B.t[i];
    const base = delta[0];
    for (let i = 0; i < n; i++) delta[i] -= base;
    deltaRate = new Float64Array(n);
    const w = Math.max(1, Math.round(20 / step));
    for (let i = 0; i < n; i++) {
      const i0 = Math.max(0, i - w);
      const i1 = Math.min(n - 1, i + w);
      deltaRate[i] = ((delta[i1] - delta[i0]) / ((i1 - i0) * step || 1)) * 100;
    }
  }
  return { step, s, a: A, b: B, delta, deltaRate };
}

export function gridValue(g: Grid, arr: Float64Array | null, s: number): number {
  if (!arr) return NaN;
  const x = s / g.step;
  const i = Math.max(0, Math.min(arr.length - 2, Math.floor(x)));
  const f = Math.max(0, Math.min(1, x - i));
  return arr[i] + f * (arr[i + 1] - arr[i]);
}

// ---------- colour ----------

/** Perceptual blue→cyan→yellow→red ramp (turbo-like) for rainbow maps. */
export function ramp(t: number): string {
  const x = Math.max(0, Math.min(1, t));
  const stops: [number, number, number][] = [
    [48, 18, 59],
    [70, 107, 227],
    [40, 187, 236],
    [50, 241, 152],
    [164, 252, 60],
    [237, 208, 58],
    [251, 128, 34],
    [208, 47, 5],
  ];
  const p = x * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(p));
  const f = p - i;
  const c = stops[i].map((v, k) => Math.round(v + f * (stops[i + 1][k] - v)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

/** Diverging green (gaining) ↔ grey ↔ red (losing). v in [-1, 1]. */
export function diverge(v: number): string {
  const x = Math.max(-1, Math.min(1, v));
  const grey = [120, 128, 140];
  const red = [239, 68, 68];
  const green = [34, 197, 94];
  const tgt = x > 0 ? red : green;
  const f = Math.abs(x);
  const c = grey.map((g, k) => Math.round(g + f * (tgt[k] - g)));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export const COLORS = { A: "#ff7a45", B: "#4cc2ff", lose: "#ef4444", gain: "#22c55e", brake: "#ef4444", throttle: "#22c55e" };

// ---------- formatting ----------

export function fmtLap(ms: number | null | undefined): string {
  if (ms == null || !isFinite(ms)) return "—";
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return m > 0 ? `${m}:${r.toFixed(3).padStart(6, "0")}` : r.toFixed(3);
}

export function fmtDelta(s: number | null | undefined, nd = 2): string {
  if (s == null || !isFinite(s)) return "—";
  return `${s > 0 ? "+" : s < 0 ? "−" : "±"}${Math.abs(s).toFixed(nd)}`;
}

export function slotKey(s: Slot | null): string {
  return s ? `${s.driver}#${s.lap}` : "";
}
