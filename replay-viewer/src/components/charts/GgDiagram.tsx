import { useMemo } from "react";
import type { EnrichedSample } from "../../utils/telemetryDerived";
import {
  decimateSeries,
  filterBySplineRange,
  gripLeftPct,
  gripUsage,
  gripUsageColor,
  indexAtSpline,
  peakAyAtSpeed,
  sessionPeakAy,
} from "../../utils/telemetryDerived";

interface Props {
  samples: EnrichedSample[];
  compareSamples?: EnrichedSample[];
  playheadSpline: number;
  viewRange?: [number, number] | null;
  peakAy?: number[];
  onSplineChange: (spline: number) => void;
}

const PAD = 36;

function toXY(ax: number, ay: number, gMax: number, size: number) {
  const plot = size - PAD * 2;
  const cx = PAD + ((ax + gMax) / (gMax * 2)) * plot;
  const cy = PAD + ((gMax - ay) / (gMax * 2)) * plot;
  return { x: cx, y: cy };
}

function usageArcPath(
  cx: number,
  cy: number,
  r: number,
  usage: number,
): string {
  const angle = Math.min(usage, 1.5) * Math.PI * 0.5;
  const x1 = cx + r * Math.sin(angle);
  const y1 = cy - r * Math.cos(angle);
  const large = angle > Math.PI * 0.5 ? 1 : 0;
  if (usage <= 0.01) return "";
  return `M ${cx} ${cy - r} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} L ${cx} ${cy} Z`;
}

export function GgDiagram({
  samples,
  compareSamples,
  playheadSpline,
  viewRange,
  peakAy,
  onSplineChange,
}: Props) {
  const zoomed = viewRange != null;
  const visible = useMemo(
    () => filterBySplineRange(samples, viewRange),
    [samples, viewRange],
  );
  const display = useMemo(
    () => decimateSeries(visible, zoomed ? 120 : 48),
    [visible, zoomed],
  );

  const playIdx = indexAtSpline(samples, playheadSpline);
  const play = samples[playIdx];
  const speed = play?.speed_kmh ?? 120;
  const gripLimit = peakAy?.length ? peakAyAtSpeed(peakAy, speed) : 2.2;
  const sessionPeak = peakAy?.length ? sessionPeakAy(peakAy) : 2.4;
  const usage = peakAy?.length && play
    ? gripUsage(peakAy, play.speed_kmh, play.acc_g_lat)
    : 0;
  const leftPct = gripLeftPct(usage);

  const gMax = useMemo(() => {
    const vals = visible.flatMap((s) => [
      Math.abs(s.acc_g_lat),
      Math.abs(s.acc_g_long),
      gripLimit,
      sessionPeak,
    ]);
    return Math.max(1.2, Math.min(3.2, Math.ceil(Math.max(...vals, 1.5) * 10) / 10));
  }, [visible, gripLimit, sessionPeak]);

  const size = zoomed ? 300 : 240;

  const center = toXY(0, 0, gMax, size);
  const rLimit = ((gripLimit / gMax) * (size - PAD * 2)) / 2;
  const rPeak = ((sessionPeak / gMax) * (size - PAD * 2)) / 2;
  const rTargetLo = rLimit * 0.85;
  const rTargetHi = rLimit * 0.92;

  const trailPoints = display
    .map((s) => {
      const p = toXY(s.acc_g_long, s.acc_g_lat, gMax, size);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    })
    .join(" ");

  const handlePick = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * size;
    const my = ((e.clientY - rect.top) / rect.height) * size;
    let best = samples[0]?.spline ?? 0;
    let bestD = Infinity;
    for (const s of display) {
      const p = toXY(s.acc_g_long, s.acc_g_lat, gMax, size);
      const d = (p.x - mx) ** 2 + (p.y - my) ** 2;
      if (d < bestD) {
        bestD = d;
        best = s.spline;
      }
    }
    onSplineChange(best);
  };

  const usagePct = Math.round(usage * 100);
  const usageColor = gripUsageColor(usage);

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 11, color: "#94a3b8", margin: "0 0 4px 4px" }}>
        G-G diagram {zoomed ? "(zoomed region)" : "(full lap)"} · line colour = grip usage
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          style={{
            background: "#0f172a",
            borderRadius: 8,
            cursor: "crosshair",
            flex: "0 0 auto",
          }}
          onMouseMove={handlePick}
          onClick={handlePick}
        >
          <line x1={PAD} y1={center.y} x2={size - PAD} y2={center.y} stroke="#334155" strokeWidth={1} />
          <line x1={center.x} y1={PAD} x2={center.x} y2={size - PAD} stroke="#334155" strokeWidth={1} />

          {/* session peak envelope */}
          <circle
            cx={center.x}
            cy={center.y}
            r={rPeak}
            fill="none"
            stroke="#475569"
            strokeWidth={1}
            strokeDasharray="6 4"
            opacity={0.6}
          />
          {/* target band 85–92% at current speed */}
          <circle
            cx={center.x}
            cy={center.y}
            r={rTargetHi}
            fill="none"
            stroke="#22c55e"
            strokeWidth={1.5}
            opacity={0.45}
          />
          <circle
            cx={center.x}
            cy={center.y}
            r={rTargetLo}
            fill="none"
            stroke="#22c55e"
            strokeWidth={1}
            opacity={0.35}
          />
          {/* personal limit at current speed */}
          <circle
            cx={center.x}
            cy={center.y}
            r={rLimit}
            fill="rgba(71,85,105,0.08)"
            stroke="#94a3b8"
            strokeWidth={2}
            strokeDasharray="4 3"
          />

          {/* trail */}
          {trailPoints && (
            <polyline
              points={trailPoints}
              fill="none"
              stroke="#64748b"
              strokeWidth={zoomed ? 2.5 : 1.8}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={0.85}
            />
          )}

          {/* colour last segment by grip usage */}
          {display.length > 1 &&
            display.slice(-Math.min(12, display.length)).map((s, i) => {
              const u = peakAy?.length
                ? gripUsage(peakAy, s.speed_kmh, s.acc_g_lat)
                : 0.5;
              const p = toXY(s.acc_g_long, s.acc_g_lat, gMax, size);
              return (
                <circle
                  key={i}
                  cx={p.x}
                  cy={p.y}
                  r={zoomed ? 3.5 : 2.5}
                  fill={gripUsageColor(u)}
                  opacity={0.9}
                />
              );
            })}

          {/* playhead grip wedge */}
          {play && (
            <>
              <path
                d={usageArcPath(center.x, center.y, rLimit, usage)}
                fill={usageColor}
                opacity={0.35}
              />
              <circle
                cx={toXY(play.acc_g_long, play.acc_g_lat, gMax, size).x}
                cy={toXY(play.acc_g_long, play.acc_g_lat, gMax, size).y}
                r={zoomed ? 9 : 7}
                fill={usageColor}
                stroke="#fff"
                strokeWidth={2}
              />
            </>
          )}

          <text x={size - PAD} y={PAD + 8} fill="#64748b" fontSize={9} textAnchor="end">
            accel →
          </text>
          <text x={PAD + 2} y={size - PAD + 4} fill="#64748b" fontSize={9}>
            ← brake
          </text>
        </svg>

        <div
          style={{
            flex: "1 1 180px",
            background: "#1e293b",
            borderRadius: 8,
            padding: 12,
            fontSize: 12,
            color: "#cbd5e1",
            minWidth: 160,
          }}
        >
          <div style={{ fontWeight: 600, color: "#f1f5f9", marginBottom: 8 }}>Grip at playhead</div>
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: "#94a3b8" }}>Speed </span>
            {Math.round(speed)} km/h
          </div>
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: "#94a3b8" }}>Using </span>
            <strong style={{ color: usageColor, fontSize: 18 }}>{usagePct}%</strong>
            <span style={{ color: "#64748b" }}> of your {gripLimit.toFixed(2)}G limit</span>
          </div>
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: "#94a3b8" }}>Grip left </span>
            <strong>{leftPct}%</strong>
          </div>
          <div style={{ marginBottom: 8, fontSize: 11, color: "#94a3b8", lineHeight: 1.4 }}>
            Target <strong style={{ color: "#22c55e" }}>85–92%</strong> in corners — green rings on
            diagram. Above 100% you&apos;re over your personal envelope.
          </div>
          {play && (
            <div style={{ fontSize: 11, color: "#64748b", borderTop: "1px solid #334155", paddingTop: 8 }}>
              {play.acc_g_lat.toFixed(2)}G lateral · {play.acc_g_long.toFixed(2)}G longitudinal
            </div>
          )}
          <div style={{ fontSize: 10, color: "#475569", marginTop: 8 }}>
            Grey dashed = session peak · Zoom a telemetry region to inspect a corner
          </div>
        </div>
      </div>
    </div>
  );
}
