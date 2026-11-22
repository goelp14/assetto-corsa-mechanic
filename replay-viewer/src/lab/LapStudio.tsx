// Lap Studio: frame-accurate side-by-side ACC replay comparison with coaching, setup, limits and video review.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  bestLap,
  buildGrid,
  bundleIdFromBase,
  COLORS,
  fmtDelta,
  fmtLap,
  gridValue,
  interp,
  lapRow,
  loadBundle,
  loadLap,
  loadReview,
  prepareLap,
  resolveLapSpec,
  sAtTime,
  slotKey,
  timeAtS,
  type PreparedLap,
} from "./data";
import { GgPlot, Hud } from "./Hud";
import { relPos } from "./landmarks";
import { CoachingPanel, CornersPanel, LimitsPanel, SetupPanel, type StudioApi } from "./Panels";
import { ReviewPanel } from "./ReviewPanel";
import { TrackCanvas, type MapColor, type MapMarker } from "./TrackCanvas";
import { ALL_LANES, Traces } from "./Traces";
import type { Annotation, LabBundle, Overlay, Review, Scene, Slot } from "./types";
import "./lab.css";

type Tab = "coaching" | "corners" | "setup" | "limits" | "review";
const TABS: { id: Tab; label: string }[] = [
  { id: "coaching", label: "Coaching" },
  { id: "corners", label: "Corners" },
  { id: "review", label: "Video review" },
  { id: "setup", label: "Setup & physics" },
  { id: "limits", label: "Track limits" },
];
const RATES = [0.1, 0.25, 0.5, 1, 2, 4];
const DEFAULT_LANES = ["delta", "speed", "throttle", "brake", "steer", "gear", "line", "elev"];

function loadPref<T>(k: string, d: T): T {
  try {
    const v = localStorage.getItem(`lab_${k}`);
    return v ? (JSON.parse(v) as T) : d;
  } catch {
    return d;
  }
}
function savePref(k: string, v: unknown) {
  try {
    localStorage.setItem(`lab_${k}`, JSON.stringify(v));
  } catch {
    /* ignore */
  }
}

interface ActiveReview {
  review: Review;
  scene: number;
  pauseText: string | null;
}

export function LapStudio({ base, onBack }: { base: string; onBack: () => void }) {
  const [bundle, setBundle] = useState<LabBundle | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [A, setA] = useState<Slot | null>(null);
  const [B, setB] = useState<Slot | null>(null);
  const [pa, setPa] = useState<PreparedLap | null>(null);
  const [pb, setPb] = useState<PreparedLap | null>(null);
  const [tA, setTA] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(1);
  const [mode, setMode] = useState<"dist" | "time">("dist");
  const [syncS, setSyncS] = useState(0);
  const [view, setView] = useState<[number, number] | null>(null);
  const [lanes, setLanes] = useState<string[]>(() => loadPref("lanes", DEFAULT_LANES));
  const [mapColor, setMapColor] = useState<MapColor>(() => loadPref("mapColor", "delta" as MapColor));
  const [follow, setFollow] = useState(false);
  const [fitNonce, setFitNonce] = useState(0);
  const [tab, setTab] = useState<Tab>(() => loadPref("tab", "coaching" as Tab));
  const [showNotes, setShowNotes] = useState(true);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [liveAnn, setLiveAnn] = useState<Annotation[]>([]);
  const [active, setActive] = useState<ActiveReview | null>(null);
  const [draftScenes, setDraftScenes] = useState<Scene[]>([]);
  const [reviewsNonce, setReviewsNonce] = useState(0);
  const [live, setLive] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const endS = useRef<number | null>(null);
  const pendingPlay = useRef<{ s0: number; s1: number; rate?: number } | null>(null);

  // ---------- load ----------
  useEffect(() => {
    let off = false;
    loadBundle(base)
      .then((b) => {
        if (off) return;
        setBundle(b);
        setAnnotations(b.annotations);
        const me = b.manifest.drivers.find((d) => d.role === "me") ?? b.manifest.drivers[0];
        const ref = b.manifest.drivers.find((d) => d.role === "ref");
        const la = bestLap(b.manifest, me.label);
        if (la !== null) setA({ driver: me.label, lap: la });
        if (ref) {
          const lb = bestLap(b.manifest, ref.label);
          if (lb !== null) setB({ driver: ref.label, lap: lb });
        } else {
          // no reference replay: compare with own second-best lap
          const others = me.laps.filter((l) => l.lap_index !== la && !l.partial).sort((x, y) => x.lap_ms - y.lap_ms);
          if (others[0]) setB({ driver: me.label, lap: others[0].lap_index });
        }
      })
      .catch((e) => setErr(String(e)));
    return () => {
      off = true;
    };
  }, [base]);

  useEffect(() => {
    if (!bundle || !A) return;
    const row = lapRow(bundle.manifest, A);
    if (!row) return;
    let off = false;
    loadLap(bundle.base, row).then((f) => !off && f && setPa(prepareLap(A, f)));
    return () => {
      off = true;
    };
  }, [bundle, A]);
  useEffect(() => {
    if (!bundle || !B) {
      setPb(null);
      return;
    }
    const row = lapRow(bundle.manifest, B);
    if (!row) return;
    let off = false;
    loadLap(bundle.base, row).then((f) => !off && f && setPb(prepareLap(B, f)));
    return () => {
      off = true;
    };
  }, [bundle, B]);

  const ready = !!pa && slotKey(pa.slot) === slotKey(A) && (!B || (!!pb && slotKey(pb.slot) === slotKey(B)));
  const length = bundle?.manifest.track_length_m ?? bundle?.analysis?.length_m ?? 5000;
  const grid = useMemo(() => (pa ? buildGrid(pa, B && pb ? pb : null, length) : null), [pa, pb, B, length]);
  const corners = bundle?.track?.corners ?? bundle?.analysis?.pack.corners ?? [];

  // ---------- cursor ----------
  const sA = pa ? sAtTime(pa, tA) : 0;
  const sB = useMemo(() => {
    if (!pb || !pa) return null;
    if (mode === "dist") return sA;
    const tSyncA = timeAtS(pa, syncS);
    const tSyncB = timeAtS(pb, syncS);
    return sAtTime(pb, tSyncB + (tA - tSyncA));
  }, [pa, pb, mode, sA, tA, syncS]);
  const deltaAtCursor = grid?.delta ? gridValue(grid, grid.delta, sA) : null;

  const seek = useCallback(
    (s: number) => {
      if (!pa) return;
      setTA(timeAtS(pa, Math.max(-50, Math.min(length, s))));
    },
    [pa, length],
  );

  // ---------- playback ----------
  const state = useRef({ tA, playing, rate, pa, active, sA });
  state.current = { tA, playing, rate, pa, active, sA };
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    let last = performance.now();
    const loop = (now: number) => {
      const st = state.current;
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      if (!st.pa) return;
      let t = st.tA + dt * st.rate;
      const sNow = sAtTime(st.pa, t);
      // review pauses
      const sc = st.active ? st.active.review.scenes[st.active.scene] : null;
      if (sc?.pauses) {
        const hit = sc.pauses.find((p) => p.at_m > st.sA && p.at_m <= sNow);
        if (hit) {
          setTA(timeAtS(st.pa, hit.at_m));
          setPlaying(false);
          setActive({ ...st.active!, pauseText: hit.text });
          return;
        }
      }
      if (endS.current != null && sNow >= endS.current) {
        setTA(timeAtS(st.pa, endS.current));
        setPlaying(false);
        endS.current = null;
        return;
      }
      if (t >= st.pa.lapS) {
        t = st.pa.lapS;
        setTA(t);
        setPlaying(false);
        return;
      }
      setTA(t);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  const playRange = useCallback(
    (s0: number, s1: number, r?: number) => {
      if (!pa) return;
      setView([s0, s1]);
      setSyncS(s0);
      setTA(timeAtS(pa, s0));
      endS.current = s1;
      if (r) setRate(r);
      setPlaying(true);
    },
    [pa],
  );

  // corner framing: from just before braking to the exit
  const cornerRange = useCallback(
    (key: string): [number, number] | null => {
      const w = bundle?.analysis?.windows.find((x) => `${x.corner}#${x.index}` === key || x.corner === key);
      if (!w) {
        const c = corners.find((x) => x.display_name === key || x.name === key);
        return c ? [c.start_m - 150, c.end_m + 150] : null;
      }
      const ev = bundle?.analysis?.drivers[A?.driver ?? ""]?.corners[`${w.corner}#${w.index}`];
      const lapEv = ev?.laps.find((l) => l.lap_index === A?.lap) ?? ev?.best_lap;
      const brake = lapEv?.brake_on_m ?? lapEv?.turn_in_m ?? w.apex_m - 150;
      const s0 = Math.max(w.s0_m - 40, brake - 70);
      const s1 = Math.min(w.s1_m, w.apex_m + 230);
      return [s0, Math.max(s1, s0 + 120)];
    },
    [bundle, corners, A],
  );

  const focusCorner = useCallback(
    (key: string, play = false) => {
      const r = cornerRange(key);
      if (!r) return;
      setActive(null);
      if (play) {
        setMode((m) => m);
        playRange(r[0], r[1], 0.5);
      } else {
        setView(r);
        setSyncS(r[0]);
        seek(r[0]);
      }
    },
    [cornerRange, playRange, seek],
  );

  // ---------- reviews ----------
  const playScene = useCallback(
    (review: Review, i: number) => {
      if (!bundle) return;
      const sc = review.scenes[i];
      if (!sc) return;
      setPlaying(false);
      const nA = resolveLapSpec(bundle.manifest, "me", sc.laps?.me, A);
      const nB = resolveLapSpec(bundle.manifest, "ref", sc.laps?.ref, B);
      if (sc.mode) setMode(sc.mode);
      if (sc.lanes?.length) setLanes(Array.from(new Set(["delta", ...sc.lanes])).filter((l) => ALL_LANES.some((x) => x.id === l)));
      setActive({ review, scene: i, pauseText: null });
      setTab("review");
      const same = slotKey(nA) === slotKey(A) && slotKey(nB) === slotKey(B);
      if (same && ready) {
        pendingPlay.current = null;
        playRange(sc.s0_m, sc.s1_m, sc.rate ?? 0.5);
        return;
      }
      pendingPlay.current = { s0: sc.s0_m, s1: sc.s1_m, rate: sc.rate ?? 0.5 };
      if (slotKey(nA) !== slotKey(A)) setA(nA);
      if (slotKey(nB) !== slotKey(B)) setB(nB);
    },
    [bundle, A, B, ready, playRange],
  );

  useEffect(() => {
    if (ready && pendingPlay.current && pa) {
      const p = pendingPlay.current;
      pendingPlay.current = null;
      playRange(p.s0, p.s1, p.rate);
    }
  }, [ready, pa, playRange]);

  const resume = () => {
    if (!active) return;
    setActive({ ...active, pauseText: null });
    if (pa) setTA(timeAtS(pa, sA + 0.6));
    setPlaying(true);
  };

  // ---------- overlays & markers ----------
  const sceneOverlays: Overlay[] = useMemo(() => {
    if (!active) return [];
    const sc = active.review.scenes[active.scene];
    const out: Overlay[] = [...(sc?.overlays ?? [])];
    if (active.pauseText) {
      const p = sc?.pauses?.find((x) => x.text === active.pauseText);
      if (p) out.push({ kind: "pin", at_m: p.at_m, driver: (p.driver as "me" | "ref") ?? "me", text: p.text, color: "#f472b6" });
    }
    return out;
  }, [active]);
  const overlays = useMemo(() => [...sceneOverlays, ...(showNotes ? [...annotations, ...liveAnn] : [])], [sceneOverlays, annotations, liveAnn, showNotes]);

  const markers: MapMarker[] = useMemo(() => {
    const out: MapMarker[] = [];
    const an = bundle?.analysis;
    if (!an) return out;
    const add = (slot: Slot | null, who: "A" | "B") => {
      if (!slot) return;
      const d = an.drivers[slot.driver];
      if (!d) return;
      for (const c of Object.values(d.corners)) {
        const e = c.laps.find((l) => l.lap_index === slot.lap);
        if (!e) continue;
        const pairs: [MapMarker["kind"], number | null | undefined][] = [
          ["brake_on", e.brake_on_m],
          ["turn_in", e.turn_in_m],
          ["vmin", e.vmin_m],
          ["full_throttle", e.full_throttle_m],
        ];
        for (const [kind, s] of pairs) if (s != null) out.push({ s, who, kind });
      }
    };
    add(A, "A");
    add(B, "B");
    const lim = bundle?.limits?.drivers?.find((d) => d.label === A?.driver)?.laps.find((l) => l.lap_index === A?.lap);
    if (lim?.cut?.cut_m != null) out.push({ s: lim.cut.cut_m, who: "A", kind: "cut" });
    return out;
  }, [bundle, A, B]);

  // ---------- annotations ----------
  const persistAnnotations = useCallback(
    async (next: Annotation[]) => {
      setAnnotations(next);
      if (!bundle) return;
      try {
        await fetch(`/api/bundles/${bundleIdFromBase(bundle.base)}/annotations`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ annotations: next }),
        });
      } catch {
        setToast("Could not save the note (viewer opened without the launcher?)");
      }
    },
    [bundle],
  );
  const addNote = () => {
    const text = window.prompt(`Note at ${relPos(sA, corners)}:`);
    if (!text) return;
    persistAnnotations([...annotations, { kind: "pin", at_m: Math.round(sA * 10) / 10, driver: "me", text, author: "user", created: new Date().toISOString() }]);
  };

  // ---------- AI / live control (SSE from the launcher) ----------
  const handler = useRef<(m: { cmd: string; args: Record<string, unknown> }) => void>(() => undefined);
  handler.current = (m) => {
    const a = m.args || {};
    const num = (k: string) => (typeof a[k] === "number" ? (a[k] as number) : undefined);
    switch (m.cmd) {
      case "seek":
        setPlaying(false);
        if (num("s_m") != null) seek(num("s_m")!);
        else if (num("t_s") != null) setTA(num("t_s")!);
        break;
      case "play_range":
        if (a.mode === "dist" || a.mode === "time") setMode(a.mode);
        playRange(num("s0_m") ?? sA, num("s1_m") ?? sA + 300, num("rate"));
        break;
      case "pause":
        setPlaying(false);
        break;
      case "set_mode":
        if (a.mode === "dist" || a.mode === "time") setMode(a.mode);
        if (typeof a.rate === "number") setRate(a.rate);
        break;
      case "focus_corner":
        focusCorner(String(a.corner ?? a.key ?? ""), !!a.play);
        break;
      case "set_laps": {
        if (!bundle) break;
        const nA = a.me != null ? resolveLapSpec(bundle.manifest, "me", a.me as string | number, A) : A;
        const nB = a.ref != null ? resolveLapSpec(bundle.manifest, "ref", a.ref as string | number, B) : B;
        if (typeof a.A === "object" && a.A) setA(a.A as Slot);
        else setA(nA);
        if (typeof a.B === "object" && a.B) setB(a.B as Slot);
        else setB(nB);
        break;
      }
      case "annotate": {
        const list = (Array.isArray(a.annotations) ? a.annotations : [a.annotation ?? a]) as Annotation[];
        const clean = list.filter((x) => x && (x.at_m != null || x.s0_m != null)).map((x) => ({ ...x, kind: x.kind ?? "pin", author: x.author ?? "ai" }));
        if (a.persist) persistAnnotations([...annotations, ...clean]);
        else setLiveAnn((l) => [...l, ...clean]);
        break;
      }
      case "clear_annotations":
        setLiveAnn([]);
        if (a.persisted) persistAnnotations([]);
        break;
      case "open_review":
        if (bundle && typeof a.name === "string") {
          setReviewsNonce((n) => n + 1);
          loadReview(bundle.base, a.name).then((r) => r && playScene(r, typeof a.scene === "number" ? a.scene : 0));
        }
        break;
      case "add_scene":
        if (a.scene) setDraftScenes((d) => [...d, a.scene as Scene]);
        setTab("review");
        break;
      case "set_tab":
        if (TABS.some((t) => t.id === a.tab)) setTab(a.tab as Tab);
        break;
      case "set_map_color":
        if (["delta", "speed", "pedals", "gear", "g_lat"].includes(String(a.by))) setMapColor(a.by as MapColor);
        break;
      case "reload":
        if (a.what === "annotations" && bundle)
          fetch(`${bundle.base}/annotations.json`)
            .then((r) => r.json())
            .then((j) => setAnnotations(j.annotations ?? []))
            .catch(() => undefined);
        setReviewsNonce((n) => n + 1);
        break;
    }
    setToast(`AI: ${m.cmd.replace(/_/g, " ")}`);
  };
  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const es = new EventSource("/api/viewer/events");
    es.onopen = () => setLive(true);
    es.onerror = () => setLive(false);
    es.onmessage = (e) => {
      try {
        handler.current(JSON.parse(e.data));
      } catch {
        /* ignore */
      }
    };
    return () => es.close();
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2200);
    return () => clearTimeout(t);
  }, [toast]);

  // state report for the AI (what the viewer shows right now)
  const report = useRef({ last: "" });
  useEffect(() => {
    if (!bundle || !pa || !live) return;
    const id = setTimeout(() => {
      const v = (p: PreparedLap | null, s: number | null) =>
        p && s != null
          ? {
              lap: p.slot.lap,
              driver: p.slot.driver,
              s_m: +s.toFixed(1),
              t_s: +interp(p.frames.s_m, p.frames.t, s).toFixed(3),
              speed_kmh: +interp(p.frames.s_m, p.frames.speed_kmh, s).toFixed(1),
              throttle: +interp(p.frames.s_m, p.frames.throttle, s).toFixed(2),
              brake: +interp(p.frames.s_m, p.frames.brake, s).toFixed(2),
              gear: Math.round(interp(p.frames.s_m, p.frames.gear, s)),
              steer_deg: +interp(p.frames.s_m, p.frames.steer_deg, s).toFixed(1),
            }
          : null;
      const payload = {
        bundle: bundleIdFromBase(bundle.base),
        tab,
        mode,
        playing,
        rate,
        view,
        where: relPos(sA, corners),
        delta_s: deltaAtCursor != null ? +deltaAtCursor.toFixed(3) : null,
        A: v(pa, sA),
        B: v(pb, sB),
        review: active ? { title: active.review.title, scene: active.scene, paused_on: active.pauseText } : null,
        map_color: mapColor,
        live_annotations: liveAnn.length,
      };
      const s = JSON.stringify(payload);
      if (s === report.current.last) return;
      report.current.last = s;
      fetch("/api/viewer/state", { method: "POST", headers: { "Content-Type": "application/json" }, body: s }).catch(() => undefined);
    }, playing ? 600 : 150);
    return () => clearTimeout(id);
  }, [bundle, pa, pb, live, tab, mode, playing, rate, view, sA, sB, deltaAtCursor, active, mapColor, liveAnn, corners]);

  // ---------- keyboard ----------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const hz = pa?.frames.meta.pose_hz || 20;
      if (e.key === " ") {
        e.preventDefault();
        if (active?.pauseText) resume();
        else setPlaying((p) => !p);
      } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        setPlaying(false);
        const d = (e.shiftKey ? 1 : 1 / hz) * (e.key === "ArrowRight" ? 1 : -1);
        setTA((t) => Math.max(0, Math.min(pa?.lapS ?? t, t + d)));
      } else if (e.key === "]") setRate((r) => RATES[Math.min(RATES.length - 1, RATES.indexOf(r) + 1)] ?? r);
      else if (e.key === "[") setRate((r) => RATES[Math.max(0, RATES.indexOf(r) - 1)] ?? r);
      else if (e.key === "m") setMode((m) => (m === "dist" ? "time" : "dist"));
      else if (e.key === "f") setFollow((f) => !f);
      else if (e.key === "Escape") {
        setActive(null);
        setView(null);
        endS.current = null;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  useEffect(() => savePref("lanes", lanes), [lanes]);
  useEffect(() => savePref("mapColor", mapColor), [mapColor]);
  useEffect(() => savePref("tab", tab), [tab]);

  const api: StudioApi | null = bundle
    ? {
        bundle,
        A,
        B,
        focusCorner,
        seek: (s) => {
          setPlaying(false);
          seek(s);
        },
        setSlot: (w, s) => (w === "A" ? setA(s) : setB(s)),
        playRange: (s0, s1) => playRange(s0, s1, 0.5),
      }
    : null;

  if (err)
    return (
      <div className="lab lab-center">
        <p>Could not open this replay bundle: {err}</p>
        <button className="lab-btn" onClick={onBack}>
          ← Sessions
        </button>
      </div>
    );
  if (!bundle || !api) return <div className="lab lab-center">Loading Lap Studio…</div>;

  const m = bundle.manifest;
  const an = bundle.analysis;
  const theo = an?.drivers[A?.driver ?? ""]?.theoretical;
  const lapA = lapRow(m, A);
  const lapB = lapRow(m, B);
  const vr: [number, number] = view ?? [0, length];
  const scene = active ? active.review.scenes[active.scene] : null;
  const slotOptions = m.drivers.flatMap((d) =>
    d.laps.map((l) => ({
      v: `${d.label}#${l.lap_index}`,
      t: `${d.label} · L${l.lap_index} · ${fmtLap(l.lap_ms)}${l.valid === false ? " ✕" : ""}${l.partial ? " (partial)" : ""}${l.sync_ok === false ? " (unsynced)" : ""}${d.best_lap_index === l.lap_index ? " ★" : ""}`,
    })),
  );
  const parseSlot = (v: string): Slot | null => {
    if (!v) return null;
    const i = v.lastIndexOf("#");
    return { driver: v.slice(0, i), lap: Number(v.slice(i + 1)) };
  };
  const gap = lapA && lapB ? (lapA.lap_ms - lapB.lap_ms) / 1000 : null;

  return (
    <div className="lab">
      <header className="lab-header">
        <button className="lab-btn lab-btn--ghost" onClick={onBack} title="All sessions">
          ←
        </button>
        <div className="lab-title">
          <b>{m.track_display}</b>
          <span className="lab-muted">{(m.car_id ?? "").replace(/_/g, " ")}</span>
        </div>
        <div className="lab-slots">
          <label className="lab-slot" style={{ borderColor: COLORS.A }}>
            <span style={{ color: COLORS.A }}>A</span>
            <select value={slotKey(A)} onChange={(e) => setA(parseSlot(e.target.value))}>
              {slotOptions.map((o) => (
                <option key={o.v} value={o.v}>
                  {o.t}
                </option>
              ))}
            </select>
          </label>
          <label className="lab-slot" style={{ borderColor: COLORS.B }}>
            <span style={{ color: COLORS.B }}>B</span>
            <select value={slotKey(B)} onChange={(e) => setB(parseSlot(e.target.value))}>
              <option value="">— none —</option>
              {slotOptions.map((o) => (
                <option key={o.v} value={o.v}>
                  {o.t}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="lab-kpis">
          <Kpi label="A lap" value={fmtLap(lapA?.lap_ms)} color={COLORS.A} />
          {lapB && <Kpi label="B lap" value={fmtLap(lapB.lap_ms)} color={COLORS.B} />}
          {gap != null && <Kpi label="Gap" value={`${fmtDelta(gap, 3)} s`} color={gap > 0 ? COLORS.lose : COLORS.gain} />}
          {theo?.ok && theo.theoretical_best_s != null && (
            <Kpi label="A ideal lap" value={fmtLap(theo.theoretical_best_s * 1000)} hint={`best corner sectors from ${theo.laps_used} lap${theo.laps_used === 1 ? "" : "s"}: ${theo.potential_s?.toFixed(2)} s to find`} />
          )}
        </div>
        <span className={`lab-live ${live ? "on" : ""}`} title={live ? "AI connected: it can drive this view" : "Not connected to the launcher"}>
          ● {live ? "AI link" : "offline"}
        </span>
      </header>

      <div className="lab-body">
        <main className="lab-main">
          <section className="lab-stage">
            <TrackCanvas
              track={bundle.track}
              A={ready ? pa : null}
              B={ready ? pb : null}
              grid={ready ? grid : null}
              colorBy={mapColor}
              sA={sA}
              sB={sB}
              view={view}
              follow={follow}
              fitNonce={fitNonce}
              markers={markers}
              overlays={overlays}
              showCorners
              onSeek={(s) => {
                setPlaying(false);
                seek(s);
              }}
            />
            <div className="lab-huds">
              {pa && <Hud p={pa} s={sA} color={COLORS.A} label={A?.driver ?? "A"} deltaS={deltaAtCursor} />}
              {pb && sB != null && <Hud p={pb} s={sB} color={COLORS.B} label={B?.driver ?? "B"} />}
            </div>
            <div className="lab-mapctl">
              <select value={mapColor} onChange={(e) => setMapColor(e.target.value as MapColor)} aria-label="Colour the line by">
                <option value="delta">Colour: where time is lost/gained</option>
                <option value="speed">Colour: speed</option>
                <option value="pedals">Colour: brake / throttle</option>
                <option value="gear">Colour: gear</option>
                <option value="g_lat">Colour: lateral g</option>
              </select>
              <button className={`lab-btn ${follow ? "lab-btn--on" : ""}`} onClick={() => setFollow((f) => !f)} title="Follow car A (f)">
                Follow
              </button>
              <button className="lab-btn" onClick={() => setFitNonce((n) => n + 1)} title="Fit view">
                Fit
              </button>
              <button className={`lab-btn ${showNotes ? "lab-btn--on" : ""}`} onClick={() => setShowNotes((s) => !s)}>
                Notes
              </button>
            </div>
            {pa && <GgPlot A={pa} B={pb} range={vr} sA={sA} sB={sB} />}
            <MapLegend colorBy={mapColor} hasB={!!pb} />
            {scene && (
              <div className="lab-caption">
                <b>{scene.title}</b> {!active?.pauseText && scene.narration}
                {active?.pauseText && (
                  <div className="lab-caption-pause">
                    {active.pauseText}{" "}
                    <button className="lab-btn lab-btn--accent" onClick={resume}>
                      Continue ▶ (space)
                    </button>
                  </div>
                )}
              </div>
            )}
            {toast && <div className="lab-toast">{toast}</div>}
          </section>

          <section className="lab-transport">
            <button className="lab-btn lab-btn--accent lab-play" onClick={() => (active?.pauseText ? resume() : setPlaying((p) => !p))} aria-label={playing ? "Pause" : "Play"}>
              {playing ? "❚❚" : "▶"}
            </button>
            <button className="lab-btn" onClick={() => setTA((t) => Math.max(0, t - 1 / (pa?.frames.meta.pose_hz || 20)))} title="Previous frame (←)">
              ⏮
            </button>
            <button className="lab-btn" onClick={() => setTA((t) => Math.min(pa?.lapS ?? t, t + 1 / (pa?.frames.meta.pose_hz || 20)))} title="Next frame (→)">
              ⏭
            </button>
            <div className="lab-seg" role="group" aria-label="Playback rate">
              {RATES.map((r) => (
                <button key={r} className={r === rate ? "on" : ""} onClick={() => setRate(r)}>
                  {r}×
                </button>
              ))}
            </div>
            <div className="lab-seg" role="group" aria-label="Sync mode">
              <button className={mode === "dist" ? "on" : ""} onClick={() => setMode("dist")} title="Both cars at the same place: compare inputs at each metre">
                Same place
              </button>
              <button
                className={mode === "time" ? "on" : ""}
                onClick={() => {
                  setMode("time");
                  setSyncS(view ? view[0] : sA);
                }}
                title="Both cars released at the same moment from the start of the view: watch the gap open up"
              >
                Same moment
              </button>
            </div>
            <input
              className="lab-scrub"
              type="range"
              min={0}
              max={pa?.lapS ?? 1}
              step={0.01}
              value={tA}
              onChange={(e) => {
                setPlaying(false);
                setTA(Number(e.target.value));
              }}
              aria-label="Lap time scrubber"
            />
            <span className="lab-cursorpos" title="Cursor position">
              {relPos(sA, corners)}
            </span>
            <button className="lab-btn" onClick={addNote} title="Add a note at the cursor (saved to the bundle)">
              + Note
            </button>
          </section>

          <section className="lab-lanes">
            <div className="lab-lanechips">
              {ALL_LANES.map((l) => (
                <button key={l.id} className={`lab-chip ${lanes.includes(l.id) ? "on" : ""}`} onClick={() => setLanes((ls) => (ls.includes(l.id) ? ls.filter((x) => x !== l.id) : [...ls, l.id]))}>
                  {l.label}
                </button>
              ))}
              <span className="lab-muted lab-small" style={{ marginLeft: "auto" }}>
                drag = zoom · scroll = zoom · shift-scroll = pan · double-click = full lap
              </span>
            </div>
            <CornerStrip corners={corners} length={length} view={vr} onPick={(c) => focusCorner(c)} />
            <Traces
              grid={ready ? grid : null}
              lanes={lanes}
              view={vr}
              full={[0, length]}
              cursorA={sA}
              cursorB={mode === "time" ? sB : null}
              corners={corners}
              terrain={bundle.track?.terrain ?? []}
              markers={markers}
              overlays={overlays}
              cliffs={an?.variance_cliffs ?? []}
              labelA={A?.driver ?? "A"}
              labelB={B?.driver ?? null}
              onCursor={(s) => {
                setPlaying(false);
                seek(s);
              }}
              onView={(v) => setView(v)}
              relLabel={(s) => relPos(s, corners)}
            />
          </section>
        </main>

        <aside className="lab-side">
          <nav className="lab-tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
                {t.label}
              </button>
            ))}
          </nav>
          <div className="lab-sidebody">
            {tab === "coaching" && <CoachingPanel api={api} />}
            {tab === "corners" && <CornersPanel api={api} />}
            {tab === "setup" && <SetupPanel api={api} />}
            {tab === "limits" && <LimitsPanel api={api} />}
            {tab === "review" && (
              <ReviewPanel
                bundle={bundle}
                active={active}
                openReview={(r, i) => playScene(r, i ?? 0)}
                playScene={playScene}
                stop={() => {
                  setActive(null);
                  setPlaying(false);
                  endS.current = null;
                }}
                resume={resume}
                currentView={view}
                cursor={sA}
                reviewsNonce={reviewsNonce}
                draftScenes={draftScenes}
                setDraftScenes={setDraftScenes}
              />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Kpi({ label, value, color, hint }: { label: string; value: string; color?: string; hint?: string }) {
  return (
    <div className="lab-kpi" title={hint}>
      <span>{label}</span>
      <b style={{ color }}>{value}</b>
    </div>
  );
}

function MapLegend({ colorBy, hasB }: { colorBy: MapColor; hasB: boolean }) {
  const items: Record<MapColor, JSX.Element> = {
    delta: (
      <>
        <i style={{ background: COLORS.gain }} /> A gaining <i style={{ background: "#78808c" }} /> even <i style={{ background: COLORS.lose }} /> A losing
      </>
    ),
    speed: (
      <>
        <i className="lab-ramp" /> slow → fast
      </>
    ),
    pedals: (
      <>
        <i style={{ background: COLORS.brake }} /> brake <i style={{ background: "#94a3b8" }} /> coast <i style={{ background: "#a3e635" }} /> part <i style={{ background: COLORS.throttle }} /> full throttle
      </>
    ),
    gear: (
      <>
        <i className="lab-ramp" /> 1st → 6th
      </>
    ),
    g_lat: (
      <>
        <i className="lab-ramp" /> 0 → 2.6 g
      </>
    ),
  };
  return (
    <div className="lab-legend">
      <span>
        <i style={{ background: COLORS.A }} /> A
      </span>
      {hasB && (
        <span>
          <i style={{ background: COLORS.B }} /> B (dashed)
        </span>
      )}
      <span>{items[colorBy]}</span>
      <span title="Event markers on the line">B brake · T turn-in · V slowest · G full throttle · ▲ crest ▼ dip</span>
    </div>
  );
}

function CornerStrip({ corners, length, view, onPick }: { corners: { display_name: string; name: string; start_m: number; end_m: number; apex_m: number }[]; length: number; view: [number, number]; onPick: (k: string) => void }) {
  return (
    <div className="lab-cornerstrip" aria-label="Lap overview: click a corner to frame it">
      <span className="lab-cornerstrip-view" style={{ left: `${(view[0] / length) * 100}%`, width: `${((view[1] - view[0]) / length) * 100}%` }} />
      {corners.map((c, i) => (
        <button
          key={`${c.name}-${i}`}
          className="lab-cornerstrip-c"
          style={{ left: `${(c.start_m / length) * 100}%`, width: `${Math.max(0.6, ((c.end_m - c.start_m) / length) * 100)}%` }}
          title={c.display_name || c.name}
          onClick={() => onPick(c.display_name || c.name)}
        >
          <span>{c.display_name || c.name}</span>
        </button>
      ))}
    </div>
  );
}
