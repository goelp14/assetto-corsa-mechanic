import type { Annotation, CornerTimeLoss } from "../types";
import { formatEvidence } from "../utils/formatEvidence";
import { filterNarrativeByCorner } from "../utils/filterNarrative";

interface Props {
  annotation: Annotation | null;
  narrative?: string | null;
  narrativeSections?: { corner_id?: string; heading: string; body: string }[];
  cornerId?: string | null;
  cornerDisplay?: string;
  timeLossCorner?: CornerTimeLoss;
  sessionPlanDrill?: string;
  viewMode?: "guided" | "explore";
  onClearSelection?: () => void;
}

function renderMarkdownLite(text: string) {
  return text
    .split("\n")
    .map((line, i) => {
      if (line.startsWith("### ")) {
        return (
          <h4 key={i} style={{ color: "#e2e8f0", margin: "12px 0 4px", fontSize: 13 }}>
            {line.slice(4)}
          </h4>
        );
      }
      if (line.startsWith("## ")) {
        return (
          <h3 key={i} style={{ color: "#f1f5f9", margin: "16px 0 6px", fontSize: 14 }}>
            {line.slice(3)}
          </h3>
        );
      }
      if (line.startsWith("# ")) {
        return (
          <h2 key={i} style={{ color: "#f8fafc", margin: "0 0 10px", fontSize: 15 }}>
            {line.slice(2)}
          </h2>
        );
      }
      if (line.startsWith("**") && line.includes(":**")) {
        const idx = line.indexOf(":**");
        const label = line.slice(2, idx);
        const body = line.slice(idx + 3).replace(/\*\*/g, "");
        return (
          <p key={i} style={{ margin: "4px 0", fontSize: 13, color: "#cbd5e1" }}>
            <strong style={{ color: "#94a3b8" }}>{label}:</strong> {body}
          </p>
        );
      }
      if (line.startsWith("---"))
        return (
          <hr key={i} style={{ border: "none", borderTop: "1px solid #334155", margin: "12px 0" }} />
        );
      if (!line.trim()) return <div key={i} style={{ height: 6 }} />;
      return (
        <p key={i} style={{ margin: "4px 0", fontSize: 13, color: "#cbd5e1", lineHeight: 1.45 }}>
          {line.replace(/\*\*/g, "")}
        </p>
      );
    });
}

export function Inspector({
  annotation,
  narrative,
  narrativeSections,
  cornerId,
  cornerDisplay,
  timeLossCorner,
  sessionPlanDrill,
  viewMode = "guided",
  onClearSelection,
}: Props) {
  const tabColor =
    annotation?.category === "opportunity"
      ? "#06b6d4"
      : annotation?.category === "setup"
        ? "#a855f7"
        : annotation?.category === "coach"
          ? "#38bdf8"
          : "#f97316";

  const filteredNarrative = narrative
    ? filterNarrativeByCorner(narrative, cornerId, cornerDisplay, narrativeSections)
    : null;

  const drillLine =
    annotation?.action ||
    timeLossCorner?.primary_action ||
    timeLossCorner?.fixes?.[0]?.action ||
    sessionPlanDrill ||
    null;

  const evidenceRows = annotation?.evidence ? formatEvidence(annotation.evidence) : [];

  return (
    <div className="inspector" style={{ padding: 16, overflow: "auto", height: "100%" }}>
      {(cornerId || annotation) && onClearSelection && (
        <button
          type="button"
          className="inspector-clear"
          onClick={onClearSelection}
          style={{ marginBottom: 12, fontSize: 11, padding: "4px 10px" }}
        >
          Clear selection
        </button>
      )}

      {drillLine && (
        <section className="inspector-drill">
          <h4>Next session drill</h4>
          <p>{drillLine}</p>
        </section>
      )}

      {annotation ? (
        <>
          {viewMode === "explore" && (
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <span
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 4,
                  background: tabColor,
                  color: "#0f172a",
                  textTransform: "uppercase",
                }}
              >
                {annotation.category}
              </span>
              {annotation.subtype && (
                <span style={{ fontSize: 11, color: "#64748b" }}>{annotation.subtype}</span>
              )}
            </div>
          )}
          <h3 style={{ margin: "0 0 8px", color: "#f1f5f9" }}>
            {annotation.corner_display || cornerDisplay || annotation.corner || annotation.title}
          </h3>
          {annotation.title && (
            <p style={{ color: "#cbd5e1", fontWeight: 600, fontSize: 14 }}>{annotation.title}</p>
          )}
          {annotation.what && (
            <section style={{ marginTop: 12 }}>
              <h4 style={{ color: "#94a3b8", margin: "0 0 4px", fontSize: 11 }}>WHAT</h4>
              <p style={{ color: "#e2e8f0", margin: 0, fontSize: 14 }}>{annotation.what}</p>
            </section>
          )}
          {annotation.why && (
            <section style={{ marginTop: 12 }}>
              <h4 style={{ color: "#94a3b8", margin: "0 0 4px", fontSize: 11 }}>WHY</h4>
              <p style={{ color: "#e2e8f0", margin: 0, fontSize: 14 }}>{annotation.why}</p>
            </section>
          )}
          {annotation.action && (
            <section style={{ marginTop: 12 }}>
              <h4 style={{ color: "#94a3b8", margin: "0 0 4px", fontSize: 11 }}>HOW</h4>
              <p style={{ color: "#22c55e", margin: 0, fontSize: 14 }}>{annotation.action}</p>
            </section>
          )}
          {evidenceRows.length > 0 && (
            <section style={{ marginTop: 16 }}>
              <h4 style={{ color: "#94a3b8", margin: "0 0 8px", fontSize: 11 }}>Evidence</h4>
              <dl className="evidence-list">
                {evidenceRows.map((row) => (
                  <div key={row.label} className={row.emphasis ? "evidence-row emphasis" : "evidence-row"}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
        </>
      ) : cornerDisplay ? (
        <>
          <h3 style={{ margin: "0 0 8px", color: "#e2e8f0" }}>{cornerDisplay}</h3>
          <p style={{ color: "#64748b", fontSize: 13, margin: "0 0 12px" }}>
            Corner selected — debrief below is filtered to this corner. Click a map pin or chart
            highlight for specific coaching notes.
          </p>
        </>
      ) : (
        <>
          <h3 style={{ margin: "0 0 8px", color: "#e2e8f0" }}>Stint debrief</h3>
          <p style={{ color: "#64748b", fontSize: 13, margin: "0 0 12px" }}>
            Click a highlighted region on the charts or a map pin for corner-specific coaching.
            Drag across a chart to zoom telemetry; use Reset zoom to widen again.
          </p>
        </>
      )}

      {filteredNarrative && (
        <section
          style={{
            marginTop: annotation || cornerDisplay ? 20 : 0,
            borderTop: annotation || cornerDisplay ? "1px solid #334155" : undefined,
            paddingTop: annotation || cornerDisplay ? 16 : 0,
          }}
        >
          {cornerDisplay && !annotation && (
            <h4 style={{ color: "#94a3b8", margin: "0 0 8px", fontSize: 11 }}>
              Debrief for {cornerDisplay}
            </h4>
          )}
          {renderMarkdownLite(filteredNarrative)}
        </section>
      )}
    </div>
  );
}
