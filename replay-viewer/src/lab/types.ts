// Lap Studio bundle types (schema vre.replay_bundle.acc.v2, written by external/query_tools/acc_replay_bundle.py).

export const LAB_SCHEMA = "vre.replay_bundle.acc.v2";

export interface LapRow {
  lap_index: number;
  lap_ms: number;
  valid: boolean | null;
  flying: boolean | null;
  partial: boolean | null;
  sync_ok: boolean | null;
  frames: string;
}

export interface DriverMeta {
  label: string;
  role: "me" | "ref";
  identity: Record<string, unknown>;
  car: { car_index?: number; is_player?: boolean } | null;
  best_lap_index: number | null;
  laps: LapRow[];
  sync: Record<string, unknown>;
  pose_hz: number;
}

export interface LabManifest {
  schema: string;
  session_id: string;
  game: "acc";
  track_id: string;
  track_display: string;
  car_id: string | null;
  track_length_m: number;
  best_lap_ms: number | null;
  created: string;
  drivers: DriverMeta[];
  files: Record<string, string>;
}

/** Columnar per-lap frames (vre.acc_rpy.lap_frames.v1). t is seconds from the lap's S/F crossing. */
export interface LapFrames {
  t: number[];
  s_m: number[];
  lat_m: number[];
  x: number[];
  y: number[];
  z: number[];
  yaw_deg: number[];
  course_deg: number[];
  slip_deg: (number | null)[];
  speed_kmh: number[];
  throttle: number[];
  brake: number[];
  steer_deg: number[];
  rpm: number[];
  g_lat: number[];
  g_lon: number[];
  g_vert: number[];
  gear: number[];
  edge_all4_left_m?: number[];
  edge_all4_right_m?: number[];
  predicted_lap_ms?: (number | null)[];
  lap_valid_so_far?: number[];
  tyre_load?: Record<string, number[]>;
  slip_ratio?: Record<string, (number | null)[]>;
  meta: {
    lap_index: number;
    lap_ms: number;
    valid: boolean | null;
    partial?: boolean;
    pose_hz: number;
    wheel_body_m?: [number, number][];
    sync?: Record<string, unknown>;
    [k: string]: unknown;
  };
}

export interface CornerWindow {
  corner: string;
  index: number;
  s0_m: number;
  s1_m: number;
  apex_m: number;
  direction: string;
  inside_edge: string;
  braked: boolean;
  speed_class: string;
}

export interface CornerEvent {
  lap_index: number;
  ok: boolean;
  section_time_s?: number;
  vmin_kmh?: number;
  vmin_m?: number;
  brake_on_m?: number | null;
  brake_on_kmh?: number | null;
  brake_full_m?: number | null;
  brake_ramp_m?: number | null;
  brake_off_m?: number | null;
  turn_in_m?: number | null;
  turn_in_kmh?: number | null;
  throttle_on_m?: number | null;
  full_throttle_m?: number | null;
  full_throttle_kmh?: number | null;
  coast_s?: number | null;
  peak_slip_deg?: number | null;
  decel_peak_g?: number | null;
  brake_at_turn_in?: number | null;
  rebrake_peak?: number | null;
  terrain?: { kind: string; at_m: number; expected_dg: number; brake: number; throttle: number; speed_kmh: number }[];
  [k: string]: unknown;
}

export interface CornerStats {
  laps: CornerEvent[];
  best_lap?: CornerEvent;
  consistency?: Record<string, { median: number; iqr: number; n: number; r_with_time: number | null; matters: boolean }>;
}

export interface DriverAnalysis {
  lap_ms: number[];
  best_lap_ms: number;
  theoretical: { ok: boolean; theoretical_best_s?: number; best_lap_s?: number; potential_s?: number; laps_used?: number };
  corners: Record<string, CornerStats>;
}

export interface PackCorner {
  start_m: number;
  end_m: number;
  apex_m: number;
  turn_deg: number;
  min_radius_m: number;
  speed_class: string;
  direction: string;
  name: string;
  display_name: string;
  notes?: { type?: string; cues?: string[]; priority?: string } | null;
}

export interface Terrain {
  kind: string;
  start_m: number;
  end_m: number;
  peak_m: number;
  dg_at_100kmh: number;
  grade_pct: number;
}

export interface Analysis {
  ok: boolean;
  length_m: number;
  windows: CornerWindow[];
  drivers: Record<string, DriverAnalysis>;
  delta_best_vs_ref?: { step_m: number; delta_s: number[]; final_s: number };
  variance_cliffs: { s0_m: number; s1_m: number; loss_s: number }[];
  corner_loss_best_vs_ref: { corner: string; index: number; loss_s: number }[];
  car_state: Record<string, Record<string, number | string | null>>;
  pack: { corners: PackCorner[]; terrain: Terrain[]; sf_offset_m: number; notes?: { hotspots?: unknown[]; sources?: string[] } | null };
  labels: { me: string; ref: string | null };
}

export interface Fix {
  id: string;
  corner: string;
  corner_key: string;
  title: string;
  belief: string;
  correct_model: string;
  why: string;
  what: Record<string, unknown>;
  drill: string;
  success_metric: string;
  cues: string[];
  physics: unknown[];
  pace_impact_s: number;
  corner_loss_s: number | null;
  repeats: number;
  corners_with_habit: string[];
  confidence: string;
}

export interface Habit {
  id: string;
  group: string;
  title: string;
  detail: string;
  polarity: "strength" | "weakness" | string;
  instances: { corner: string; key: string; evidence: Record<string, unknown>; loss_s?: number }[];
  pace_impact_s: number;
  corners: string[];
  repeats: number;
}

export interface Coaching {
  driver: string;
  reference: string | null;
  fixes: Fix[];
  later: Fix[];
  strengths: unknown[];
  setup_checks: Record<string, unknown>[];
  habits: { habits: Habit[] };
  diagnosis: {
    corners: { corner: string; loss_s: number; cause: string; habits: string[] }[];
    setup_recommendations: { lever: string; direction: string; why: string; test: string; expect: string }[];
    order: string;
  };
  persistent_habits: { id: string; where: string[] }[];
}

export interface Estimated {
  value: number;
  spread: number | null;
  laps: number;
  status: string;
  unit: string;
  note: string;
}

export interface Fingerprint {
  exact: {
    kmh_per_1000rpm_by_gear?: Record<string, number>;
    tyre_radius_m?: Record<string, number>;
    static_mass_kg?: number;
    static_front_share?: number;
  };
  estimated: Record<string, Estimated>;
}

export interface SetupData {
  label: string;
  fingerprint: Fingerprint;
  reference?: { label: string; fingerprint: Fingerprint };
  comparison?: { item: string; difference: number; noise: number; verdict: string; likely_levers: string | null; status: string; [label: string]: unknown }[];
  library_candidates?: { name: string; physical: Record<string, unknown>; values: Record<string, unknown> }[];
}

export interface Excursion {
  side: string;
  s0_m: number;
  s1_m: number;
  peak_s_m: number;
  all4_peak_m: number;
  any_peak_m: number;
  all4: boolean;
  status: string;
}

export interface LimitsLap {
  lap_index: number;
  lap_ms: number;
  valid: boolean | null;
  cut: { cut_m: number | null; drop_m: number; side?: string; judged_after_s?: number; confidence: string; method: string } | null;
  excursions: Excursion[];
}

export interface Limits {
  zones: { drop_m: number; cut_m: number; laps: number; lag_s_median: number }[];
  envelope?: { bin_m: number; left: number[]; right: number[]; note: string };
  drivers: { label: string; laps: LimitsLap[] }[];
  notes: string[];
  error?: string;
}

export interface TrackData {
  track_id: string;
  length_m: number;
  sf_offset_m: number;
  corners: PackCorner[];
  terrain: Terrain[];
  centerline?: [number, number][];
  left?: [number, number][];
  right?: [number, number][];
}

export type OverlayKind = "pin" | "zone" | "arrow" | "text" | "line";

export interface Overlay {
  kind: OverlayKind;
  at_m?: number;
  s0_m?: number;
  s1_m?: number;
  driver?: "me" | "ref";
  text?: string;
  color?: string;
}

export interface Annotation extends Overlay {
  id?: string;
  author?: string;
  created?: string;
}

export interface Scene {
  title: string;
  corner_key?: string;
  s0_m: number;
  s1_m: number;
  mode?: "dist" | "time";
  rate?: number;
  laps?: { me?: string | number; ref?: string | number };
  narration?: string;
  pauses?: { at_m: number; text: string; driver?: string }[];
  overlays?: Overlay[];
  lanes?: string[];
  citations?: string[];
  author?: string;
}

export interface Review {
  schema: "vre.review.v1";
  title: string;
  author?: string;
  scenes: Scene[];
  note?: string;
}

export interface LabBundle {
  base: string;
  manifest: LabManifest;
  analysis: Analysis | null;
  coaching: Coaching | null;
  setup: SetupData | null;
  limits: Limits | null;
  track: TrackData | null;
  annotations: Annotation[];
  reviews: string[];
}

/** A lap chosen into slot A (primary) or B (comparison). */
export interface Slot {
  driver: string;
  lap: number;
}
