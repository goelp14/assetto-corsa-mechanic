export interface SetupEpisode {
  episode_id: string;
  tweak_id?: string;
  parameter?: string;
  parameter_display?: string;
  old_value?: unknown;
  new_value?: unknown;
  delta?: number;
  symptom?: string;
  reason?: string;
  source?: string;
  status?: string;
  detected_lap?: number;
  detected_corner?: string;
  detected_corner_display?: string;
  detected_phase?: string;
  detected_spline?: number;
  detected_spline_start?: number;
  detected_spline_end?: number;
  detection_what?: string;
  detection_why?: string;
  verdict?: string;
  input_score?: number;
  output_score?: number;
  corner_delta_s?: number;
  queued_lap?: number;
  applied_lap?: number | null;
  applied_at_pit?: boolean;
  active_from_lap?: number | null;
  active_to_lap?: number | null;
  evaluation_lap?: number;
  effectiveness?: number | null;
  lap_time_delta_ms?: number | null;
  avg_lap_before_ms?: number | null;
  avg_lap_after_ms?: number | null;
  action?: string;
}

export interface Manifest {
  session_id: string;
  track_id: string;
  track_display: string;
  track_length_m?: number;
  car_id?: string;
  laps: { lap: number; lap_time_ms: number; file: string }[];
  best_lap_ms: number | null;
  theoretical_best_ms: number | null;
  geometry: string;
  analysis: string;
  has_world_coords?: boolean;
  has_projected_coords?: boolean;
  archive_note?: string;
  channel_availability?: ChannelAvailability;
  coach_notes?: string | null;
}

export interface Geometry {
  track_id: string;
  display_name?: string;
  centerline: [number, number][];
  left_limit: [number, number][];
  right_limit: [number, number][];
  surface_polygon: [number, number][];
  corners: {
    id: string;
    display_name: string;
    spline_start: number;
    spline_end: number;
    label_xy: [number, number];
  }[];
}

export interface LapSample {
  spline: number;
  corner?: string;
  phase?: string;
  speed_kmh: number;
  brake: number;
  throttle: number;
  steer_deg: number;
  acc_g_lat: number;
  acc_g_long?: number;
  beta_deg?: number;
  delta_us_deg?: number;
  yaw_rate?: number;
  pos_x?: number;
  pos_z?: number;
  heading?: number;
  wheel_load?: number[];
  susp_ratio?: number[];
}

export interface LapData {
  lap: number;
  lap_time_ms: number;
  samples: LapSample[];
}

export interface Annotation {
  id: string;
  lap?: number;
  spline: number;
  spline_start?: number;
  spline_end?: number;
  corner?: string;
  corner_display?: string;
  phase?: string;
  category: "correction" | "opportunity" | "setup" | "surface" | "coach";
  subtype?: string;
  title?: string;
  what?: string;
  why?: string;
  action?: string;
  evidence?: Record<string, unknown>;
  source?: string;
}

export interface StintSummary {
  best_lap_ms?: number;
  theoretical_best_ms?: number;
  potential_gap_s?: number;
  lap_count?: number;
}

export interface CornerTimeLoss {
  corner: string;
  corner_display: string;
  spline_start: number;
  spline_end: number;
  loss_s: number;
  primary_action?: string;
  primary_title?: string;
  fixes?: {
    category: string;
    title: string;
    action: string;
    what?: string;
    subtype?: string;
    phase?: string;
  }[];
}

export interface LapTimeLoss {
  lap: number;
  lap_time_ms: number;
  potential_gap_s: number;
  corners: CornerTimeLoss[];
}

export interface TimeLossAnalysis {
  theoretical_best_ms: number;
  best_lap_ms: number;
  potential_gap_s: number;
  track_length_m: number;
  num_buckets: number;
  stitched_bucket_speed_kmh: number[];
  laps: Record<string, LapTimeLoss>;
}

export interface SessionPlanItem {
  corner: string;
  corner_display: string;
  loss_s: number;
  drill: string;
  spline_start: number;
  spline_end: number;
}

export interface CoachResponse {
  summary?: string;
  what?: string;
  why?: string;
  how?: string;
  drill?: string;
  citations?: string[];
  confidence?: number;
  status?: string;
  question_type?: string;
}

export interface SessionPlan {
  potential_gap_s: number;
  items: SessionPlanItem[];
}

export interface ChannelAvailability {
  acc_g_lat: boolean;
  acc_g_long: boolean;
  beta_deg: boolean;
  delta_us_deg: boolean;
  yaw_rate: boolean;
  wheel_load: boolean;
  susp_ratio: boolean;
  phase: boolean;
  gg_envelope: boolean;
  time_loss: boolean;
  world_coords: boolean;
  projected_coords: boolean;
}

export interface LayerState {
  mapTarmac: boolean;
  mapLines: boolean;
  mapCorners: boolean;
  corrections: boolean;
  opportunities: boolean;
  setup: boolean;
  surface: boolean;
  coach: boolean;
  chartSpeed: boolean;
  chartTimeLoss: boolean;
  chartLatG: boolean;
  chartGg: boolean;
  chartGrip: boolean;
  chartLongG: boolean;
  chartBalance: boolean;
  chartBeta: boolean;
  chartYaw: boolean;
  chartWheelLoad: boolean;
  chartSuspension: boolean;
  chartPhase: boolean;
  chartBrake: boolean;
  chartThrottle: boolean;
  chartSteer: boolean;
  chartDelta: boolean;
  setupPanel: boolean;
}

export const defaultLayers: LayerState = {
  mapTarmac: true,
  mapLines: true,
  mapCorners: true,
  corrections: true,
  opportunities: true,
  setup: true,
  surface: true,
  coach: true,
  chartSpeed: true,
  chartTimeLoss: false,
  chartLatG: true,
  chartGg: false,
  chartGrip: false,
  chartLongG: false,
  chartBalance: false,
  chartBeta: false,
  chartYaw: false,
  chartWheelLoad: false,
  chartSuspension: false,
  chartPhase: false,
  chartBrake: true,
  chartThrottle: true,
  chartSteer: true,
  chartDelta: true,
  setupPanel: true,
};
