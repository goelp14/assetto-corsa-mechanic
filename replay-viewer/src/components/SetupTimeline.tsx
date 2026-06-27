import type { SetupEpisode } from "../types";

interface Props {
  episodes: SetupEpisode[];
  visible: boolean;
  activeLap?: number;
  onSelectEpisode?: (episode: SetupEpisode) => void;
}

function fmtMs(ms: number | null | undefined) {
  if (!ms) return "—";
  return (ms / 1000).toFixed(3) + "s";
}

function statusColor(status?: string) {
  if (status === "confirmed") return "#22c55e";
  if (status === "reverted") return "#ef4444";
  if (status === "queued_only") return "#64748b";
  return "#a855f7";
}

export function SetupTimeline({ episodes, visible, activeLap, onSelectEpisode }: Props) {
  if (!visible) return null;
  if (!episodes.length) {
    return (
      <div style={{ padding: 12, color: "#64748b", borderTop: "1px solid #334155" }}>
        No setup changes this stint.
      </div>
    );
  }

  return (
    <div
      style={{
        borderTop: "1px solid #334155",
        padding: 12,
        background: "#0f172a",
        overflowX: "auto",
      }}
    >
      <h4 style={{ margin: "0 0 8px", color: "#e2e8f0" }}>Setup engineering</h4>
      <p style={{ margin: "0 0 12px", fontSize: 12, color: "#64748b" }}>
        Click a card to jump to where it was detected on track and inspect telemetry.
      </p>
      <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
        {episodes.map((ep) => {
          const delta =
            ep.avg_lap_before_ms && ep.avg_lap_after_ms
              ? (ep.avg_lap_after_ms - ep.avg_lap_before_ms) / 1000
              : null;
          const isActive =
            ep.active_from_lap != null &&
            activeLap != null &&
            activeLap >= ep.active_from_lap &&
            (ep.active_to_lap == null || activeLap <= ep.active_to_lap);
          const activeRange =
            ep.active_from_lap == null
              ? "Queued — applies on pit entry"
              : ep.active_to_lap != null && ep.active_to_lap > ep.active_from_lap
                ? `Tweak live on laps ${ep.active_from_lap}–${ep.active_to_lap}`
                : `Tweak live from lap ${ep.active_from_lap}`;

          return (
            <button
              key={ep.episode_id}
              type="button"
              onClick={() => onSelectEpisode?.(ep)}
              style={{
                minWidth: 260,
                maxWidth: 320,
                padding: 12,
                background: isActive ? "#1e293b" : "#172033",
                borderRadius: 8,
                border: isActive ? "1px solid #a855f7" : "1px solid #334155",
                borderLeft: `4px solid ${statusColor(ep.status)}`,
                textAlign: "left",
                cursor: onSelectEpisode ? "pointer" : "default",
                color: "inherit",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ fontSize: 11, color: "#94a3b8", textTransform: "uppercase" }}>
                  {ep.status?.replace("_", " ") ?? "setup"}
                </span>
                {ep.detected_lap != null && (
                  <span style={{ fontSize: 11, color: "#64748b" }}>detected L{ep.detected_lap}</span>
                )}
              </div>
              <div style={{ color: "#f1f5f9", fontWeight: 600, marginTop: 4 }}>
                {ep.parameter_display || ep.parameter}
              </div>
              <div style={{ fontSize: 12, color: "#cbd5e1", marginTop: 2 }}>
                {String(ep.old_value)} → {String(ep.new_value)}
                {ep.delta != null && (
                  <span style={{ color: "#94a3b8" }}>
                    {" "}
                    ({ep.delta >= 0 ? "+" : ""}
                    {ep.delta})
                  </span>
                )}
              </div>

              {ep.detection_what && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 10, color: "#64748b", letterSpacing: 0.5 }}>DETECTED</div>
                  <div style={{ fontSize: 12, color: "#e2e8f0", marginTop: 2 }}>{ep.detection_what}</div>
                </div>
              )}
              {ep.detection_why && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ fontSize: 10, color: "#64748b", letterSpacing: 0.5 }}>WHY SETUP</div>
                  <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2, lineHeight: 1.4 }}>
                    {ep.detection_why}
                  </div>
                </div>
              )}

              {(ep.input_score != null || ep.output_score != null) && (
                <div style={{ fontSize: 11, color: "#64748b", marginTop: 6 }}>
                  Input {ep.input_score?.toFixed(2) ?? "—"} · Balance {ep.output_score?.toFixed(2) ?? "—"}
                  {ep.corner_delta_s != null && ep.corner_delta_s >= 0.01 && (
                    <span> · +{ep.corner_delta_s.toFixed(2)}s</span>
                  )}
                </div>
              )}

              <div style={{ fontSize: 11, marginTop: 8, color: isActive ? "#c4b5fd" : "#64748b" }}>
                {activeRange}
                {ep.applied_at_pit && ep.applied_lap != null && (
                  <span> · applied in pits L{ep.applied_lap}</span>
                )}
              </div>

              {delta != null && (
                <div style={{ fontSize: 11, marginTop: 6, color: "#94a3b8" }}>
                  Stint pace {fmtMs(ep.avg_lap_before_ms)} → {fmtMs(ep.avg_lap_after_ms)}
                  <span style={{ color: delta < 0 ? "#22c55e" : "#ef4444" }}>
                    {" "}
                    ({delta > 0 ? "+" : ""}
                    {delta.toFixed(3)}s)
                  </span>
                </div>
              )}

              {ep.effectiveness != null && (
                <div style={{ fontSize: 11, marginTop: 4, color: "#94a3b8" }}>
                  Eval L{ep.evaluation_lap}: effectiveness {ep.effectiveness.toFixed(2)}
                  {ep.lap_time_delta_ms != null && (
                    <span>
                      {" "}
                      ({ep.lap_time_delta_ms > 0 ? "+" : ""}
                      {(ep.lap_time_delta_ms / 1000).toFixed(3)}s)
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
