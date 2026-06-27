const LABELS: Record<string, string> = {
  peak_ay_g: "Peak lateral G",
  max_throttle_pct: "Max throttle",
  min_speed_kmh: "Min speed",
  ref_min_speed_kmh: "Reference min speed",
  speed_gap_kmh: "Speed gap vs reference",
  mean_brake: "Average brake",
  corrections: "Steering corrections",
  ref_corrections: "Reference corrections",
  phase_upper: "Corner phase",
  root_cause_id: "Root cause",
  root_cause_label: "Root cause",
  line_hint: "Line hint",
  input_throttle: "Throttle technique",
  input_brake: "Brake technique",
  input_steer: "Steering technique",
  evidence_point: "Key observation",
  mechanism: "Why it costs time",
  detection_what: "Detected",
  detection_why: "Why setup",
  detected_corner_display: "Corner",
  detected_phase: "Phase",
  active_from_lap: "Active from lap",
  active_to_lap: "Active until lap",
  applied_lap: "Applied lap",
  applied_at_pit: "Applied in pits",
  effectiveness: "Effectiveness",
  lap_time_delta_ms: "Lap time delta (ms)",
  input_score: "Input score",
  output_score: "Balance score",
  corner_delta_s: "Corner time cost (s)",
  verdict: "Verdict",
  symptom: "Symptom",
  status: "Outcome",
};

const SKIP = new Set(["root_cause_id"]);

function humanizeKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export interface EvidenceRow {
  label: string;
  value: string;
  emphasis?: boolean;
}

export function formatEvidence(evidence: Record<string, unknown>): EvidenceRow[] {
  const order = [
    "detection_what",
    "detection_why",
    "detected_corner_display",
    "detected_phase",
    "verdict",
    "input_score",
    "output_score",
    "corner_delta_s",
    "active_from_lap",
    "active_to_lap",
    "applied_lap",
    "effectiveness",
    "lap_time_delta_ms",
    "status",
    "evidence_point",
    "root_cause_label",
    "mechanism",
    "fix_action",
    "expected_outcome",
    "min_speed_kmh",
    "ref_min_speed_kmh",
    "speed_gap_kmh",
    "peak_ay_g",
    "mean_brake",
    "max_throttle_pct",
    "corrections",
    "ref_corrections",
    "phase_upper",
    "line_hint",
    "input_brake",
    "input_throttle",
    "input_steer",
  ];

  const rows: EvidenceRow[] = [];
  const seen = new Set<string>();

  for (const key of order) {
    if (SKIP.has(key)) continue;
    const val = evidence[key];
    if (val == null || val === "") continue;
    seen.add(key);
    rows.push({
      label: LABELS[key] ?? humanizeKey(key),
      value: String(val),
      emphasis: key === "evidence_point" || key === "fix_action",
    });
  }

  for (const [key, val] of Object.entries(evidence)) {
    if (seen.has(key) || SKIP.has(key) || val == null || val === "") continue;
    rows.push({
      label: LABELS[key] ?? humanizeKey(key),
      value: typeof val === "object" ? JSON.stringify(val) : String(val),
    });
  }

  return rows;
}
