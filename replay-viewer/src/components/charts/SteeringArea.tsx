import type { LapSample } from "../../types";
import { filterBySplineRange, splineFromMouseX } from "../../utils/telemetryDerived";

interface Props {
  samples: LapSample[];
  playheadSpline: number;
  viewRange?: [number, number] | null;
  onSplineChange: (spline: number) => void;
}

const H = 80;

export function SteeringArea({ samples, playheadSpline, viewRange, onSplineChange }: Props) {
  const visible = filterBySplineRange(samples, viewRange);
  const w = Math.max(visible.length, 2);
  const max = Math.max(...visible.map((s) => Math.abs(s.steer_deg)), 15);
  const mid = H / 2;

  const scrub = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    onSplineChange(splineFromMouseX(samples, e.clientX, rect, viewRange));
  };

  const points = visible.map((s, i) => {
    const y = mid - (s.steer_deg / max) * (mid - 6);
    return `${i},${y}`;
  });

  const areaPath = `M0,${mid} L${points.join(" L")} L${w - 1},${mid} Z`;

  const playX =
    ((playheadSpline - (viewRange?.[0] ?? 0)) /
      Math.max((viewRange?.[1] ?? 1) - (viewRange?.[0] ?? 0), 0.001)) *
    w;

  return (
    <div style={{ marginBottom: 8, width: "100%" }}>
      <div style={{ fontSize: 11, color: "#94a3b8", margin: "0 0 4px 4px" }}>
        Steering angle · signed area (left / right)
      </div>
      <svg
        width="100%"
        height={H}
        viewBox={`0 0 ${w} ${H}`}
        preserveAspectRatio="none"
        style={{ background: "#0f172a", borderRadius: 8, cursor: "crosshair", display: "block" }}
        onMouseMove={scrub}
        onClick={scrub}
      >
        <line x1={0} y1={mid} x2={w} y2={mid} stroke="#334155" strokeWidth={0.5} />
        <path d={areaPath} fill="rgba(168,85,247,0.35)" />
        <polyline
          points={points.join(" ")}
          fill="none"
          stroke="#a855f7"
          strokeWidth={1.2}
        />
        <line x1={playX} y1={0} x2={playX} y2={H} stroke="#ef4444" strokeWidth={1.5} />
      </svg>
    </div>
  );
}
