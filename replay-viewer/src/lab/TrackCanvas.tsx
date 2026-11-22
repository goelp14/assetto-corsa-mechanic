// Track map: official edges, rainbow/gain-loss racing line, real-footprint cars with trails, events, pins.
import { useCallback, useEffect, useRef } from "react";
import { COLORS, diverge, gridValue, indexAt, interp, interpAngle, ramp, type Grid, type PreparedLap } from "./data";
import type { Overlay, TrackData } from "./types";

export type MapColor = "delta" | "speed" | "pedals" | "gear" | "g_lat";

export interface MapMarker {
  s: number;
  who: "A" | "B";
  kind: "brake_on" | "brake_full" | "turn_in" | "vmin" | "throttle_on" | "full_throttle" | "cut";
}

interface Props {
  track: TrackData | null;
  A: PreparedLap | null;
  B: PreparedLap | null;
  grid: Grid | null;
  colorBy: MapColor;
  sA: number;
  sB: number | null;
  view: [number, number] | null;
  follow: boolean;
  fitNonce: number;
  markers: MapMarker[];
  overlays: Overlay[];
  showCorners: boolean;
  steeringRatio?: number;
  onSeek: (s: number) => void;
  onUserCamera?: () => void;
}

interface Cam {
  cx: number;
  cz: number;
  scale: number; // px per metre
}

const MARK_STYLE: Record<MapMarker["kind"], { color: string; label: string }> = {
  brake_on: { color: "#ef4444", label: "B" },
  brake_full: { color: "#b91c1c", label: "F" },
  turn_in: { color: "#e2e8f0", label: "T" },
  vmin: { color: "#facc15", label: "V" },
  throttle_on: { color: "#86efac", label: "t" },
  full_throttle: { color: "#22c55e", label: "G" },
  cut: { color: "#f97316", label: "!" },
};

function posAt(p: PreparedLap, s: number) {
  const f = p.frames;
  return { x: interp(f.s_m, f.x, s), z: interp(f.s_m, f.z, s) };
}

export function TrackCanvas(props: Props) {
  const { track, A, B, grid, colorBy, sA, sB, view, follow, fitNonce, markers, overlays, showCorners, onSeek, onUserCamera } = props;
  const ratio = props.steeringRatio ?? 11;
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const cam = useRef<Cam>({ cx: 0, cz: 0, scale: 1 });
  const size = useRef({ w: 300, h: 300 });
  const userCam = useRef(false);
  const drag = useRef<{ x: number; y: number; cx: number; cz: number; moved: boolean } | null>(null);

  const fitTo = useCallback(
    (pts: [number, number][]) => {
      if (!pts.length) return;
      let x0 = Infinity,
        x1 = -Infinity,
        z0 = Infinity,
        z1 = -Infinity;
      for (const [x, z] of pts) {
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (z < z0) z0 = z;
        if (z > z1) z1 = z;
      }
      const { w, h } = size.current;
      const pad = 36;
      const sc = Math.min((w - 2 * pad) / Math.max(20, x1 - x0), (h - 2 * pad) / Math.max(20, z1 - z0));
      cam.current = { cx: (x0 + x1) / 2, cz: (z0 + z1) / 2, scale: Math.min(sc, 30) };
    },
    [],
  );

  const fitDefault = useCallback(() => {
    userCam.current = false;
    if (view && A) {
      const f = A.frames;
      const pts: [number, number][] = [];
      for (let i = 0; i < f.s_m.length; i++) if (f.s_m[i] >= view[0] && f.s_m[i] <= view[1]) pts.push([f.x[i], f.z[i]]);
      if (pts.length > 2) return fitTo(pts);
    }
    const line = track?.left && track?.right ? [...track.left, ...track.right] : A ? A.frames.x.map((x, i) => [x, A.frames.z[i]] as [number, number]) : [];
    fitTo(line);
  }, [view, A, track, fitTo]);

  const draw = useCallback(() => {
    const c = canvas.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const { w, h } = size.current;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (follow && A) {
      const p = posAt(A, sA);
      cam.current.cx = p.x;
      cam.current.cz = p.z;
      if (!userCam.current) cam.current.scale = Math.max(cam.current.scale, 3.2);
    }
    const { cx, cz, scale } = cam.current;
    const X = (x: number) => (x - cx) * scale + w / 2;
    const Y = (z: number) => (z - cz) * scale + h / 2;

    // track surface + edges
    if (track?.left && track?.right && track.left.length > 2) {
      ctx.beginPath();
      track.left.forEach(([x, z], i) => (i ? ctx.lineTo(X(x), Y(z)) : ctx.moveTo(X(x), Y(z))));
      for (let i = track.right.length - 1; i >= 0; i--) ctx.lineTo(X(track.right[i][0]), Y(track.right[i][1]));
      ctx.closePath();
      ctx.fillStyle = "rgba(148,163,184,0.13)";
      ctx.fill("evenodd");
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(203,213,225,0.45)";
      for (const edge of [track.left, track.right]) {
        ctx.beginPath();
        edge.forEach(([x, z], i) => (i ? ctx.lineTo(X(x), Y(z)) : ctx.moveTo(X(x), Y(z))));
        ctx.closePath();
        ctx.stroke();
      }
      // start/finish
      if (track.left[0] && track.right[0]) {
        ctx.strokeStyle = "#f8fafc";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(X(track.left[0][0]), Y(track.left[0][1]));
        ctx.lineTo(X(track.right[0][0]), Y(track.right[0][1]));
        ctx.stroke();
      }
    }

    const step = track?.centerline && track.length_m ? track.length_m / track.centerline.length : 10;
    const cl = (s: number): [number, number] | null => {
      if (!track?.centerline?.length) return null;
      const n = track.centerline.length;
      const i = ((Math.round(s / step) % n) + n) % n;
      return track.centerline[i];
    };

    // terrain features (crest = car goes light, dip = car pressed down)
    if (track?.terrain && scale > 0.6) {
      ctx.font = "10px ui-sans-serif, system-ui";
      for (const t of track.terrain) {
        const p = cl(t.peak_m);
        if (!p) continue;
        const crest = t.kind === "crest";
        ctx.fillStyle = crest ? "rgba(250,204,21,0.9)" : "rgba(56,189,248,0.9)";
        const px = X(p[0]),
          py = Y(p[1]);
        ctx.beginPath();
        if (crest) {
          ctx.moveTo(px, py - 6);
          ctx.lineTo(px - 5, py + 3);
          ctx.lineTo(px + 5, py + 3);
        } else {
          ctx.moveTo(px, py + 6);
          ctx.lineTo(px - 5, py - 3);
          ctx.lineTo(px + 5, py - 3);
        }
        ctx.closePath();
        ctx.fill();
        if (scale > 2) ctx.fillText(`${crest ? "crest" : "dip"} ${t.dg_at_100kmh > 0 ? "+" : ""}${t.dg_at_100kmh.toFixed(2)}g@100`, px + 8, py + 3);
      }
    }

    // B line (comparison)
    if (B) {
      const f = B.frames;
      ctx.strokeStyle = COLORS.B;
      ctx.globalAlpha = 0.85;
      ctx.lineWidth = Math.max(1.2, Math.min(3, scale * 0.6));
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      for (let i = 0; i < f.x.length; i++) (i ? ctx.lineTo(X(f.x[i]), Y(f.z[i])) : ctx.moveTo(X(f.x[i]), Y(f.z[i])));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    // A line coloured by metric
    if (A) {
      const f = A.frames;
      const lw = Math.max(2.5, Math.min(7, scale * 1.2));
      ctx.lineWidth = lw;
      ctx.lineCap = "round";
      let vmin = Infinity,
        vmax = -Infinity;
      if (colorBy === "speed") {
        for (const v of f.speed_kmh) {
          if (v < vmin) vmin = v;
          if (v > vmax) vmax = v;
        }
      }
      for (let i = 1; i < f.x.length; i++) {
        let col: string;
        switch (colorBy) {
          case "delta": {
            const r = grid?.deltaRate ? gridValue(grid, grid.deltaRate, f.s_m[i]) : 0;
            col = grid?.deltaRate ? diverge(r / 1.2) : ramp((f.speed_kmh[i] - 40) / 260);
            break;
          }
          case "speed":
            col = ramp((f.speed_kmh[i] - vmin) / (vmax - vmin || 1));
            break;
          case "pedals":
            col = f.brake[i] > 0.05 ? `rgba(239,68,68,${0.35 + 0.65 * f.brake[i]})` : f.throttle[i] > 0.98 ? "#22c55e" : f.throttle[i] > 0.05 ? "#a3e635" : "#94a3b8";
            break;
          case "gear":
            col = ramp((f.gear[i] - 1) / 6);
            break;
          case "g_lat":
            col = ramp(Math.min(1, Math.abs(f.g_lat[i]) / 2.6));
            break;
        }
        ctx.strokeStyle = col;
        ctx.beginPath();
        ctx.moveTo(X(f.x[i - 1]), Y(f.z[i - 1]));
        ctx.lineTo(X(f.x[i]), Y(f.z[i]));
        ctx.stroke();
      }
      ctx.lineCap = "butt";
    }

    // view range brackets
    if (view && A) {
      for (const s of view) {
        const p = posAt(A, s);
        ctx.fillStyle = "#e2e8f0";
        ctx.beginPath();
        ctx.arc(X(p.x), Y(p.z), 3, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // corner labels
    if (showCorners && track?.corners) {
      ctx.font = `${scale > 2 ? 12 : 10}px ui-sans-serif, system-ui`;
      for (const c of track.corners) {
        const p = cl(c.apex_m);
        if (!p) continue;
        const px = X(p[0]),
          py = Y(p[1]);
        if (px < -40 || py < -20 || px > w + 40 || py > h + 20) continue;
        const label = c.display_name || c.name;
        const tw = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(15,23,42,0.78)";
        ctx.fillRect(px + 7, py - 15, tw + 8, 16);
        ctx.fillStyle = "#cbd5e1";
        ctx.fillText(label, px + 11, py - 3);
      }
    }

    // event markers
    const lapOf = (who: "A" | "B") => (who === "A" ? A : B);
    ctx.font = "bold 9px ui-sans-serif, system-ui";
    for (const m of markers) {
      const p = lapOf(m.who);
      if (!p) continue;
      const q = posAt(p, m.s);
      const st = MARK_STYLE[m.kind];
      const r = scale > 2 ? 7 : 5;
      ctx.beginPath();
      ctx.arc(X(q.x), Y(q.z), r, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(2,6,23,0.85)";
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = m.who === "A" ? COLORS.A : COLORS.B;
      ctx.stroke();
      if (r >= 7) {
        ctx.fillStyle = st.color;
        ctx.textAlign = "center";
        ctx.fillText(st.label, X(q.x), Y(q.z) + 3);
        ctx.textAlign = "left";
      } else {
        ctx.fillStyle = st.color;
        ctx.beginPath();
        ctx.arc(X(q.x), Y(q.z), 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // overlays / annotations
    for (const o of overlays) {
      const p = (o.driver === "ref" ? B : A) ?? A;
      if (!p) continue;
      const col = o.color || (o.driver === "ref" ? COLORS.B : o.driver === "me" ? COLORS.A : "#f472b6");
      if ((o.kind === "zone" || o.kind === "line") && o.s0_m != null && o.s1_m != null) {
        const f = p.frames;
        ctx.strokeStyle = col;
        ctx.globalAlpha = 0.45;
        ctx.lineWidth = Math.max(8, scale * 3);
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < f.s_m.length; i++) {
          if (f.s_m[i] < o.s0_m || f.s_m[i] > o.s1_m) continue;
          if (!started) {
            ctx.moveTo(X(f.x[i]), Y(f.z[i]));
            started = true;
          } else ctx.lineTo(X(f.x[i]), Y(f.z[i]));
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
      }
      const at = o.at_m ?? o.s0_m;
      if (at == null) continue;
      const q = posAt(p, at);
      const px = X(q.x),
        py = Y(q.z);
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(px - 6, py - 12);
      ctx.lineTo(px + 6, py - 12);
      ctx.closePath();
      ctx.fill();
      if (o.text) {
        ctx.font = "12px ui-sans-serif, system-ui";
        const lines = wrapText(ctx, o.text, 220);
        const bw = Math.max(...lines.map((l) => ctx.measureText(l).width)) + 12;
        const bh = lines.length * 15 + 8;
        let bx = px + 8,
          by = py - 14 - bh;
        if (bx + bw > w - 4) bx = px - 8 - bw;
        if (by < 4) by = py + 8;
        ctx.fillStyle = "rgba(2,6,23,0.9)";
        roundRect(ctx, bx, by, bw, bh, 6);
        ctx.fill();
        ctx.strokeStyle = col;
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.fillStyle = "#f1f5f9";
        lines.forEach((l, k) => ctx.fillText(l, bx + 6, by + 16 + k * 15));
      }
    }

    // cars + trails
    const drawCar = (p: PreparedLap, s: number, color: string) => {
      const f = p.frames;
      const t = interp(f.s_m, f.t, s);
      // trail: last 2.5 s
      const i1 = indexAt(f.t, t);
      const i0 = indexAt(f.t, t - 2.5);
      for (let i = i0 + 1; i <= i1; i++) {
        ctx.strokeStyle = color;
        ctx.globalAlpha = 0.15 + 0.6 * ((i - i0) / Math.max(1, i1 - i0));
        ctx.lineWidth = Math.max(2, Math.min(6, scale));
        ctx.beginPath();
        ctx.moveTo(X(f.x[i - 1]), Y(f.z[i - 1]));
        ctx.lineTo(X(f.x[i]), Y(f.z[i]));
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      const x = interp(f.s_m, f.x, s);
      const z = interp(f.s_m, f.z, s);
      const yaw = (interpAngle(f.s_m, f.yaw_deg, s) * Math.PI) / 180;
      const course = (interpAngle(f.s_m, f.course_deg, s) * Math.PI) / 180;
      const steer = (interp(f.s_m, f.steer_deg, s) / ratio) * (Math.PI / 180);
      const hx = Math.sin(yaw),
        hz = Math.cos(yaw);
      const rx = hz,
        rz = -hx; // body-right in world x/z
      const wb = (f.meta.wheel_body_m as [number, number][] | undefined) ?? [
        [1.4, 0.86],
        [1.4, -0.86],
        [-1.25, 0.86],
        [-1.25, -0.86],
      ];
      const front = Math.max(wb[0][0], wb[1][0]) + 0.9;
      const rear = Math.min(wb[2][0], wb[3][0]) - 0.85;
      const half = Math.max(Math.abs(wb[0][1]), Math.abs(wb[2][1])) + 0.15;
      const px = X(x),
        py = Y(z);
      const realLen = (front - rear) * scale;
      if (realLen < 16) {
        // marker: chevron of fixed size
        const L = 9;
        ctx.fillStyle = color;
        ctx.strokeStyle = "#0b1220";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(px + hx * L, py + hz * L);
        ctx.lineTo(px - hx * L * 0.6 + rx * L * 0.6, py - hz * L * 0.6 + rz * L * 0.6);
        ctx.lineTo(px - hx * L * 0.3, py - hz * L * 0.3);
        ctx.lineTo(px - hx * L * 0.6 - rx * L * 0.6, py - hz * L * 0.6 - rz * L * 0.6);
        ctx.closePath();
        ctx.stroke();
        ctx.fill();
        return;
      }
      const pt = (fwd: number, side: number): [number, number] => [X(x + hx * fwd + rx * side), Y(z + hz * fwd + rz * side)];
      // body
      const corners = [pt(front, half), pt(front, -half), pt(rear, -half), pt(rear, half)];
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      corners.forEach(([a, b], i) => (i ? ctx.lineTo(a, b) : ctx.moveTo(a, b)));
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "#0b1220";
      ctx.lineWidth = 1.5;
      ctx.stroke();
      // wheels at the measured contact points, fronts steered
      const tw = 0.33,
        tl = 0.68;
      wb.forEach(([fx, sy], k) => {
        const a = k < 2 ? steer : 0;
        const ca = Math.cos(a),
          sa = Math.sin(a);
        const whx = hx * ca + rx * sa,
          whz = hz * ca + rz * sa;
        const wrx = rx * ca - hx * sa,
          wrz = rz * ca - hz * sa;
        const cxw = x + hx * fx + rx * -sy,
          czw = z + hz * fx + rz * -sy;
        const q = (fw: number, sd: number) => [X(cxw + whx * fw + wrx * sd), Y(czw + whz * fw + wrz * sd)];
        ctx.fillStyle = "#0b1220";
        ctx.beginPath();
        [q(tl / 2, tw / 2), q(tl / 2, -tw / 2), q(-tl / 2, -tw / 2), q(-tl / 2, tw / 2)].forEach(([a1, b1], i) =>
          i ? ctx.lineTo(a1, b1) : ctx.moveTo(a1, b1),
        );
        ctx.closePath();
        ctx.fill();
      });
      // velocity vector vs heading = slip angle
      ctx.strokeStyle = "#f8fafc";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(px + Math.sin(course) * scale * 5, py + Math.cos(course) * scale * 5);
      ctx.stroke();
    };
    if (B && sB != null) drawCar(B, sB, COLORS.B);
    if (A) drawCar(A, sA, COLORS.A);

    // physical gap between the cars (same-moment mode)
    if (A && B && sB != null && Math.abs(sB - sA) > 0.5) {
      const pa = posAt(A, sA),
        pb = posAt(B, sB);
      ctx.strokeStyle = "rgba(248,250,252,0.5)";
      ctx.setLineDash([3, 3]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(X(pa.x), Y(pa.z));
      ctx.lineTo(X(pb.x), Y(pb.z));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = "bold 12px ui-sans-serif, system-ui";
      ctx.fillStyle = "#f8fafc";
      const gap = sB - sA;
      ctx.fillText(`${gap > 0 ? "B +" : "A +"}${Math.abs(gap).toFixed(1)} m`, (X(pa.x) + X(pb.x)) / 2 + 8, (Y(pa.z) + Y(pb.z)) / 2 - 8);
    }

    // scale bar
    const meters = niceMeters(90 / scale);
    ctx.fillStyle = "#94a3b8";
    ctx.fillRect(12, h - 16, meters * scale, 2);
    ctx.font = "10px ui-sans-serif, system-ui";
    ctx.fillText(`${meters} m`, 12, h - 21);
  }, [A, B, grid, colorBy, sA, sB, view, follow, markers, overlays, showCorners, track, ratio]);

  // size tracking
  useEffect(() => {
    const el = wrap.current;
    const c = canvas.current;
    if (!el || !c) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      const first = size.current.w === 300 && size.current.h === 300;
      size.current = { w: Math.max(50, r.width), h: Math.max(50, r.height) };
      c.width = size.current.w * dpr;
      c.height = size.current.h * dpr;
      c.style.width = `${size.current.w}px`;
      c.style.height = `${size.current.h}px`;
      if (first || !userCam.current) fitDefault();
      draw();
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fitDefault, draw]);

  useEffect(() => {
    fitDefault();
    draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view?.[0], view?.[1], fitNonce, A?.slot.driver, A?.slot.lap, track]);

  useEffect(() => {
    draw();
  }, [draw]);

  const toWorld = (ev: { clientX: number; clientY: number }) => {
    const r = canvas.current!.getBoundingClientRect();
    const { cx, cz, scale } = cam.current;
    return { x: (ev.clientX - r.left - size.current.w / 2) / scale + cx, z: (ev.clientY - r.top - size.current.h / 2) / scale + cz };
  };

  const onWheel = (ev: React.WheelEvent) => {
    const before = toWorld(ev);
    const k = Math.exp(-ev.deltaY * 0.0015);
    cam.current.scale = Math.max(0.05, Math.min(60, cam.current.scale * k));
    const after = toWorld(ev);
    cam.current.cx += before.x - after.x;
    cam.current.cz += before.z - after.z;
    userCam.current = true;
    onUserCamera?.();
    draw();
  };

  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const stop = (e: WheelEvent) => e.preventDefault();
    c.addEventListener("wheel", stop, { passive: false });
    return () => c.removeEventListener("wheel", stop);
  }, []);

  const onDown = (ev: React.PointerEvent) => {
    drag.current = { x: ev.clientX, y: ev.clientY, cx: cam.current.cx, cz: cam.current.cz, moved: false };
    (ev.target as HTMLElement).setPointerCapture(ev.pointerId);
  };
  const onMove = (ev: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    const dx = ev.clientX - d.x,
      dy = ev.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
    if (!d.moved) return;
    cam.current.cx = d.cx - dx / cam.current.scale;
    cam.current.cz = d.cz - dy / cam.current.scale;
    userCam.current = true;
    onUserCamera?.();
    draw();
  };
  const onUp = (ev: React.PointerEvent) => {
    const d = drag.current;
    drag.current = null;
    if (!d || d.moved || !A) return;
    const wpt = toWorld(ev);
    const f = A.frames;
    let best = -1,
      bd = Infinity;
    for (let i = 0; i < f.x.length; i++) {
      const dd = (f.x[i] - wpt.x) ** 2 + (f.z[i] - wpt.z) ** 2;
      if (dd < bd) {
        bd = dd;
        best = i;
      }
    }
    if (best >= 0 && Math.sqrt(bd) * cam.current.scale < 40) onSeek(f.s_m[best]);
  };

  return (
    <div ref={wrap} className="lab-map-canvas">
      <canvas
        ref={canvas}
        onWheel={onWheel}
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onDoubleClick={() => {
          fitDefault();
          draw();
        }}
        aria-label="Track map: click the line to move the cursor, drag to pan, scroll to zoom, double-click to fit"
      />
    </div>
  );
}

function niceMeters(x: number) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(1e-6, x))));
  for (const m of [1, 2, 5, 10]) if (m * p >= x) return m * p;
  return 10 * p;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export function wrapText(ctx: CanvasRenderingContext2D, text: string, maxW: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let cur = "";
  for (const wd of words) {
    const t = cur ? `${cur} ${wd}` : wd;
    if (ctx.measureText(t).width > maxW && cur) {
      lines.push(cur);
      cur = wd;
    } else cur = t;
  }
  if (cur) lines.push(cur);
  return lines.slice(0, 6);
}
