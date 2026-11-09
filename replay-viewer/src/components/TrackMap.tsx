import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Annotation, Geometry, LapSample, LayerState } from "../types";
import { mapLineSegments, pathFromSegments, preparePlotSeries } from "../utils/telemetryDerived";
import { MIN_SELECT_SPAN, normalizeSplineRange } from "../utils/viewRange";
import { throttle } from "../utils/throttle";
import {
  boundsFromPoints,
  initialViewport,
  useMapViewport,
  viewportForWorldRect,
  worldToScreen,
  type MapViewport,
} from "../hooks/useMapViewport";

export interface TrackMapHandle {
  resetView: () => void;
}

interface Props {
  geometry: Geometry;
  samples: LapSample[];
  compareSamples?: LapSample[];
  playheadSpline: number;
  layers: LayerState;
  annotations: Annotation[];
  selectedCorner: string | null;
  focusSplineRange?: [number, number] | null;
  previewRange?: [number, number] | null;
  onSplineHover: (spline: number) => void;
  onSplineClick: (spline: number) => void;
  onAnnotationClick: (ann: Annotation) => void;
  onFocusSplineRange?: (range: [number, number]) => void;
  onPreviewRangeChange?: (range: [number, number] | null) => void;
  onCommitRange?: (range: [number, number]) => void;
  onCornerSelect?: (cornerId: string) => void;
}

const W = 520;
const H = 520;

function toPathWorld(pts: [number, number][]) {
  return pathFromSegments([pts]);
}

function categoryColor(category: Annotation["category"]) {
  if (category === "opportunity") return "#06b6d4";
  if (category === "setup") return "#a855f7";
  if (category === "coach") return "#38bdf8";
  return "#f97316";
}

function splineFromScreen(
  geometry: Geometry,
  sx: number,
  sy: number,
  w: number,
  h: number,
  vp: MapViewport,
) {
  let best = 0;
  let bestD = Infinity;
  const n = geometry.centerline.length;
  for (let i = 0; i < n; i++) {
    const [x, z] = geometry.centerline[i];
    const p = worldToScreen(x, z, w, h, vp);
    const d = (p.x - sx) ** 2 + (p.y - sy) ** 2;
    if (d < bestD) {
      bestD = d;
      best = i / Math.max(1, n - 1);
    }
  }
  return best;
}

function MapLegend() {
  const items = [
    { color: "#22c55e", label: "Your lap line" },
    { color: "#3b82f6", label: "Compare lap", dash: true },
    { color: "#f97316", label: "Correction pin" },
    { color: "#06b6d4", label: "Opportunity pin" },
    { color: "#38bdf8", label: "Coach note pin" },
    { color: "#64748b", label: "Corner label" },
    { color: "#ef4444", label: "Playhead" },
    { color: "#f59e0b", label: "Selection preview", dash: true },
    { color: "#e2e8f0", label: "Zoomed region", bracket: true },
  ];
  return (
    <div className="track-map-legend">
      {items.map((it) => (
        <span key={it.label} className="track-map-legend-item">
          {it.bracket ? (
            <span className="legend-bracket" />
          ) : (
            <span
              className="legend-swatch"
              style={{
                background: it.dash ? "transparent" : it.color,
                borderColor: it.color,
                borderStyle: it.dash ? "dashed" : "solid",
              }}
            />
          )}
          {it.label}
        </span>
      ))}
    </div>
  );
}

export const TrackMap = forwardRef<TrackMapHandle, Props>(function TrackMap(
  {
    geometry,
    samples,
    compareSamples,
    playheadSpline,
    layers,
    annotations,
    selectedCorner,
    focusSplineRange,
    previewRange,
    onSplineHover,
    onSplineClick,
    onAnnotationClick,
    onFocusSplineRange,
    onPreviewRangeChange,
    onCommitRange,
    onCornerSelect,
  },
  ref,
) {
  const svgRef = useRef<SVGSVGElement>(null);
  const hoverRef = useRef(onSplineHover);
  hoverRef.current = onSplineHover;
  const [regionSelectMode, setRegionSelectMode] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const selectStartRef = useRef<number | null>(null);
  const justSelectedRef = useRef(false);

  const worldBounds = useMemo(
    () =>
      boundsFromPoints(
        geometry.surface_polygon.length ? geometry.surface_polygon : geometry.centerline,
      ),
    [geometry],
  );

  const fitVp = useMemo(() => initialViewport(worldBounds), [worldBounds]);

  const { vp, vpRef, setVp, reset, zoomAt, onPointerDown, onPointerMove, onPointerUp, dragging } =
    useMapViewport(fitVp);

  useImperativeHandle(
    ref,
    () => ({
      resetView: () => reset(fitVp),
    }),
    [reset, fitVp],
  );

  useEffect(() => {
    reset(fitVp);
  }, [geometry.centerline.length, fitVp, reset]);

  useEffect(() => {
    if (!focusSplineRange) return;
    const [s0, s1] = focusSplineRange;
    const i0 = Math.floor(s0 * (geometry.centerline.length - 1));
    const i1 = Math.ceil(s1 * (geometry.centerline.length - 1));
    const slice = geometry.centerline.slice(
      Math.max(0, i0),
      Math.min(geometry.centerline.length, i1 + 1),
    );
    if (slice.length < 2) return;
    const b = boundsFromPoints(slice);
    setVp(viewportForWorldRect(worldBounds, b.minX, b.maxX, b.minZ, b.maxZ, W, H));
  }, [focusSplineRange, geometry, worldBounds, setVp]);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      zoomAt(e.offsetX, e.offsetY, W, H, factor);
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [zoomAt]);

  const throttledHover = useMemo(
    () => throttle((s: number) => hoverRef.current(s), 32),
    [],
  );

  const transform = `translate(${W / 2}, ${H / 2}) scale(${vp.scale}, ${vp.scale}) translate(${-vp.cx}, ${-vp.cz})`;

  const plotSamples = useMemo(() => preparePlotSeries(samples), [samples]);

  const lineSegments = useMemo((): [number, number][][] => {
    if (!layers.mapLines) return [];
    return mapLineSegments(plotSamples, geometry);
  }, [plotSamples, geometry, layers.mapLines]);

  const compareSegments = useMemo((): [number, number][][] => {
    if (!compareSamples?.length || !layers.mapLines) return [];
    return mapLineSegments(preparePlotSeries(compareSamples), geometry);
  }, [compareSamples, geometry, layers.mapLines]);

  const visibleAnnotations = annotations.filter((a) => {
    if (a.category === "correction" && !layers.corrections) return false;
    if (a.category === "opportunity" && !layers.opportunities) return false;
    if (a.category === "setup" && !layers.setup) return false;
    if (a.category === "surface" && !layers.surface) return false;
    if (a.category === "coach" && !layers.coach) return false;
    return a.spline > 0 || a.category === "setup";
  });

  const cornerLabels = useMemo(() => {
    const sorted = [...geometry.corners].sort((a, b) => a.spline_start - b.spline_start);
    const order = new Map(sorted.map((c, i) => [c.id, i + 1]));
    return geometry.corners.map((c) => ({
      ...c,
      lapOrder: order.get(c.id) ?? 0,
    }));
  }, [geometry.corners]);

  const playheadScreen = useMemo(() => {
    const idx = Math.round(playheadSpline * (geometry.centerline.length - 1));
    const [x, z] = geometry.centerline[Math.min(Math.max(idx, 0), geometry.centerline.length - 1)];
    return worldToScreen(x, z, W, H, vp);
  }, [playheadSpline, geometry, vp]);

  const zoomWindowPath = useMemo(() => {
    if (!focusSplineRange) return "";
    return splineRangePath(focusSplineRange, geometry, vp);
  }, [focusSplineRange, geometry, vp]);

  const previewHighlightPath = useMemo(() => {
    if (!previewRange) return "";
    return splineRangePath(previewRange, geometry, vp, plotSamples);
  }, [previewRange, geometry, vp, plotSamples]);

  const wantsRegionSelect = (e: React.PointerEvent) => regionSelectMode || e.shiftKey;

  const splineAtEvent = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    return splineFromScreen(geometry, sx, sy, W, H, vpRef.current);
  };

  const handlePointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0) return;
    if (wantsRegionSelect(e)) {
      e.preventDefault();
      e.currentTarget.setPointerCapture(e.pointerId);
      const spline = splineAtEvent(e);
      selectStartRef.current = spline;
      setSelecting(true);
      justSelectedRef.current = false;
      onPreviewRangeChange?.([spline, spline]);
      return;
    }
    onPointerDown(e);
  };

  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (selecting && selectStartRef.current != null) {
      const end = splineAtEvent(e);
      const [lo, hi] = normalizeSplineRange(selectStartRef.current, end);
      onPreviewRangeChange?.([lo, hi]);
      throttledHover(end);
      return;
    }
    onPointerMove(e);
    if (!dragging) {
      throttledHover(splineAtEvent(e));
    }
  };

  const handlePointerUp = (e: React.PointerEvent<SVGSVGElement>) => {
    if (selecting) {
      const end = splineAtEvent(e);
      const start = selectStartRef.current ?? end;
      selectStartRef.current = null;
      setSelecting(false);
      onPreviewRangeChange?.(null);
      const [lo, hi] = normalizeSplineRange(start, end);
      if (hi - lo >= MIN_SELECT_SPAN) {
        justSelectedRef.current = true;
        onCommitRange?.([lo, hi]);
      }
      return;
    }
    onPointerUp();
  };

  const handleClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (justSelectedRef.current) {
      justSelectedRef.current = false;
      return;
    }
    const rect = e.currentTarget.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    onSplineClick(splineFromScreen(geometry, sx, sy, W, H, vpRef.current));
  };

  const handleCornerClick = (cornerId: string, s0: number, s1: number, e: React.MouseEvent) => {
    e.stopPropagation();
    onCornerSelect?.(cornerId);
    onFocusSplineRange?.([s0, s1]);
  };

  return (
    <div className="track-map-wrap">
      <div className="track-map-toolbar">
        <button
          type="button"
          title="Fit entire track"
          onClick={() => reset(fitVp)}
          style={{ fontSize: 11, padding: "2px 8px" }}
        >
          Fit map
        </button>
        <button
          type="button"
          title="Drag on track to select a region (Shift+drag always works)"
          className={regionSelectMode || selecting ? "active" : ""}
          onClick={() => setRegionSelectMode((v) => !v)}
          style={{ fontSize: 11, padding: "2px 8px" }}
        >
          {regionSelectMode || selecting ? "Selecting…" : "Select region"}
        </button>
      </div>
      <svg
        ref={svgRef}
        width={W}
        height={H}
        className={`track-map${regionSelectMode || selecting ? " track-map-select-mode" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
        onClick={handleClick}
      >
        <g transform={transform}>
          {layers.mapTarmac && (
            <path
              d={toPathWorld(geometry.surface_polygon)}
              fill="#2a2f38"
              stroke="#444"
              vectorEffect="non-scaling-stroke"
              strokeWidth={1}
            />
          )}
          {compareSegments.map((seg, i) => (
            <path
              key={`cmp${i}`}
              d={pathFromSegments([seg])}
              fill="none"
              stroke="#3b82f6"
              strokeWidth={2}
              strokeDasharray="6,4"
              vectorEffect="non-scaling-stroke"
              opacity={0.75}
            />
          ))}
          {lineSegments.map((seg, i) => (
            <path
              key={`lap${i}`}
              d={pathFromSegments([seg])}
              fill="none"
              stroke="#22c55e"
              strokeWidth={2.5}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </g>

        <g className="track-map-overlay">
          {previewHighlightPath && (
            <path
              d={previewHighlightPath}
              fill="none"
              stroke="#f59e0b"
              strokeWidth={5}
              strokeLinecap="round"
              opacity={0.95}
              pointerEvents="none"
            />
          )}
          {zoomWindowPath && (
            <path
              d={zoomWindowPath}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth={2}
              strokeDasharray="4,3"
              opacity={0.9}
            />
          )}
          {layers.mapCorners &&
            cornerLabels.map((c) => {
              const active = selectedCorner === c.id;
              const [lx, lz] = c.label_xy;
              const p = worldToScreen(lx, lz, W, H, vp);
              const labelAbove = p.y > H * 0.22;
              const labelY = labelAbove ? p.y - 14 : p.y + 18;
              const anchor =
                p.x > W * 0.78 ? "end" : p.x < W * 0.22 ? "start" : "middle";
              const labelX =
                anchor === "end" ? p.x - 4 : anchor === "start" ? p.x + 4 : p.x;
              return (
                <g key={c.id}>
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={active ? 10 : 7}
                    fill={active ? "#f59e0b" : "#64748b"}
                    stroke="#0f172a"
                    strokeWidth={1.5}
                    onClick={(e) => handleCornerClick(c.id, c.spline_start, c.spline_end, e)}
                    style={{ cursor: "pointer" }}
                  />
                  <text
                    x={labelX}
                    y={labelY}
                    textAnchor={anchor}
                    className="track-map-corner-label"
                    fill={active ? "#fbbf24" : "#e2e8f0"}
                    fontWeight={active ? 700 : 600}
                    onClick={(e) => handleCornerClick(c.id, c.spline_start, c.spline_end, e)}
                    style={{ cursor: "pointer" }}
                  >
                    {c.lapOrder}. {c.display_name}
                  </text>
                </g>
              );
            })}
          {visibleAnnotations.map((ann) => {
            const color = categoryColor(ann.category);
            const idx = Math.round(ann.spline * (geometry.centerline.length - 1));
            const [ax, az] = geometry.centerline[Math.min(idx, geometry.centerline.length - 1)];
            const p = worldToScreen(ax, az, W, H, vp);
            return (
              <circle
                key={ann.id}
                cx={p.x}
                cy={p.y}
                r={6}
                fill={color}
                stroke="#0f172a"
                strokeWidth={1.5}
                onClick={(ev) => {
                  ev.stopPropagation();
                  onAnnotationClick(ann);
                }}
                style={{ cursor: "pointer" }}
              />
            );
          })}
          <circle
            cx={playheadScreen.x}
            cy={playheadScreen.y}
            r={7}
            fill="#ef4444"
            stroke="#fff"
            strokeWidth={2}
            pointerEvents="none"
          />
        </g>
      </svg>
      <MapLegend />
      <div className="track-map-hint">
        Drag to pan · scroll to zoom · click to scrub · Shift+drag or Select region to zoom
      </div>
    </div>
  );
});

function splineRangePath(
  range: [number, number],
  geometry: Geometry,
  vp: MapViewport,
  samples?: LapSample[],
) {
  const [s0, s1] = range;
  const pts: string[] = [];

  if (samples?.length) {
    const slice = samples.filter((s) => s.spline >= s0 - 0.0001 && s.spline <= s1 + 0.0001);
    for (const s of slice) {
      if (s.pos_x != null && s.pos_z != null) {
        const p = worldToScreen(s.pos_x, s.pos_z, W, H, vp);
        pts.push(`${p.x},${p.y}`);
      }
    }
  }

  if (pts.length < 2) {
    const i0 = Math.floor(s0 * (geometry.centerline.length - 1));
    const i1 = Math.ceil(s1 * (geometry.centerline.length - 1));
    const slice = geometry.centerline.slice(
      Math.max(0, i0),
      Math.min(geometry.centerline.length, i1 + 1),
    );
    for (const [x, z] of slice) {
      const p = worldToScreen(x, z, W, H, vp);
      pts.push(`${p.x},${p.y}`);
    }
  }

  if (pts.length < 2) return "";
  return `M ${pts.join(" L ")}`;
}
