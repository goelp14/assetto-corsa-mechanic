interface Props {
  potentialGapS: number;
  bestLapMs?: number;
  theoreticalBestMs?: number;
  lapTimeMs?: number;
  lapLabel?: string;
}

export function KpiStrip({
  potentialGapS,
  bestLapMs,
  theoreticalBestMs,
  lapTimeMs,
  lapLabel,
}: Props) {
  return (
    <div className="kpi-strip">
      <div className="kpi-item">
        <span className="kpi-label">Potential gap</span>
        <span className="kpi-value accent">{potentialGapS.toFixed(2)}s</span>
      </div>
      {bestLapMs != null && (
        <div className="kpi-item">
          <span className="kpi-label">Best lap</span>
          <span className="kpi-value">{(bestLapMs / 1000).toFixed(3)}s</span>
        </div>
      )}
      {theoreticalBestMs != null && (
        <div className="kpi-item">
          <span className="kpi-label">Theoretical</span>
          <span className="kpi-value">{(theoreticalBestMs / 1000).toFixed(3)}s</span>
        </div>
      )}
      {lapTimeMs != null && (
        <div className="kpi-item">
          <span className="kpi-label">{lapLabel ?? "This lap"}</span>
          <span className="kpi-value">{(lapTimeMs / 1000).toFixed(3)}s</span>
        </div>
      )}
    </div>
  );
}
