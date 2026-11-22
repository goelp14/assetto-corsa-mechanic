// Driver HUDs (speed, gear, pedals, steering wheel, lap time) and a G-G friction-circle plot.
import { useEffect, useRef } from "react";
import { COLORS, fmtDelta, interp, type PreparedLap } from "./data";

interface HudProps {
  p: PreparedLap;
  s: number;
  color: string;
  label: string;
  deltaS?: number | null;
}

export function Hud({ p, s, color, label, deltaS }: HudProps) {
  const f = p.frames;
  const v = (k: keyof typeof f) => interp(f.s_m, f[k] as number[], s);
  const speed = v("speed_kmh");
  const thr = v("throttle");
  const brk = v("brake");
  const steer = v("steer_deg");
  const gear = Math.round(v("gear"));
  const t = v("t");
  const rpm = v("rpm");
  return (
    <div className="lab-hud" style={{ borderColor: color }}>
      <div className="lab-hud-top">
        <span className="lab-hud-name" style={{ color }}>
          {label}
        </span>
        <span className="lab-hud-lap">L{p.slot.lap}</span>
        <span className="lab-hud-time">{t.toFixed(2)} s</span>
      </div>
      <div className="lab-hud-main">
        <div className="lab-hud-speed">
          <b>{speed.toFixed(0)}</b>
          <small>km/h</small>
        </div>
        <div className="lab-hud-gear" title={`${rpm.toFixed(0)} rpm`}>
          {gear}
          <div className="lab-hud-rpm">
            <i style={{ width: `${Math.max(0, Math.min(100, ((rpm - 3000) / 5500) * 100))}%` }} />
          </div>
        </div>
        <svg className="lab-hud-wheel" viewBox="-24 -24 48 48" aria-label={`steering ${steer.toFixed(0)} degrees`}>
          <g transform={`rotate(${steer})`}>
            <circle r="19" fill="none" stroke="#cbd5e1" strokeWidth="4" />
            <line x1="-19" y1="0" x2="19" y2="0" stroke="#cbd5e1" strokeWidth="3" />
            <line x1="0" y1="0" x2="0" y2="19" stroke="#cbd5e1" strokeWidth="3" />
            <rect x="-2" y="-23" width="4" height="7" fill={color} />
          </g>
        </svg>
        <div className="lab-hud-pedals">
          <div className="lab-pedal" title="brake">
            <i style={{ height: `${brk * 100}%`, background: COLORS.brake }} />
          </div>
          <div className="lab-pedal" title="throttle">
            <i style={{ height: `${thr * 100}%`, background: COLORS.throttle }} />
          </div>
        </div>
      </div>
      {deltaS != null && isFinite(deltaS) && (
        <div className="lab-hud-delta" style={{ color: deltaS > 0 ? COLORS.lose : COLORS.gain }}>
          {fmtDelta(deltaS, 3)} s
        </div>
      )}
    </div>
  );
}

interface GgProps {
  A: PreparedLap | null;
  B: PreparedLap | null;
  range: [number, number];
  sA: number;
  sB: number | null;
}

export function GgPlot({ A, B, range, sA, sB }: GgProps) {
  const cv = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = cv.current;
    if (!c) return;
    const S = 150;
    const dpr = window.devicePixelRatio || 1;
    c.width = S * dpr;
    c.height = S * dpr;
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, S, S);
    const R = 3.2;
    const k = (S / 2 - 8) / R;
    const X = (g: number) => S / 2 - g * k; // right-hand corner (negative lat g) plots right
    const Y = (g: number) => S / 2 - g * k; // acceleration up, braking down
    ctx.strokeStyle = "rgba(100,116,139,0.5)";
    for (const r of [1, 2, 3]) {
      ctx.beginPath();
      ctx.arc(S / 2, S / 2, r * k, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(S / 2, 4);
    ctx.lineTo(S / 2, S - 4);
    ctx.moveTo(4, S / 2);
    ctx.lineTo(S - 4, S / 2);
    ctx.stroke();
    const dots = (p: PreparedLap, color: string) => {
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.45;
      const f = p.frames;
      for (let i = 0; i < f.s_m.length; i++) {
        if (f.s_m[i] < range[0] || f.s_m[i] > range[1]) continue;
        ctx.fillRect(X(f.g_lat[i]) - 1, Y(f.g_lon[i]) - 1, 2, 2);
      }
      ctx.globalAlpha = 1;
    };
    if (B) dots(B, COLORS.B);
    if (A) dots(A, COLORS.A);
    const cur = (p: PreparedLap, s: number, color: string) => {
      const f = p.frames;
      const gl = interp(f.s_m, f.g_lat, s),
        gn = interp(f.s_m, f.g_lon, s);
      ctx.fillStyle = color;
      ctx.strokeStyle = "#0b1220";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(X(gl), Y(gn), 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    };
    if (B && sB != null) cur(B, sB, COLORS.B);
    if (A) cur(A, sA, COLORS.A);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "9px ui-sans-serif, system-ui";
    ctx.fillText("accel", S / 2 + 3, 11);
    ctx.fillText("brake", S / 2 + 3, S - 5);
    ctx.fillText("1g 2g 3g", 4, S - 5);
  }, [A, B, range, sA, sB]);
  return (
    <div className="lab-gg" title="G-G: lateral vs longitudinal g in the current view range; dots = current position">
      <canvas ref={cv} style={{ width: 150, height: 150 }} />
    </div>
  );
}
