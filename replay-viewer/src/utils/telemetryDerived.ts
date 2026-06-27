import type { LapSample } from "../types";
import type { Annotation } from "../types";
import type { CornerTimeLoss } from "../types";

export interface EnrichedSample extends LapSample {
  acc_g_long: number;
}

/** Sort, drop backward jitter, and dedupe so spline is strictly increasing (required by uPlot). */
export function preparePlotSeries<T extends LapSample>(samples: T[]): T[] {
  const sorted = [...samples].sort((a, b) => a.spline - b.spline);
  const out: T[] = [];
  for (const s of sorted) {
    const last = out[out.length - 1];
    if (!last) {
      out.push(s);
      continue;
    }
    const ds = s.spline - last.spline;
    if (ds < -0.003) continue;
    if (ds < 0.00008) {
      out[out.length - 1] = s;
      continue;
    }
    out.push(s);
  }
  return out;
}

export function mapLineSegments(
  samples: LapSample[],
  geometry: { centerline: [number, number][] },
  maxJumpM = 55,
  maxSplineGap = 0.1,
): [number, number][][] {
  const prepared = preparePlotSeries(samples);
  const segments: [number, number][][] = [];
  let current: [number, number][] = [];
  let prev: LapSample | null = null;

  for (const s of prepared) {
    let x = s.pos_x;
    let z = s.pos_z;
    if (x == null || z == null) {
      const idx = Math.round(s.spline * (geometry.centerline.length - 1));
      const pt = geometry.centerline[Math.min(Math.max(idx, 0), geometry.centerline.length - 1)];
      x = pt[0];
      z = pt[1];
    }
    const pt: [number, number] = [x, z];
    if (prev && current.length > 0) {
      const [px, pz] = current[current.length - 1];
      const dist = Math.hypot(pt[0] - px, pt[1] - pz);
      const ds = s.spline - prev.spline;
      if (dist > maxJumpM || ds > maxSplineGap) {
        if (current.length > 1) segments.push(current);
        current = [];
      }
    }
    current.push(pt);
    prev = s;
  }
  if (current.length > 1) segments.push(current);
  return segments;
}

export function pathFromSegments(segments: [number, number][][]): string {
  return segments
    .map((seg) =>
      seg.map(([x, z], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${z.toFixed(2)}`).join(" "),
    )
    .join(" ");
}

/** Sort samples and ensure longitudinal G for G-G / traction-circle plots. */
export function enrichSamples(samples: LapSample[], trackLengthM = 3337): EnrichedSample[] {
  const sorted = preparePlotSeries(samples);
  return sorted.map((s, i) => {
    let acc_g_long = s.acc_g_long;
    if (acc_g_long == null || Number.isNaN(acc_g_long)) {
      if (i > 0) {
        const prev = sorted[i - 1];
        const ds = Math.max(0.5, (s.spline - prev.spline) * trackLengthM);
        const v0 = prev.speed_kmh / 3.6;
        const v1 = s.speed_kmh / 3.6;
        acc_g_long = ((v1 - v0) / ds) / 9.81;
      } else {
        acc_g_long = s.throttle * 0.35 - s.brake * 1.1;
      }
    }
    return { ...s, acc_g_long };
  });
}

export function filterBySplineRange<T extends { spline: number }>(
  samples: T[],
  range?: [number, number] | null,
): T[] {
  if (!range) return samples;
  const [a, b] = range;
  return samples.filter((s) => s.spline >= a && s.spline <= b);
}

export function speedToColor(speedKmh: number, min: number, max: number): string {
  const t = Math.max(0, Math.min(1, (speedKmh - min) / Math.max(max - min, 1)));
  const hue = 120 - t * 120;
  return `hsl(${hue}, 70%, 50%)`;
}

export function indexAtSpline(samples: LapSample[], spline: number): number {
  let idx = 0;
  let bestD = Infinity;
  for (let i = 0; i < samples.length; i++) {
    const d = Math.abs(samples[i].spline - spline);
    if (d < bestD) {
      bestD = d;
      idx = i;
    }
  }
  return idx;
}

export function peakAyAtSpeed(
  peakAy: number[],
  speedKmh: number,
  binWidth = 30,
): number {
  const idx = Math.min(
    peakAy.length - 1,
    Math.max(0, Math.floor(speedKmh / binWidth)),
  );
  return peakAy[idx] || 2.0;
}

/** Fraction of personal peak lateral G used at this speed (0–1.5). */
export function gripUsage(
  peakAy: number[],
  speedKmh: number,
  ayG: number,
  binWidth = 30,
): number {
  const peak = peakAyAtSpeed(peakAy, speedKmh, binWidth);
  if (peak < 0.25) return 1.0;
  return Math.min(1.5, Math.abs(ayG) / peak);
}

export function gripLeftPct(usage: number): number {
  if (usage >= 0.92) return 0;
  return Math.round((0.92 - usage) * 100);
}

export function gripUsageColor(usage: number): string {
  if (usage > 1.02) return "#ef4444";
  if (usage >= 0.85) return "#22c55e";
  if (usage >= 0.6) return "#eab308";
  return "#38bdf8";
}

export function decimateSeries<T>(items: T[], maxPoints: number): T[] {
  if (items.length <= maxPoints) return items;
  const out: T[] = [];
  const step = (items.length - 1) / Math.max(maxPoints - 1, 1);
  for (let i = 0; i < maxPoints; i++) {
    out.push(items[Math.round(i * step)]);
  }
  return out;
}

export function sessionPeakAy(peakAy: number[]): number {
  return Math.max(...peakAy.filter((v) => v > 0.3), 2.2);
}

export function splineFromMouseX(
  samples: LapSample[],
  clientX: number,
  rect: DOMRect,
  viewRange?: [number, number] | null,
): number {
  const t = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
  const s0 = viewRange?.[0] ?? 0;
  const s1 = viewRange?.[1] ?? 1;
  const spline = s0 + t * (s1 - s0);
  const idx = indexAtSpline(samples, spline);
  return samples[idx]?.spline ?? spline;
}

export interface RegionBand {
  id: string;
  start: number;
  end: number;
  color: string;
  title?: string;
}

function categoryColor(category: Annotation["category"]) {
  if (category === "opportunity") return "rgba(6,182,212,0.22)";
  if (category === "setup") return "rgba(168,85,247,0.22)";
  if (category === "coach") return "rgba(56,189,248,0.24)";
  return "rgba(249,115,22,0.22)";
}

export function annotationRegions(
  annotations: Annotation[],
  activeLap?: number | null,
): RegionBand[] {
  return annotations
    .filter((a) => {
      if (a.spline <= 0) return false;
      if (activeLap != null && a.lap != null && a.lap !== activeLap) return false;
      return true;
    })
    .map((a) => ({
      id: a.id,
      start: a.spline_start ?? Math.max(0, a.spline - 0.012),
      end: a.spline_end ?? Math.min(1, a.spline + 0.012),
      color: categoryColor(a.category),
      title: a.title,
    }));
}

export function timeLossRegions(corners: CornerTimeLoss[]): RegionBand[] {
  if (!corners.length) return [];
  const max = Math.max(...corners.map((c) => c.loss_s), 0.05);
  return corners.map((c) => ({
    id: `loss_${c.corner}`,
    start: c.spline_start,
    end: c.spline_end,
    color: `rgba(251,146,60,${0.12 + 0.4 * (c.loss_s / max)})`,
    title: `${c.corner_display}: +${c.loss_s.toFixed(2)}s`,
  }));
}

const PHASE_COLORS: Record<string, string> = {
  entry: "rgba(59,130,246,0.1)",
  mid: "rgba(168,85,247,0.1)",
  exit: "rgba(34,197,94,0.1)",
};

/** Corner phase bands (entry / mid / exit) when phase is logged per sample. */
export function phaseRegions(samples: LapSample[]): RegionBand[] {
  const sorted = preparePlotSeries(samples).filter((s) => s.phase);
  if (!sorted.length) return [];
  const out: RegionBand[] = [];
  let runPhase = sorted[0].phase!;
  let runStart = sorted[0].spline;
  let runEnd = sorted[0].spline;
  for (let i = 1; i < sorted.length; i++) {
    const s = sorted[i];
    if (s.phase === runPhase) {
      runEnd = s.spline;
    } else {
      out.push({
        id: `ph_${runPhase}_${runStart}`,
        start: runStart,
        end: runEnd,
        color: PHASE_COLORS[runPhase] ?? "rgba(148,163,184,0.08)",
        title: runPhase,
      });
      runPhase = s.phase!;
      runStart = s.spline;
      runEnd = s.spline;
    }
  }
  out.push({
    id: `ph_${runPhase}_${runStart}`,
    start: runStart,
    end: runEnd,
    color: PHASE_COLORS[runPhase] ?? "rgba(148,163,184,0.08)",
    title: runPhase,
  });
  return out;
}

function wheelVal(s: LapSample, i: number): number | null {
  const w = s.wheel_load;
  return w && w.length > i ? w[i] : null;
}

function suspVal(s: LapSample, i: number): number | null {
  const r = s.susp_ratio;
  return r && r.length > i ? r[i] * 100 : null;
}

export { wheelVal, suspVal };
