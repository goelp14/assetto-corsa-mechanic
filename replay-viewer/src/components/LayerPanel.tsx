import type { ChannelAvailability, LayerState } from "../types";

interface Props {
  layers: LayerState;
  availability: ChannelAvailability;
  onChange: (layers: LayerState) => void;
  compact?: boolean;
}

function Toggle({
  label,
  checked,
  disabled,
  hint,
  onToggle,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  hint?: string;
  onToggle: () => void;
}) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontSize: 12,
        color: disabled ? "#475569" : "#cbd5e1",
        cursor: disabled ? "not-allowed" : "pointer",
      }}
      title={hint}
    >
      <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
      {label}
    </label>
  );
}

function Section({ title }: { title: string }) {
  return (
    <div style={{ fontSize: 10, color: "#64748b", marginTop: 6, textTransform: "uppercase" }}>
      {title}
    </div>
  );
}

export function LayerPanel({ layers, availability, onChange, compact }: Props) {
  const set = (key: keyof LayerState, val: boolean) => onChange({ ...layers, [key]: val });

  return (
    <div
      className="layer-panel"
      style={{
        padding: compact ? 8 : 12,
        background: "#1e293b",
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        gap: 4,
        minWidth: compact ? 140 : 168,
        maxHeight: compact ? "40vh" : "calc(100vh - 120px)",
        overflowY: "auto",
      }}
    >
      <strong style={{ color: "#e2e8f0", fontSize: 13 }}>Layers</strong>

      <Section title="Session" />
      <Toggle label="Tarmac" checked={layers.mapTarmac} onToggle={() => set("mapTarmac", !layers.mapTarmac)} />
      <Toggle label="Racing lines" checked={layers.mapLines} onToggle={() => set("mapLines", !layers.mapLines)} />
      <Toggle label="Corner labels" checked={layers.mapCorners} onToggle={() => set("mapCorners", !layers.mapCorners)} />
      <Toggle label="Corrections" checked={layers.corrections} onToggle={() => set("corrections", !layers.corrections)} />
      <Toggle label="Opportunities" checked={layers.opportunities} onToggle={() => set("opportunities", !layers.opportunities)} />
      <Toggle label="Setup" checked={layers.setup} onToggle={() => set("setup", !layers.setup)} />
      <Toggle label="Coach notes" checked={layers.coach} onToggle={() => set("coach", !layers.coach)} />

      <Section title="Analysis" />
      <Toggle label="Speed" checked={layers.chartSpeed} onToggle={() => set("chartSpeed", !layers.chartSpeed)} />
      <Toggle label="Brake" checked={layers.chartBrake} onToggle={() => set("chartBrake", !layers.chartBrake)} />
      <Toggle label="Throttle" checked={layers.chartThrottle} onToggle={() => set("chartThrottle", !layers.chartThrottle)} />
      <Toggle label="Steering" checked={layers.chartSteer} onToggle={() => set("chartSteer", !layers.chartSteer)} />
      <Toggle
        label="Lat G"
        checked={layers.chartLatG}
        disabled={!availability.acc_g_lat}
        hint="Lateral acceleration line"
        onToggle={() => set("chartLatG", !layers.chartLatG)}
      />
      <Toggle label="Compare Δt" checked={layers.chartDelta} onToggle={() => set("chartDelta", !layers.chartDelta)} />
      <Toggle
        label="Phase bands"
        checked={layers.chartPhase}
        disabled={!availability.phase}
        hint="Entry / mid / exit shading"
        onToggle={() => set("chartPhase", !layers.chartPhase)}
      />
      <Toggle
        label="Time loss map"
        checked={layers.chartTimeLoss}
        disabled={!availability.time_loss}
        hint="Where your stitched best time is"
        onToggle={() => set("chartTimeLoss", !layers.chartTimeLoss)}
      />
      <Toggle
        label="G-G diagram"
        checked={layers.chartGg}
        disabled={!availability.acc_g_long || !availability.gg_envelope}
        hint="Friction circle + grip readout"
        onToggle={() => set("chartGg", !layers.chartGg)}
      />
      <Toggle
        label="Grip %"
        checked={layers.chartGrip}
        disabled={!availability.gg_envelope}
        hint="% of personal lateral-G limit"
        onToggle={() => set("chartGrip", !layers.chartGrip)}
      />

      <Section title="Chassis" />
      <Toggle
        label="Long G"
        checked={layers.chartLongG}
        disabled={!availability.acc_g_long}
        onToggle={() => set("chartLongG", !layers.chartLongG)}
      />
      <Toggle
        label="Balance δᵤₛ"
        checked={layers.chartBalance}
        disabled={!availability.delta_us_deg}
        hint="Understeer / oversteer gradient"
        onToggle={() => set("chartBalance", !layers.chartBalance)}
      />
      <Toggle
        label="Slip angle β"
        checked={layers.chartBeta}
        disabled={!availability.beta_deg}
        onToggle={() => set("chartBeta", !layers.chartBeta)}
      />
      <Toggle
        label="Yaw rate"
        checked={layers.chartYaw}
        disabled={!availability.yaw_rate}
        onToggle={() => set("chartYaw", !layers.chartYaw)}
      />
      <Toggle
        label="Wheel load"
        checked={layers.chartWheelLoad}
        disabled={!availability.wheel_load}
        onToggle={() => set("chartWheelLoad", !layers.chartWheelLoad)}
      />
      <Toggle
        label="Suspension"
        checked={layers.chartSuspension}
        disabled={!availability.susp_ratio}
        onToggle={() => set("chartSuspension", !layers.chartSuspension)}
      />
    </div>
  );
}
