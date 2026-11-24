// Replay video beside the telemetry: ACC replay recordings (OBS) synced to the lap clock of A and B.
// A capture session records both replays (full lap + trouble spots from several angles); angle clips
// show up as chips while the cursor is inside their corner.
import { useCallback, useEffect, useRef, useState } from "react";
import type { Slot } from "./types";

interface LapMap {
  laps?: number;
  lap_index?: number;
  lap_ms: number | null;
  complete: boolean;
  map: [number, number][];
}
export interface ReplayVideo {
  id: string;
  driver: string | null;
  camera: string;
  recorded: string;
  offset_s: number;
  available: boolean;
  file_windows?: string;
  kind?: "full" | "angle";
  corner?: string | null;
  pass_label?: string;
  laps: LapMap[];
}
interface CaptureStatus {
  state: string;
  error?: string;
  log: string[];
  laps?: number;
}
interface SessionStatus {
  state: string;
  eta_s?: number | null;
  elapsed_s?: number | null;
  estimate_s?: number;
  estimate_fresh_s?: number;
  plan?: {
    segments: { label: string; loss_s: number; lap_s: [number, number] }[];
    cameras: string[];
    passes: number;
    loss_covered_s: number;
    gap_s: number | null;
    rule: string;
  };
  prompt?: string;
  expect?: { driver: string; file: string; length_s: number } | null;
  acc_now?: { in_replay: boolean; file?: string; driver?: string; length_s?: number | null; file_ok: boolean; length_ok: boolean } | null;
  error?: string;
  steps: { driver: string; label: string; state: string }[];
  log: string[];
}

const FRAME = 1 / 60;
const fmtMin = (s: number) => (s < 90 ? `${Math.max(1, Math.round(s))} s` : `${Math.round(s / 60)} min`);
const ANGLE: Record<string, string> = {
  "Drivable/Dash": "Dash",
  "Drivable/Chase": "Chase",
  "Drivable/FarChase": "Far chase",
  "Drivable/Bonnet": "Bonnet",
  "Helicam/Helicam": "Helicam",
};
const angleName = (cam: string) => ANGLE[cam] ?? (cam.startsWith("set") ? "TV" : cam.split("/").pop() || cam);

/** Video time for a lap time, interpolating the recorded lap-time → video-time table. */
export function videoTimeAt(map: [number, number][], t: number): number | null {
  if (!map.length) return null;
  if (t < map[0][0] - 0.5 || t > map[map.length - 1][0] + 0.5) return null;
  if (t <= map[0][0]) return map[0][1] - (map[0][0] - t);
  for (let i = 1; i < map.length; i++) {
    const [a, va] = map[i - 1];
    const [b, vb] = map[i];
    if (t <= b) return b === a ? va : va + ((t - a) * (vb - va)) / (b - a);
  }
  const [l, vl] = map[map.length - 1];
  return vl + (t - l);
}

type Hit = { video: ReplayVideo; lap: LapMap };

/** Full-lap recording for a slot (newest first; angle clips excluded). */
export function findLapVideo(videos: ReplayVideo[], slot: Slot | null): Hit | null {
  if (!slot) return null;
  for (const v of [...videos].reverse()) {
    if (!v.available || v.driver !== slot.driver || v.kind === "angle") continue;
    const lap = v.laps.find((l) => l.lap_index === slot.lap);
    if (lap) return { video: v, lap };
  }
  return null;
}

/** Angle clips covering the slot's lap at lap time t (one per camera, newest wins). */
export function anglesAt(videos: ReplayVideo[], slot: Slot | null, t: number): Hit[] {
  if (!slot) return [];
  const by = new Map<string, Hit>();
  for (const v of videos) {
    if (!v.available || v.driver !== slot.driver || v.kind !== "angle") continue;
    const lap = v.laps.find((l) => l.lap_index === slot.lap);
    if (!lap || !lap.map.length) continue;
    if (t < lap.map[0][0] - 0.3 || t > lap.map[lap.map.length - 1][0] + 0.3) continue;
    by.set(v.camera, { video: v, lap });
  }
  return [...by.values()];
}

function SyncedVideo({
  bundleId,
  label,
  color,
  hit,
  lapT,
  playing,
  rate,
  onOffset,
  angles,
  angle,
  setAngle,
}: {
  bundleId: string;
  label: string;
  color: string;
  hit: Hit;
  lapT: number;
  playing: boolean;
  rate: number;
  onOffset: (id: string, off: number) => void;
  angles: Hit[];
  angle: string | null;
  setAngle: (cam: string | null) => void;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const prev = useRef<{ t: number; at: number } | null>(null);
  const [nudge, setNudge] = useState(false);
  const shown = (angle && angles.find((a) => a.video.camera === angle)) || hit;
  const target = videoTimeAt(shown.lap.map, lapT);
  const tv = target == null ? null : target + (shown.video.offset_s || 0);

  useEffect(() => {
    const el = ref.current;
    if (!el || tv == null) return;
    const now = performance.now();
    // rate of this car's lap clock vs wall time (≠ global rate for B in "same place" mode)
    let r = rate;
    if (prev.current && now - prev.current.at > 30) {
      const est = (lapT - prev.current.t) / ((now - prev.current.at) / 1000);
      if (isFinite(est) && est > 0) r = est;
    }
    prev.current = { t: lapT, at: now };
    if (playing) {
      // video seconds per lap second here (0.5 for a recording made at 2× replay speed)
      const a0 = videoTimeAt(shown.lap.map, lapT - 0.5);
      const a1 = videoTimeAt(shown.lap.map, lapT + 0.5);
      const slope = a0 != null && a1 != null && a1 > a0 ? a1 - a0 : 1;
      const pr = Math.min(16, Math.max(0.0625, r * slope));
      if (Math.abs(el.playbackRate - pr) > 0.02) el.playbackRate = pr;
      if (Math.abs(el.currentTime - tv) > 0.2 + 0.1 * pr) el.currentTime = tv;
      if (el.paused) void el.play().catch(() => undefined);
    } else {
      if (!el.paused) el.pause();
      if (Math.abs(el.currentTime - tv) > FRAME / 2) el.currentTime = tv;
    }
  }, [tv, playing, rate, lapT, shown.video.id]);

  return (
    <div className="lab-video">
      <video key={shown.video.id} ref={ref} src={`/api/bundles/${bundleId}/video/${shown.video.id}`} muted playsInline preload="metadata" />
      <div className="lab-video-tag" style={{ borderColor: color }}>
        <b style={{ color }}>{label}</b> L{shown.lap.lap_index}
        {angles.length === 0 && <span className="lab-muted"> · {angleName(shown.video.camera || "")}</span>}
        {tv == null && <span className="lab-muted"> · not recorded here</span>}
      </div>
      {angles.length > 0 && (
        <div className="lab-video-angles" role="group" aria-label="Camera angle">
          <button className={!angle || shown === hit ? "on" : ""} onClick={() => setAngle(null)}>
            {angleName(hit.video.camera || "Drivable/Dash")}
          </button>
          {angles.map((a) => (
            <button key={a.video.id} className={angle === a.video.camera ? "on" : ""} onClick={() => setAngle(a.video.camera)} title={a.video.pass_label}>
              {angleName(a.video.camera)}
            </button>
          ))}
        </div>
      )}
      <div className="lab-video-sync">
        {nudge ? (
          <>
            <button className="lab-btn" title="Video is ahead: shift it one frame later" onClick={() => onOffset(shown.video.id, (shown.video.offset_s || 0) - FRAME)}>
              −1f
            </button>
            <span className="lab-small" title="Manual sync nudge (saved)">
              {((shown.video.offset_s || 0) * 1000).toFixed(0)} ms
            </span>
            <button className="lab-btn" title="Video is behind: shift it one frame earlier" onClick={() => onOffset(shown.video.id, (shown.video.offset_s || 0) + FRAME)}>
              +1f
            </button>
          </>
        ) : null}
        <button className="lab-video-more" title="Fine-tune video sync" onClick={() => setNudge((n) => !n)}>
          ⋯
        </button>
      </div>
    </div>
  );
}

export function VideoPanel({
  bundleId,
  A,
  B,
  tA,
  tB,
  playing,
  rate,
  colors,
  onPickLap,
}: {
  bundleId: string;
  A: Slot | null;
  B: Slot | null;
  tA: number;
  tB: number | null;
  playing: boolean;
  rate: number;
  colors: { A: string; B: string };
  drivers: string[];
  onPickLap: (which: "A" | "B", slot: Slot) => void;
}) {
  const [videos, setVideos] = useState<ReplayVideo[]>([]);
  const [cap, setCap] = useState<CaptureStatus>({ state: "idle", log: [] });
  const [ses, setSes] = useState<SessionStatus>({ state: "idle", steps: [], log: [] });
  const [angleA, setAngleA] = useState<string | null>(null);
  const [angleB, setAngleB] = useState<string | null>(null);
  const [canJump, setCanJump] = useState(false);
  const [acc, setAcc] = useState<{ in_replay?: boolean; file?: string; bundle?: string; driver?: string; best_lap_index?: number } | null>(null);

  useEffect(() => {
    fetch("/api/acc/control")
      .then((r) => r.json())
      .then((d) => setCanJump(!!d.replay_control))
      .catch(() => setCanJump(false));
  }, []);
  useEffect(() => {
    let off = false;
    const poll = () =>
      fetch("/api/acc/replay")
        .then((r) => r.json())
        .then((d) => !off && setAcc(d.ok ? d : null))
        .catch(() => !off && setAcc(null));
    poll();
    const id = setInterval(poll, 4000);
    return () => {
      off = true;
      clearInterval(id);
    };
  }, [bundleId]);

  const reload = useCallback(() => {
    fetch(`/api/bundles/${bundleId}/videos`)
      .then((r) => (r.ok ? r.json() : { videos: [] }))
      .then((d) => setVideos(d.videos || []))
      .catch(() => setVideos([]));
  }, [bundleId]);
  useEffect(reload, [reload]);

  // single recordings
  const busy = ["connecting", "waiting", "recording", "stopping", "saving"].includes(cap.state);
  useEffect(() => {
    if (!busy) return;
    const id = setInterval(() => {
      fetch(`/api/bundles/${bundleId}/capture`)
        .then((r) => r.json())
        .then((s: CaptureStatus) => {
          setCap(s);
          if (s.state === "done") reload();
        })
        .catch(() => undefined);
    }, 700);
    return () => clearInterval(id);
  }, [busy, bundleId, reload]);
  const post = (body: object) =>
    fetch(`/api/bundles/${bundleId}/capture`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then((r) => r.json())
      .then((d) => setCap((c) => ({ ...c, state: d.ok ? d.state || c.state : "error", error: d.error })))
      .catch(() => setCap({ state: "error", error: "Launcher not reachable", log: [] }));

  // capture session (both replays)
  const sesBusy = ["starting", "starting_acc", "loading_replay", "waiting_for_load", "recording", "finishing"].includes(ses.state);
  useEffect(() => {
    fetch(`/api/bundles/${bundleId}/session`)
      .then((r) => r.json())
      .then((s: SessionStatus) => setSes(s))
      .catch(() => undefined);
  }, [bundleId]);
  useEffect(() => {
    if (!sesBusy) return;
    let done = 0;
    const id = setInterval(() => {
      fetch(`/api/bundles/${bundleId}/session`)
        .then((r) => r.json())
        .then((s: SessionStatus) => {
          setSes(s);
          const n = s.steps.filter((x) => x.state === "done").length;
          if (n !== done) {
            done = n;
            reload();
          }
        })
        .catch(() => undefined);
    }, 1000);
    return () => clearInterval(id);
  }, [sesBusy, bundleId, reload]);
  const session = (action: "start" | "stop", force = false) =>
    fetch(`/api/bundles/${bundleId}/session`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, force }) })
      .then(() => setSes((s) => ({ ...s, state: action === "start" ? "starting" : s.state })))
      .catch(() => undefined);

  const setOffset = (id: string, off: number) => {
    setVideos((vs) => vs.map((v) => (v.id === id ? { ...v, offset_s: off } : v)));
    fetch(`/api/bundles/${bundleId}/videos/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ offset_s: off }) }).catch(
      () => undefined,
    );
  };

  const hitA = findLapVideo(videos, A);
  const hitB = findLapVideo(videos, B);
  const recorded = (driver?: string) =>
    videos
      .filter((v) => v.available && v.driver === driver && v.kind !== "angle")
      .flatMap((v) => v.laps.filter((l) => l.lap_index != null && l.complete).map((l) => l.lap_index as number));

  const missing = (which: "A" | "B", slot: Slot | null, color: string) => {
    if (!slot) return null;
    const have = [...new Set(recorded(slot.driver))].sort((a, b) => a - b);
    return (
      <div className="lab-video lab-video--empty">
        <div>
          <b style={{ color }}>{slot.driver}</b> L{slot.lap}: no video yet
        </div>
        {have.length > 0 && (
          <div className="lab-small">
            Recorded laps:{" "}
            {have.map((n) => (
              <button key={n} className="lab-chip" onClick={() => onPickLap(which, { driver: slot.driver, lap: n })}>
                {n}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  };

  const stepsDone = ses.steps.filter((x) => x.state === "done").length;
  const current = ses.steps.find((x) => x.state === "recording");

  return (
    <div className="lab-videos">
      <div className="lab-video-row">
      {hitA ? (
        <SyncedVideo
          bundleId={bundleId}
          label={A!.driver}
          color={colors.A}
          hit={hitA}
          lapT={tA}
          playing={playing}
          rate={rate}
          onOffset={setOffset}
          angles={anglesAt(videos, A, tA)}
          angle={angleA}
          setAngle={(c) => {
            setAngleA(c);
            setAngleB(c);
          }}
        />
      ) : (
        missing("A", A, colors.A)
      )}
      {B &&
        (hitB && tB != null ? (
          <SyncedVideo
            bundleId={bundleId}
            label={B.driver}
            color={colors.B}
            hit={hitB}
            lapT={tB}
            playing={playing}
            rate={rate}
            onOffset={setOffset}
            angles={anglesAt(videos, B, tB)}
            angle={angleB}
            setAngle={(c) => {
              setAngleA(c);
              setAngleB(c);
            }}
          />
        ) : (
          missing("B", B, colors.B)
        ))}
      </div>

      <div className="lab-capture">
        {sesBusy ? (
          <div className="lab-session">
            {ses.prompt ? <b className="lab-session-prompt">{ses.prompt}</b> : <span>{current ? `Recording ${current.driver}: ${current.label}` : ses.state === "loading_replay" ? `Loading ${ses.expect?.driver ?? ""}'s replay in ACC…` : ses.state === "starting_acc" ? "Starting ACC…" : ses.state === "finishing" ? "Closing ACC…" : "Preparing…"}</span>}
            {ses.state === "waiting_for_load" && ses.expect && (
              <span className="lab-small" title="Recording starts only when both checks pass">
                ACC now:{" "}
                {ses.acc_now?.in_replay ? (
                  <>
                    <b className={ses.acc_now.file_ok ? "lab-ok" : "lab-err"}>
                      {ses.acc_now.file_ok ? "✓" : "✗"} {ses.acc_now.driver ? `${ses.acc_now.driver}'s replay` : ses.acc_now.file}
                    </b>{" "}
                    <b className={ses.acc_now.length_ok ? "lab-ok" : "lab-err"}>
                      {ses.acc_now.length_ok ? "✓" : "✗"} {ses.acc_now.length_s != null ? `${Math.round(ses.acc_now.length_s)} s` : "?"} (need {Math.round(ses.expect.length_s)} s)
                    </b>
                  </>
                ) : (
                  "no replay loaded"
                )}
              </span>
            )}
            <div className="lab-session-bar" title={`${stepsDone} of ${ses.steps.length} passes`}>
              <i style={{ width: `${ses.steps.length ? (100 * stepsDone) / ses.steps.length : 0}%` }} />
            </div>
            <span className="lab-small">
              {stepsDone}/{ses.steps.length} passes{ses.eta_s != null ? ` · ≈ ${fmtMin(ses.eta_s)} left` : ""}
            </span>
            <button className="lab-btn" onClick={() => session("stop")}>
              Cancel
            </button>
          </div>
        ) : busy ? (
          <>
            <span className="lab-small">{cap.state === "waiting" ? "Press play on the replay in ACC…" : `${cap.state}…`}</span>
            <button className="lab-btn" onClick={() => post({ action: "stop" })}>
              Stop
            </button>
          </>
        ) : (
          <>
            {canJump && ses.estimate_s === 0 ? (
              <>
                <span className="lab-small lab-ok">✓ Laps recorded</span>
                <button className="lab-btn" title={`Record everything again (≈ ${fmtMin(ses.estimate_fresh_s ?? 0)}); the older copies are deleted`} onClick={() => session("start", true)}>
                  re-record
                </button>
              </>
            ) : (
            <button
              className="lab-btn lab-btn--accent"
              disabled={!canJump}
              title={
                canJump
                  ? "ACC starts if needed, loads each replay itself and records: both full fastest laps first, then the trouble spots from Chase, Helicam, TV and Bonnet. Don't use the PC while it runs (ACC must stay in front)."
                  : "Needs the ACC replay control (UE4SS) installed — see docs/USAGE.md"
              }
              onClick={() => session("start")}
            >
              ● Record laps from ACC{ses.estimate_s ? ` · ≈ ${fmtMin(ses.estimate_s)}` : ""}
            </button>
            )}
            {acc?.in_replay && acc.bundle === bundleId && <span className="lab-small lab-muted">ACC: {acc.driver}'s replay</span>}
            {ses.plan && (
              <span className="lab-small lab-muted lab-plan" title={`Picked from the telemetry: ${ses.plan.rule}`}>
                {ses.plan.segments.map((sg) => `${sg.label} (−${sg.loss_s.toFixed(2)} s)`).join(" · ")} · {ses.plan.cameras.join("/")} · {ses.plan.passes} passes
                {ses.plan.gap_s ? ` · covers ${ses.plan.loss_covered_s.toFixed(2)} of ${ses.plan.gap_s.toFixed(2)} s` : ""}
              </span>
            )}
            {ses.state === "done" && <span className="lab-small lab-muted">Done · {stepsDone}/{ses.steps.length} recorded</span>}
            {ses.state === "error" && <span className="lab-small lab-err">{ses.error}</span>}
            {cap.state === "error" && <span className="lab-small lab-err">{cap.error}</span>}
          </>
        )}
      </div>
    </div>
  );
}
