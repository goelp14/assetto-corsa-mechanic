import { useEffect, useMemo, useRef } from "react";
import uPlot from "uplot";
import type { LapSample } from "../../types";
import type { Annotation } from "../../types";
import type { CornerTimeLoss } from "../../types";
import { throttle } from "../../utils/throttle";
import {
  annotationRegions,
  gripUsage,
  phaseRegions,
  preparePlotSeries,
  suspVal,
  timeLossRegions,
  wheelVal,
  type RegionBand,
} from "../../utils/telemetryDerived";

const SYNC_KEY = "vre-replay";

export type ChartMode =
  | "speed"
  | "delta"
  | "inputs"
  | "brake"
  | "throttle"
  | "steering"
  | "grip"
  | "timeloss"
  | "latg"
  | "longg"
  | "balance"
  | "beta"
  | "yaw"
  | "wheel_load"
  | "suspension";

interface Props {
  samples: LapSample[];
  compareSamples?: LapSample[];
  delta?: number[];
  playheadSpline: number;
  viewRange?: [number, number] | null;
  highlightRange?: [number, number] | null;
  mode: ChartMode;
  showBrake?: boolean;
  showThrottle?: boolean;
  showPhaseBands?: boolean;
  peakAy?: number[];
  annotations?: Annotation[];
  timeLossCorners?: CornerTimeLoss[];
  activeLap?: number | null;
  onSplineChange: (spline: number) => void;
  onViewRangeChange?: (range: [number, number]) => void;
}

function refAligned(
  samples: LapSample[],
  compare: LapSample[] | undefined,
  field: keyof LapSample,
): (number | null)[] {
  if (!compare?.length) return [];
  const refMap = new Map(compare.map((s) => [Math.round(s.spline * 2000), s[field] as number]));
  return samples.map((s) => refMap.get(Math.round(s.spline * 2000)) ?? null);
}

function drawRegions(u: uPlot, regions: RegionBand[]) {
  const ctx = u.ctx;
  const { top, height } = u.bbox;
  ctx.save();
  for (const r of regions) {
    const x0 = u.valToPos(r.start, "x", true);
    const x1 = u.valToPos(r.end, "x", true);
    if (x1 < u.bbox.left || x0 > u.bbox.left + u.bbox.width) continue;
    ctx.fillStyle = r.color;
    ctx.fillRect(x0, top, x1 - x0, height);
  }
  ctx.restore();
}

function drawGripTargetBand(u: uPlot) {
  const ctx = u.ctx;
  const y85 = u.valToPos(85, "y", true);
  const y92 = u.valToPos(92, "y", true);
  const y100 = u.valToPos(100, "y", true);
  ctx.save();
  ctx.fillStyle = "rgba(34,197,94,0.12)";
  ctx.fillRect(u.bbox.left, y92, u.bbox.width, y85 - y92);
  ctx.strokeStyle = "rgba(34,197,94,0.45)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(u.bbox.left, y92);
  ctx.lineTo(u.bbox.left + u.bbox.width, y92);
  ctx.moveTo(u.bbox.left, y85);
  ctx.lineTo(u.bbox.left + u.bbox.width, y85);
  ctx.stroke();
  ctx.strokeStyle = "rgba(239,68,68,0.5)";
  ctx.beginPath();
  ctx.moveTo(u.bbox.left, y100);
  ctx.lineTo(u.bbox.left + u.bbox.width, y100);
  ctx.stroke();
  ctx.restore();
}

export function DistanceChart({
  samples: rawSamples,
  compareSamples,
  delta,
  playheadSpline,
  viewRange,
  highlightRange,
  mode,
  showBrake = true,
  showThrottle = true,
  showPhaseBands = false,
  peakAy,
  annotations = [],
  timeLossCorners = [],
  activeLap,
  onSplineChange,
  onViewRangeChange,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const plotRef = useRef<uPlot | null>(null);
  const onSplineRef = useRef(onSplineChange);
  const onZoomRef = useRef(onViewRangeChange);
  onSplineRef.current = onSplineChange;
  onZoomRef.current = onViewRangeChange;

  const throttledSpline = useMemo(
    () => throttle((s: number) => onSplineRef.current(s), 32),
    [],
  );

  const plotSamples = useMemo(() => preparePlotSeries(rawSamples), [rawSamples]);
  const regions = useMemo(() => {
    const ann = annotationRegions(annotations, activeLap);
    const loss = timeLossRegions(timeLossCorners);
    const phase = showPhaseBands ? phaseRegions(plotSamples) : [];
    const preview =
      highlightRange && !viewRange
        ? [
            {
              id: "preview",
              start: highlightRange[0],
              end: highlightRange[1],
              color: "rgba(245,158,11,0.32)",
              title: "Map selection",
            },
          ]
        : [];
    return [...loss, ...phase, ...ann, ...preview];
  }, [annotations, activeLap, timeLossCorners, showPhaseBands, plotSamples, highlightRange, viewRange]);
  const regionsRef = useRef(regions);
  regionsRef.current = regions;

  useEffect(() => {
    if (!ref.current || !plotSamples.length) return;
    const samples = plotSamples;
    const x = samples.map((s) => s.spline);
    const w = ref.current.clientWidth || 600;
    const xScale = viewRange
      ? { time: false as const, min: viewRange[0], max: viewRange[1] }
      : { time: false as const };

    let series: uPlot.Series[] = [{ label: "dist" }];
    let data: uPlot.AlignedData = [x];
    let yScale: uPlot.Scale = { auto: true };
    let title = "";
    let height = 100;
    let drawGripBand = false;

    if (mode === "speed") {
      title = "Speed vs distance (km/h) · drag to zoom";
      height = 120;
      series.push({ label: "speed", stroke: "#22c55e", width: 2, fill: "rgba(34,197,94,0.08)" });
      data.push(samples.map((s) => s.speed_kmh));
      if (compareSamples?.length) {
        series.push({ label: "ref", stroke: "#3b82f6", width: 1, dash: [6, 4] });
        data.push(refAligned(samples, preparePlotSeries(compareSamples), "speed_kmh"));
      }
      const max = Math.max(...samples.map((s) => s.speed_kmh), 50);
      const min = Math.min(...samples.map((s) => s.speed_kmh), 0);
      const pad = Math.max(5, (max - min) * 0.08);
      yScale = { auto: false, range: [Math.max(0, min - pad), max + pad] };
    } else if (mode === "delta" && delta?.length) {
      title = "Cumulative Δt vs reference (s) · drag to zoom";
      const visDelta = samples.map((s) => {
        const idx = plotSamples.findIndex((p) => p.spline === s.spline);
        return delta[idx >= 0 ? idx : 0] ?? 0;
      });
      series.push({ label: "Δt", stroke: "#f97316", width: 2, fill: "rgba(249,115,22,0.1)" });
      data.push(visDelta);
      const min = Math.min(...visDelta);
      const max = Math.max(...visDelta);
      const pad = Math.max(0.05, (max - min) * 0.1);
      yScale = { auto: false, range: [min - pad, max + pad] };
    } else if (mode === "inputs" || mode === "brake" || mode === "throttle") {
      const brakeOnly = mode === "brake" || (mode === "inputs" && showBrake && !showThrottle);
      const throttleOnly = mode === "throttle" || (mode === "inputs" && showThrottle && !showBrake);
      if (mode === "brake" || brakeOnly) {
        title = "Brake vs distance (%) · drag a region to zoom";
        series.push({ label: "brake", stroke: "#ef4444", width: 2 });
        data.push(samples.map((s) => s.brake * 100));
      } else if (mode === "throttle" || throttleOnly) {
        title = "Throttle vs distance (%) · drag a region to zoom";
        series.push({ label: "throttle", stroke: "#22c55e", width: 2 });
        data.push(samples.map((s) => s.throttle * 100));
      } else {
        title = "Brake / throttle vs distance (%) · drag a region to zoom";
        if (showBrake) {
          series.push({ label: "brake", stroke: "#ef4444", width: 2 });
          data.push(samples.map((s) => s.brake * 100));
        }
        if (showThrottle) {
          series.push({ label: "throttle", stroke: "#22c55e", width: 2 });
          data.push(samples.map((s) => s.throttle * 100));
        }
      }
      yScale = { auto: false, range: [0, 105] };
    } else if (mode === "steering") {
      title = "Steering vs distance (°) · drag to zoom";
      const vals = samples.map((s) => s.steer_deg);
      const max = Math.max(...vals.map(Math.abs), 10);
      series.push({ label: "steer", stroke: "#a855f7", width: 2 });
      data.push(vals);
      if (compareSamples?.length) {
        series.push({ label: "ref", stroke: "#3b82f6", width: 1, dash: [6, 4] });
        data.push(refAligned(samples, preparePlotSeries(compareSamples), "steer_deg"));
      }
      yScale = { auto: false, range: [-max * 1.15, max * 1.15] };
    } else if (mode === "latg") {
      title = "Lateral G vs distance · drag to zoom";
      const vals = samples.map((s) => s.acc_g_lat);
      const max = Math.max(...vals.map(Math.abs), 0.5);
      series.push({ label: "lat G", stroke: "#eab308", width: 2 });
      data.push(vals);
      yScale = { auto: false, range: [-max * 1.15, max * 1.15] };
    } else if (mode === "longg") {
      title = "Longitudinal G vs distance (accel + / brake −) · drag to zoom";
      const vals = samples.map((s) => s.acc_g_long ?? 0);
      const max = Math.max(...vals.map(Math.abs), 0.5);
      series.push({ label: "long G", stroke: "#38bdf8", width: 2 });
      data.push(vals);
      yScale = { auto: false, range: [-max * 1.15, max * 1.15] };
    } else if (mode === "balance") {
      title = "Understeer gradient δᵤₛ (°) · + = understeer · drag to zoom";
      height = 90;
      const vals = samples.map((s) => s.delta_us_deg ?? 0);
      const max = Math.max(...vals.map(Math.abs), 1);
      series.push({ label: "δᵤₛ", stroke: "#f472b6", width: 2 });
      data.push(vals);
      yScale = { auto: false, range: [-max * 1.2, max * 1.2] };
    } else if (mode === "beta") {
      title = "Slip angle β (°) vs distance · drag to zoom";
      height = 90;
      const vals = samples.map((s) => s.beta_deg ?? 0);
      const max = Math.max(...vals.map(Math.abs), 1);
      series.push({ label: "β", stroke: "#a78bfa", width: 2 });
      data.push(vals);
      yScale = { auto: false, range: [-max * 1.2, max * 1.2] };
    } else if (mode === "yaw") {
      title = "Yaw rate (rad/s) vs distance · drag to zoom";
      height = 90;
      const vals = samples.map((s) => s.yaw_rate ?? 0);
      const max = Math.max(...vals.map(Math.abs), 0.1);
      series.push({ label: "yaw", stroke: "#2dd4bf", width: 2 });
      data.push(vals);
      yScale = { auto: false, range: [-max * 1.2, max * 1.2] };
    } else if (mode === "wheel_load") {
      title = "Wheel load (N) FL/FR/RL/RR · drag to zoom";
      height = 110;
      const labels = ["FL", "FR", "RL", "RR"] as const;
      const colors = ["#ef4444", "#3b82f6", "#22c55e", "#eab308"];
      labels.forEach((lab, i) => {
        series.push({ label: lab, stroke: colors[i], width: 1.5 });
        data.push(samples.map((s) => wheelVal(s, i)));
      });
      const flat = samples.flatMap((s) => s.wheel_load ?? []).filter((v) => v > 0);
      const max = Math.max(...flat, 1000);
      yScale = { auto: false, range: [0, max * 1.05] };
    } else if (mode === "suspension") {
      title = "Suspension travel (%) FL/FR/RL/RR · drag to zoom";
      height = 110;
      const labels = ["FL", "FR", "RL", "RR"] as const;
      const colors = ["#ef4444", "#3b82f6", "#22c55e", "#eab308"];
      labels.forEach((lab, i) => {
        series.push({ label: lab, stroke: colors[i], width: 1.5 });
        data.push(samples.map((s) => suspVal(s, i)));
      });
      yScale = { auto: false, range: [0, 105] };
    } else if (mode === "grip" && peakAy?.length) {
      title = "Grip utilization vs distance (% of your limit) · drag to zoom";
      height = 110;
      drawGripBand = true;
      series.push({ label: "grip%", stroke: "#eab308", width: 2, fill: "rgba(234,179,8,0.1)" });
      data.push(
        samples.map((s) =>
          Math.round(gripUsage(peakAy, s.speed_kmh, s.acc_g_lat) * 100),
        ),
      );
      yScale = { auto: false, range: [0, 120] };
    } else if (mode === "timeloss" && delta?.length) {
      title = "Time loss vs your stitched best (s) · drag to zoom";
      height = 120;
      const visLoss = samples.map((s) => {
        const idx = plotSamples.findIndex((p) => p.spline === s.spline);
        return Math.max(0, delta[idx >= 0 ? idx : 0] ?? 0);
      });
      series.push({
        label: "loss",
        stroke: "#fb923c",
        width: 2,
        fill: "rgba(251,146,60,0.12)",
      });
      data.push(visLoss);
      const max = Math.max(...visLoss, 0.05);
      yScale = { auto: false, range: [0, max * 1.15] };
    }

    const titleEl = ref.current.querySelector(".chart-title");
    if (titleEl) {
      titleEl.textContent = title;
    } else {
      const t = document.createElement("div");
      t.className = "chart-title";
      t.textContent = title;
      t.style.cssText = "font-size:11px;color:#94a3b8;margin:0 0 4px 4px";
      ref.current.prepend(t);
    }

    const mount = document.createElement("div");
    ref.current.appendChild(mount);

    const opts: uPlot.Options = {
      width: w,
      height,
      series,
      scales: { x: xScale, y: yScale },
      axes: [
        {
          stroke: "#64748b",
          grid: { stroke: "#1e293b" },
          values: (_u, splits) => splits.map((v) => (v * 100).toFixed(0) + "%"),
        },
        { stroke: "#64748b", grid: { stroke: "#1e293b" }, size: 48 },
      ],
      cursor: {
        sync: { key: SYNC_KEY, setSeries: true },
        drag: { x: true, y: false, setScale: false },
      },
      select: { show: true },
      hooks: {
        drawClear: [
          (u) => {
            drawRegions(u, regionsRef.current);
            if (drawGripBand) drawGripTargetBand(u);
          },
        ],
        setCursor: [
          (u) => {
            const idx = u.cursor.idx;
            if (idx != null && samples[idx]) throttledSpline(samples[idx].spline);
          },
        ],
        setSelect: [
          (u) => {
            const left = u.select.left;
            const width = u.select.width;
            if (left == null || width == null || width < 8) return;
            const x0 = u.posToVal(left, "x");
            const x1 = u.posToVal(left + width, "x");
            const lo = Math.max(0, Math.min(x0, x1));
            const hi = Math.min(1, Math.max(x0, x1));
            const pad = Math.max(0.002, (hi - lo) * 0.03);
            onZoomRef.current?.([Math.max(0, lo - pad), Math.min(1, hi + pad)]);
            u.setSelect({ left: 0, width: 0 }, false);
          },
        ],
      },
    };

    plotRef.current?.destroy();
    const plot = new uPlot(opts, data, mount);
    plotRef.current = plot;
    const xLo = viewRange?.[0] ?? x[0];
    const xHi = viewRange?.[1] ?? x[x.length - 1];
    plot.setScale("x", { min: xLo, max: xHi });

    return () => {
      plotRef.current?.destroy();
      plotRef.current = null;
      const root = ref.current;
      if (root) {
        const kept = root.querySelector(".chart-title");
        root.innerHTML = "";
        if (kept) root.appendChild(kept);
      }
    };
  }, [
    plotSamples,
    compareSamples,
    delta,
    mode,
    showBrake,
    showThrottle,
    peakAy,
    showPhaseBands,
  ]);

  // Zoom via setScale only — do not recreate the chart when viewRange/highlight changes.
  useEffect(() => {
    const plot = plotRef.current;
    if (!plot) return;
    const xs = plot.data[0] as number[];
    if (!xs?.length) return;
    if (viewRange) {
      plot.setScale("x", { min: viewRange[0], max: viewRange[1] });
    } else {
      plot.setScale("x", { min: xs[0], max: xs[xs.length - 1] });
    }
  }, [viewRange]);

  useEffect(() => {
    plotRef.current?.redraw();
  }, [regions]);

  useEffect(() => {
    const plot = plotRef.current;
    if (!plot || !plotSamples.length) return;
    const search = plotSamples;
    let idx = 0;
    let bestD = Infinity;
    for (let i = 0; i < search.length; i++) {
      const d = Math.abs(search[i].spline - playheadSpline);
      if (d < bestD) {
        bestD = d;
        idx = i;
      }
    }
    plot.setCursor({ left: plot.valToPos(search[idx].spline, "x"), top: 0 });
  }, [playheadSpline, plotSamples]);

  return <div ref={ref} style={{ marginBottom: 8, width: "100%" }} />;
}
