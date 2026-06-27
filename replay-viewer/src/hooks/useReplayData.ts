import { useCallback, useEffect, useState } from "react";
import type {
  Annotation,
  Geometry,
  LapData,
  LapSample,
  Manifest,
  SessionPlan,
  SetupEpisode,
  StintSummary,
  TimeLossAnalysis,
} from "../types";

export interface ReplayBundle {
  manifest: Manifest;
  geometry: Geometry | null;
  laps: Map<number, LapData>;
  annotations: Annotation[];
  coachNotes: Annotation[];
  stintSummary: StintSummary | null;
  setupTimeline: SetupEpisode[];
  setupEpisodes: SetupEpisode[];
  ggEnvelope: { peak_ay: number[] } | null;
  narrative: string | null;
  narrativeSections?: { corner_id?: string; heading: string; body: string }[];
  timeLoss: TimeLossAnalysis | null;
  sessionPlan: SessionPlan | null;
}

async function fetchJson<T>(base: string, path: string): Promise<T | null> {
  try {
    const root = base.replace(/\/$/, "");
    const rel = path.replace(/^\//, "");
    const res = await fetch(`${root}/${rel}`);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

async function fetchText(base: string, path: string): Promise<string | null> {
  try {
    const root = base.replace(/\/$/, "");
    const rel = path.replace(/^\//, "");
    const res = await fetch(`${root}/${rel}`);
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

export function useReplayData(bundleBase: string | null) {
  const [data, setData] = useState<ReplayBundle | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (base: string) => {
    setLoading(true);
    setError(null);
    try {
      const manifest = await fetchJson<Manifest>(base, "manifest.json");
      if (!manifest) throw new Error("manifest.json not found");

      const geometry = await fetchJson<Geometry>(base, manifest.geometry);
      const annotations =
        (await fetchJson<Annotation[]>(base, "analysis/annotations.json")) ?? [];
      const coachNotesPayload = manifest.coach_notes
        ? await fetchJson<{ notes?: Annotation[] }>(base, manifest.coach_notes)
        : null;
      const coachNotes = coachNotesPayload?.notes ?? [];
      const stintSummary = await fetchJson<StintSummary>(
        base,
        "analysis/stint_summary.json",
      );
      const setupEpisodes =
        (await fetchJson<SetupEpisode[]>(base, "analysis/setup_episodes.json")) ?? [];
      const setupTimeline =
        (await fetchJson<SetupEpisode[]>(base, "analysis/setup_timeline.json")) ??
        setupEpisodes;
      const ggEnvelope = await fetchJson<{ peak_ay: number[] }>(
        base,
        "analysis/gg_envelope.json",
      );
      const narrativeJson = await fetchJson<{
        markdown?: string;
        sections?: { corner_id?: string; heading: string; body: string }[];
      }>(base, "analysis/narrative.json");
      let narrative = narrativeJson?.markdown ?? null;
      const narrativeSections = narrativeJson?.sections ?? undefined;
      if (!narrative) {
        narrative = await fetchText(base, "analysis/narrative.md");
      }
      const timeLoss = await fetchJson<TimeLossAnalysis>(base, "analysis/time_loss.json");
      const sessionPlan = await fetchJson<SessionPlan>(base, "analysis/session_plan.json");

      const laps = new Map<number, LapData>();
      for (const entry of manifest.laps) {
        const lap = await fetchJson<LapData>(base, entry.file);
        if (lap) laps.set(entry.lap, lap);
      }

      setData({
        manifest,
        geometry,
        laps,
        annotations,
        coachNotes,
        stintSummary,
        setupTimeline,
        setupEpisodes,
        ggEnvelope,
        narrative,
        narrativeSections,
        timeLoss,
        sessionPlan,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (bundleBase) load(bundleBase);
  }, [bundleBase, load]);

  return { data, loading, error, load };
}

export function computeStitchedDelta(
  samples: LapSample[],
  stitchedSpeeds: number[],
  trackLengthM: number,
  numBuckets = 360,
): number[] {
  const sorted = [...samples].sort((a, b) => a.spline - b.spline);
  let cum = 0;
  const out: number[] = [];
  let prevSpline = sorted[0]?.spline ?? 0;
  for (const s of sorted) {
    const bin = Math.min(numBuckets - 1, Math.max(0, Math.floor(s.spline * numBuckets)));
    const refKmh = stitchedSpeeds[bin] ?? s.speed_kmh;
    const ds = Math.max(0, (s.spline - prevSpline) * trackLengthM);
    const spd = Math.max(s.speed_kmh / 3.6, 1);
    const ref = Math.max(refKmh / 3.6, 1);
    cum += (1 / spd - 1 / ref) * ds;
    out.push(cum);
    prevSpline = s.spline;
  }
  return out;
}

export function computeDelta(
  samples: LapSample[],
  refSamples: LapSample[],
  trackLengthM = 3337,
): number[] {
  const sorted = [...samples].sort((a, b) => a.spline - b.spline);
  const refSorted = [...refSamples].sort((a, b) => a.spline - b.spline);
  const refBySpline = new Map<number, number>();
  for (const s of refSorted) {
    refBySpline.set(Math.round(s.spline * 2000), s.speed_kmh);
  }
  let cum = 0;
  const out: number[] = [];
  let prevSpline = sorted[0]?.spline ?? 0;
  for (const s of sorted) {
    const key = Math.round(s.spline * 2000);
    const refSpd = refBySpline.get(key) ?? s.speed_kmh;
    const ds = Math.max(0, (s.spline - prevSpline) * trackLengthM);
    const spd = Math.max(s.speed_kmh / 3.6, 1);
    const ref = Math.max(refSpd / 3.6, 1);
    cum += (1 / ref - 1 / spd) * ds;
    out.push(cum);
    prevSpline = s.spline;
  }
  return out;
}
