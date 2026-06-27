import type { CornerTimeLoss } from "../types";
import { formatCornerCoaching } from "../utils/formatCoachDrill";

interface Props {
  potentialGapS: number;
  theoreticalBestMs?: number;
  lapTimeMs?: number;
  corners: CornerTimeLoss[];
  onSelectCorner: (corner: CornerTimeLoss) => void;
}

export function TimeLossPanel({
  potentialGapS,
  theoreticalBestMs,
  lapTimeMs,
  corners,
  onSelectCorner,
}: Props) {
  if (potentialGapS <= 0 || !corners.length) return null;

  const accounted = corners.reduce((s, c) => s + c.loss_s, 0);

  return (
    <div
      style={{
        background: "#1e293b",
        borderRadius: 8,
        padding: 12,
        marginBottom: 10,
        border: "1px solid #334155",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "#f8fafc" }}>
            {potentialGapS.toFixed(2)}s gap vs your stitched best
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
            Stitched best{" "}
            {theoreticalBestMs ? (theoreticalBestMs / 1000).toFixed(3) : "—"}s
            {lapTimeMs ? <> · this lap {(lapTimeMs / 1000).toFixed(3)}s</> : null}
            {" · "}
            {accounted.toFixed(2)}s mapped to corners below
          </div>
        </div>
        <div style={{ fontSize: 10, color: "#64748b", alignSelf: "center" }}>
          Click a row to zoom · orange bands = time lost
        </div>
      </div>

      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4 }}>
        {corners.slice(0, 8).map((c) => {
          const { issue, drill } = formatCornerCoaching(c);
          return (
            <button
              key={c.corner}
              type="button"
              onClick={() => onSelectCorner(c)}
              style={{
                display: "grid",
                gridTemplateColumns: "72px 1fr",
                gap: 8,
                alignItems: "start",
                textAlign: "left",
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 6,
                padding: "8px 10px",
                cursor: "pointer",
                color: "#e2e8f0",
              }}
            >
              <span style={{ color: "#fb923c", fontWeight: 700, fontSize: 13 }}>
                +{c.loss_s.toFixed(2)}s
              </span>
              <span>
                <span style={{ fontSize: 12, fontWeight: 600 }}>{c.corner_display}</span>
                {issue && (
                  <span style={{ display: "block", fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                    {issue}
                  </span>
                )}
                <span style={{ display: "block", fontSize: 11, color: "#22c55e", marginTop: 4 }}>
                  {drill}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
