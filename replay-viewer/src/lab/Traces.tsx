// Linked distance traces (MoTeC-style): Δt lane, channels for both laps, dual cursor, brush zoom,
// corner bands, terrain lane, event ticks and annotations. One canvas; all lanes share the x axis.
import { useCallback, useEffect, useRef } from "react";
import { COLORS, gridValue, type Channel, type Grid } from "./data";
import type { MapMarker } from "./TrackCanvas";
import type { Overlay, PackCorner, Terrain } from "./types";

export interface LaneDef {
  id: string;
  label: string;
  ch?: Channel;
  unit: string;
  h: number;
  min?: number;
  max?: number;
  fmt?: (v: number) => string;
}

export const ALL_LANES: LaneDef[] = [
  { id: "delta", label: "Δ time", unit: "s", h: 70 },
  { id: "speed", label: "Speed", ch: "speed_kmh", unit: "km/h", h: 120, fmt: (v) => v.toFixed(0) },
  { id: "throttle", label: "Throttle", ch: "throttle", unit: "%", h: 52, min: 0, max: 1, fmt: (v) => (v * 100).toFixed(0) },
  { id: "brake", label: "Brake", ch: "brake", unit: "%", h: 52, min: 0, max: 1, fmt: (v) => (v * 100).toFixed(0) },
  { id: "steer", label: "Steering", ch: "steer_deg", unit: "°", h: 64, fmt: (v) => v.toFixed(0) },
  { id: "gear", label: "Gear", ch: "gear", unit: "", h: 40, min: 0.5, max: 6.5, fmt: (v) => v.toFixed(0) },
  { id: "g_lat", label: "Lat G", ch: "g_lat", unit: "g", h: 56, fmt: (v) => v.toFixed(2) },
  { id: "g_lon", label: "Long G", ch: "g_lon", unit: "g", h: 56, fmt: (v) => v.toFixed(2) },
  { id: "line", label: "Line (m from centre)", ch: "lat_m", unit: "m", h: 60, fmt: (v) => v.toFixed(1) },
  { id: "slip", label: "Body slip", ch: "slip_deg", unit: "°", h: 52, fmt: (v) => v.toFixed(1) },
  { id: "rpm", label: "RPM", ch: "rpm", unit: "", h: 52, fmt: (v) => v.toFixed(0) },
  { id: "elev", label: "Elevation", ch: "y", unit: "m", h: 56, fmt: (v) => v.toFixed(1) },
];

interface Props {
  grid: Grid | null;
  lanes: string[];
  view: [number, number];
  full: [number, number];
  cursorA: number;
  cursorB: number | null;
  corners: PackCorner[];
  terrain: Terrain[];
  markers: MapMarker[];
  overlays: Overlay[];
  cliffs: { s0_m: number; s1_m: number; loss_s: number }[];
  labelA: string;
  labelB: string | null;
  onCursor: (s: number) => void;
  onView: (v: [number, number] | null) => void;
  relLabel: (s: number) => string;
}

const LEFT = 118;
const RIGHT = 12;
const TOP = 26; // corner band
const GAP = 6;

export function Traces(p: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);
  const size = useRef({ w: 600, h: 400 });
  const brush = useRef<{ x0: number; x1: number } | null>(null);
  const hoverX = useRef<number | null>(null);

  const lanes = ALL_LANES.filter((l) => p.lanes.includes(l.id) && (l.id !== "delta" || p.grid?.delta));

  const xOf = useCallback(
    (s: number) => LEFT + ((s - p.view[0]) / (p.view[1] - p.view[0] || 1)) * (size.current.w - LEFT - RIGHT),
    [p.view],
  );
  const sOf = useCallback(
    (x: number) => p.view[0] + ((x - LEFT) / (size.current.w - LEFT - RIGHT)) * (p.view[1] - p.view[0]),
    [p.view],
  );

  const draw = useCallback(() => {
    const c = cv.current;
    const g = p.grid;
    if (!c) return;
    const ctx = c.getContext("2d")!;
    const dpr = window.devicePixelRatio || 1;
    const { w, h } = size.current;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!g) return;
    const [v0, v1] = p.view;
    const i0 = Math.max(0, Math.floor(v0 / g.step) - 1);
    const i1 = Math.min(g.s.length - 1, Math.ceil(v1 / g.step) + 1);
    const plotW = w - LEFT - RIGHT;

    // corner band + labels
    ctx.font = "11px ui-sans-serif, system-ui";
    for (const cn of p.corners) {
      if (cn.end_m < v0 || cn.start_m > v1) continue;
      const xa = Math.max(LEFT, xOf(cn.start_m));
      const xb = Math.min(w - RIGHT, xOf(cn.end_m));
      ctx.fillStyle = "rgba(148,163,184,0.10)";
      ctx.fillRect(xa, TOP, xb - xa, h - TOP);
      ctx.fillStyle = "rgba(148,163,184,0.25)";
      ctx.fillRect(xa, 4, xb - xa, 16);
      ctx.fillStyle = "#e2e8f0";
      const lbl = cn.display_name || cn.name;
      ctx.save();
      ctx.beginPath();
      ctx.rect(xa, 4, xb - xa, 16);
      ctx.clip();
      ctx.fillText(lbl, xa + 4, 16);
      ctx.restore();
      const xp = xOf(cn.apex_m);
      if (xp > LEFT && xp < w - RIGHT) {
        ctx.strokeStyle = "rgba(226,232,240,0.35)";
        ctx.setLineDash([2, 3]);
        ctx.beginPath();
        ctx.moveTo(xp, TOP);
        ctx.lineTo(xp, h);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    // variance cliffs (where lap-to-lap spread costs time)
    for (const cl of p.cliffs) {
      if (cl.s1_m < v0 || cl.s0_m > v1) continue;
      const xa = Math.max(LEFT, xOf(cl.s0_m));
      const xb = Math.min(w - RIGHT, xOf(cl.s1_m));
      ctx.fillStyle = "rgba(250,204,21,0.06)";
      ctx.fillRect(xa, TOP, xb - xa, h - TOP);
    }
    // overlay zones
    for (const o of p.overlays) {
      if (o.s0_m == null || o.s1_m == null) continue;
      const xa = Math.max(LEFT, xOf(o.s0_m));
      const xb = Math.min(w - RIGHT, xOf(o.s1_m));
      if (xb <= xa) continue;
      ctx.fillStyle = "rgba(244,114,182,0.12)";
      ctx.fillRect(xa, TOP, xb - xa, h - TOP);
    }

    let y = TOP + 4;
    const readA = (lane: LaneDef, s: number) => (lane.ch ? gridValue(g, g.a[lane.ch], s) : NaN);
    const readB = (lane: LaneDef, s: number) => (lane.ch && g.b ? gridValue(g, g.b[lane.ch], s) : NaN);
    for (const lane of lanes) {
      const lh = lane.h;
      // range
      let lo = lane.min ?? Infinity,
        hi = lane.max ?? -Infinity;
      const series: Float64Array[] = [];
      if (lane.id === "delta" && g.delta) series.push(g.delta);
      else if (lane.ch) {
        series.push(g.a[lane.ch]);
        if (g.b) series.push(g.b[lane.ch]);
      }
      if (lane.min === undefined || lane.max === undefined) {
        for (const arr of series)
          for (let i = i0; i <= i1; i++) {
            const v = arr[i];
            if (v < lo) lo = v;
            if (v > hi) hi = v;
          }
        if (lane.id === "delta") {
          const m = Math.max(0.05, Math.abs(lo), Math.abs(hi));
          lo = -m;
          hi = m;
        } else if (lane.id === "steer" || lane.id === "g_lat" || lane.id === "line" || lane.id === "slip") {
          const m = Math.max(Math.abs(lo), Math.abs(hi), 0.1);
          lo = -m;
          hi = m;
        }
        const pad = (hi - lo) * 0.08 || 1;
        lo -= pad;
        hi += pad;
      }
      const Yv = (v: number) => y + lh - ((v - lo) / (hi - lo || 1)) * lh;
      // lane frame
      ctx.fillStyle = "rgba(15,23,42,0.55)";
      ctx.fillRect(LEFT, y, plotW, lh);
      ctx.strokeStyle = "rgba(51,65,85,0.8)";
      ctx.strokeRect(LEFT + 0.5, y + 0.5, plotW - 1, lh - 1);
      if (lo < 0 && hi > 0) {
        ctx.strokeStyle = "rgba(100,116,139,0.6)";
        ctx.beginPath();
        ctx.moveTo(LEFT, Yv(0));
        ctx.lineTo(w - RIGHT, Yv(0));
        ctx.stroke();
      }
      // terrain shading on elevation lane
      if (lane.id === "elev") {
        for (const t of p.terrain) {
          if (t.end_m < v0 || t.start_m > v1) continue;
          ctx.fillStyle = t.kind === "crest" ? "rgba(250,204,21,0.18)" : "rgba(56,189,248,0.18)";
          const xa = Math.max(LEFT, xOf(t.start_m)),
            xb = Math.min(w - RIGHT, xOf(t.end_m));
          ctx.fillRect(xa, y, xb - xa, lh);
          ctx.fillStyle = t.kind === "crest" ? "#facc15" : "#38bdf8";
          ctx.font = "10px ui-sans-serif, system-ui";
          ctx.fillText(`${t.kind} ${t.dg_at_100kmh > 0 ? "+" : ""}${t.dg_at_100kmh.toFixed(2)}g@100`, xa + 3, y + 11);
        }
      }
      ctx.save();
      ctx.beginPath();
      ctx.rect(LEFT, y, plotW, lh);
      ctx.clip();
      if (lane.id === "delta" && g.delta) {
        // filled Δ: red above zero = A losing, green below = A gaining
        const z = Yv(0);
        for (let i = i0 + 1; i <= i1; i++) {
          const xa = xOf(g.s[i - 1]),
            xb = xOf(g.s[i]);
          const d = g.delta[i];
          ctx.fillStyle = d > 0 ? "rgba(239,68,68,0.35)" : "rgba(34,197,94,0.35)";
          ctx.fillRect(xa, Math.min(z, Yv(d)), xb - xa + 0.5, Math.abs(Yv(d) - z));
        }
        ctx.strokeStyle = "#f8fafc";
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        for (let i = i0; i <= i1; i++) (i === i0 ? ctx.moveTo(xOf(g.s[i]), Yv(g.delta[i])) : ctx.lineTo(xOf(g.s[i]), Yv(g.delta[i])));
        ctx.stroke();
      } else if (lane.ch) {
        const plot = (arr: Float64Array, color: string, width: number) => {
          ctx.strokeStyle = color;
          ctx.lineWidth = width;
          ctx.beginPath();
          for (let i = i0; i <= i1; i++) (i === i0 ? ctx.moveTo(xOf(g.s[i]), Yv(arr[i])) : ctx.lineTo(xOf(g.s[i]), Yv(arr[i])));
          ctx.stroke();
        };
        if (g.b) plot(g.b[lane.ch], COLORS.B, 1.4);
        plot(g.a[lane.ch], COLORS.A, 1.6);
      }
      ctx.restore();
      // labels + values at cursor
      ctx.fillStyle = "#cbd5e1";
      ctx.font = "600 11px ui-sans-serif, system-ui";
      ctx.fillText(lane.label, 8, y + 14);
      ctx.font = "11px ui-monospace, SFMono-Regular, Menlo, monospace";
      if (lane.id === "delta" && g.delta) {
        const d = gridValue(g, g.delta, p.cursorA);
        ctx.fillStyle = d > 0 ? COLORS.lose : COLORS.gain;
        ctx.fillText(`${d > 0 ? "+" : ""}${d.toFixed(3)} s`, 8, y + 30);
      } else if (lane.ch) {
        const f = lane.fmt ?? ((v: number) => v.toFixed(1));
        ctx.fillStyle = COLORS.A;
        ctx.fillText(`${f(readA(lane, p.cursorA))} ${lane.unit}`, 8, y + 30);
        if (g.b) {
          ctx.fillStyle = COLORS.B;
          ctx.fillText(`${f(readB(lane, p.cursorB ?? p.cursorA))} ${lane.unit}`, 8, y + 44);
        }
      }
      y += lh + GAP;
    }

    // event ticks under the corner band
    for (const m of p.markers) {
      if (m.s < v0 || m.s > v1) continue;
      const x = xOf(m.s);
      ctx.strokeStyle = m.who === "A" ? COLORS.A : COLORS.B;
      ctx.lineWidth = 2;
      ctx.beginPath();
      const yy = m.who === "A" ? TOP : TOP + 4;
      ctx.moveTo(x, yy);
      ctx.lineTo(x, yy + 6);
      ctx.stroke();
      if (m.kind === "brake_on" || m.kind === "turn_in" || m.kind === "full_throttle") {
        ctx.globalAlpha = 0.35;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, TOP);
        ctx.lineTo(x, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
      }
    }
    // pins
    ctx.font = "11px ui-sans-serif, system-ui";
    for (const o of p.overlays) {
      if (o.at_m == null || o.at_m < v0 || o.at_m > v1) continue;
      const x = xOf(o.at_m);
      ctx.fillStyle = o.driver === "ref" ? COLORS.B : o.driver === "me" ? COLORS.A : "#f472b6";
      ctx.beginPath();
      ctx.moveTo(x, TOP + 10);
      ctx.lineTo(x - 5, TOP);
      ctx.lineTo(x + 5, TOP);
      ctx.closePath();
      ctx.fill();
    }

    // cursors
    const drawCursor = (s: number, color: string, label: string) => {
      if (s < v0 || s > v1) return;
      const x = xOf(s);
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x, TOP);
      ctx.lineTo(x, y - GAP);
      ctx.stroke();
      ctx.fillStyle = color;
      ctx.font = "600 10px ui-sans-serif, system-ui";
      ctx.fillText(label, x + 4, y - GAP - 4);
    };
    if (p.cursorB != null && Math.abs(p.cursorB - p.cursorA) > 0.5) drawCursor(p.cursorB, COLORS.B, p.labelB ?? "B");
    drawCursor(p.cursorA, "#f8fafc", p.relLabel(p.cursorA));
    if (hoverX.current != null && !brush.current) {
      ctx.strokeStyle = "rgba(248,250,252,0.25)";
      ctx.beginPath();
      ctx.moveTo(hoverX.current, TOP);
      ctx.lineTo(hoverX.current, y - GAP);
      ctx.stroke();
    }
    // brush
    if (brush.current) {
      const xa = Math.min(brush.current.x0, brush.current.x1),
        xb = Math.max(brush.current.x0, brush.current.x1);
      ctx.fillStyle = "rgba(76,194,255,0.15)";
      ctx.fillRect(xa, TOP, xb - xa, y - TOP);
      ctx.strokeStyle = "rgba(76,194,255,0.7)";
      ctx.strokeRect(xa, TOP, xb - xa, y - TOP);
    }
    // distance axis
    ctx.fillStyle = "#64748b";
    ctx.font = "10px ui-sans-serif, system-ui";
    const span = v1 - v0;
    const stepM = [10, 20, 50, 100, 200, 500, 1000].find((s) => span / s <= 10) ?? 1000;
    for (let s = Math.ceil(v0 / stepM) * stepM; s <= v1; s += stepM) {
      const x = xOf(s);
      ctx.fillText(`${s}`, x - 8, y + 10);
    }
    ctx.fillText("m from S/F", LEFT - 70, y + 10);
  }, [p, lanes, xOf]);

  const totalH = TOP + 4 + lanes.reduce((a, l) => a + l.h + GAP, 0) + 16;

  useEffect(() => {
    const el = wrap.current;
    const c = cv.current;
    if (!el || !c) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      size.current = { w: Math.max(200, r.width), h: totalH };
      c.width = size.current.w * dpr;
      c.height = totalH * dpr;
      c.style.width = `${size.current.w}px`;
      c.style.height = `${totalH}px`;
      draw();
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [draw, totalH]);

  useEffect(() => {
    const c = cv.current;
    if (!c) return;
    const dpr = window.devicePixelRatio || 1;
    size.current.h = totalH;
    c.height = totalH * dpr;
    c.style.height = `${totalH}px`;
    draw();
  }, [draw, totalH]);

  useEffect(() => {
    const c = cv.current;
    if (!c) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = c.getBoundingClientRect();
      const s = sOf(e.clientX - r.left);
      const k = Math.exp(e.deltaY * 0.0015);
      const [a, b] = p.view;
      let na = s - (s - a) * k,
        nb = s + (b - s) * k;
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const shift = ((e.deltaX || e.deltaY) / 600) * (b - a);
        na = a + shift;
        nb = b + shift;
      }
      const span = Math.max(30, Math.min(p.full[1] - p.full[0], nb - na));
      na = Math.max(p.full[0], Math.min(p.full[1] - span, na));
      p.onView([na, na + span]);
    };
    c.addEventListener("wheel", onWheel, { passive: false });
    return () => c.removeEventListener("wheel", onWheel);
  }, [p, sOf]);

  const local = (e: React.PointerEvent) => e.clientX - cv.current!.getBoundingClientRect().left;

  return (
    <div ref={wrap} className="lab-traces">
      <canvas
        ref={cv}
        onPointerDown={(e) => {
          const x = local(e);
          if (x < LEFT) return;
          brush.current = { x0: x, x1: x };
          (e.target as HTMLElement).setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const x = local(e);
          hoverX.current = x >= LEFT ? x : null;
          if (brush.current) brush.current.x1 = x;
          draw();
        }}
        onPointerLeave={() => {
          hoverX.current = null;
          draw();
        }}
        onPointerUp={(e) => {
          const b = brush.current;
          brush.current = null;
          if (!b) return;
          const x = local(e);
          if (Math.abs(b.x1 - b.x0) > 8) {
            const s0 = sOf(Math.min(b.x0, b.x1)),
              s1 = sOf(Math.max(b.x0, b.x1));
            p.onView([Math.max(p.full[0], s0), Math.min(p.full[1], s1)]);
          } else p.onCursor(Math.max(p.full[0], Math.min(p.full[1], sOf(x))));
          draw();
        }}
        onDoubleClick={() => p.onView(null)}
        aria-label="Telemetry traces: click to move the cursor, drag to zoom into a range, scroll to zoom, shift-scroll to pan, double-click for the full lap"
      />
    </div>
  );
}
