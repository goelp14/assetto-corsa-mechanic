import type { ChannelAvailability, LapSample, LayerState } from "../types";

const MIN_COVERAGE = 0.08;

function fieldCoverage(samples: LapSample[], pred: (s: LapSample) => boolean): boolean {
  if (!samples.length) return false;
  let n = 0;
  for (const s of samples) {
    if (pred(s)) n++;
  }
  return n / samples.length >= MIN_COVERAGE;
}

/** Detect which telemetry channels exist in this bundle (old archives omit newer fields). */
export function detectChannelAvailability(
  samples: LapSample[],
  opts: {
    hasGgEnvelope?: boolean;
    hasTimeLoss?: boolean;
    hasWorldCoords?: boolean;
    hasProjectedCoords?: boolean;
  } = {},
): ChannelAvailability {
  const hasLongG =
    fieldCoverage(samples, (s) => s.acc_g_long != null && !Number.isNaN(s.acc_g_long)) ||
    false;
  return {
    acc_g_lat: samples.length > 0,
    acc_g_long: hasLongG,
    beta_deg: fieldCoverage(samples, (s) => s.beta_deg != null && !Number.isNaN(s.beta_deg)),
    delta_us_deg: fieldCoverage(
      samples,
      (s) => s.delta_us_deg != null && !Number.isNaN(s.delta_us_deg),
    ),
    yaw_rate: fieldCoverage(samples, (s) => s.yaw_rate != null && !Number.isNaN(s.yaw_rate)),
    wheel_load: fieldCoverage(samples, (s) => Array.isArray(s.wheel_load) && s.wheel_load.length === 4),
    susp_ratio: fieldCoverage(samples, (s) => Array.isArray(s.susp_ratio) && s.susp_ratio.length === 4),
    phase: fieldCoverage(samples, (s) => !!s.phase),
    gg_envelope: !!opts.hasGgEnvelope,
    time_loss: !!opts.hasTimeLoss,
    world_coords: !!opts.hasWorldCoords,
    projected_coords: !!opts.hasProjectedCoords,
  };
}

/** Defaults: core channels on; new/analysis channels on only when data exists. */
export function defaultLayersForAvailability(avail: ChannelAvailability): LayerState {
  return {
    mapTarmac: true,
    mapLines: true,
    mapCorners: true,
    corrections: true,
    opportunities: true,
    setup: true,
    surface: true,
    coach: true,
    setupPanel: true,
    // Core — always in archives
    chartSpeed: true,
    chartBrake: true,
    chartThrottle: true,
    chartSteer: true,
    chartLatG: avail.acc_g_lat,
    chartDelta: true,
    chartPhase: avail.phase,
    // Analysis / physics — off unless present
    chartTimeLoss: avail.time_loss,
    chartGg: avail.gg_envelope && avail.acc_g_long,
    chartGrip: avail.gg_envelope,
    chartLongG: avail.acc_g_long,
    chartBalance: avail.delta_us_deg,
    chartBeta: avail.beta_deg,
    chartYaw: avail.yaw_rate,
    chartWheelLoad: avail.wheel_load,
    chartSuspension: avail.susp_ratio,
  };
}

/** Merge saved layer prefs; force unavailable channels off. */
export function mergeLayersWithAvailability(
  saved: Partial<LayerState> | null,
  avail: ChannelAvailability,
): LayerState {
  const base = defaultLayersForAvailability(avail);
  if (!saved) return base;

  const merged = { ...base, ...saved };
  if (!avail.acc_g_lat) merged.chartLatG = false;
  if (!avail.gg_envelope) {
    merged.chartGg = false;
    merged.chartGrip = false;
  }
  if (!avail.acc_g_long) {
    merged.chartGg = false;
    merged.chartLongG = false;
  }
  if (!avail.time_loss) merged.chartTimeLoss = false;
  if (!avail.delta_us_deg) merged.chartBalance = false;
  if (!avail.beta_deg) merged.chartBeta = false;
  if (!avail.yaw_rate) merged.chartYaw = false;
  if (!avail.wheel_load) merged.chartWheelLoad = false;
  if (!avail.susp_ratio) merged.chartSuspension = false;
  if (!avail.phase) merged.chartPhase = false;
  return merged;
}
