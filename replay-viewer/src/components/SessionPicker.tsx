import { useMemo, useState } from "react";
import type { ReplayGame } from "../types";

export interface SessionIndexEntry {
  id: string;
  track: string;
  track_id: string;
  best_lap_ms: number | null;
  theoretical_best_ms: number | null;
  lap_count: number;
  bundle_url: string;
  game?: ReplayGame;
  source?: string;
  archive_note?: string;
  has_world_coords?: boolean;
  has_projected_coords?: boolean;
}

export interface SessionsIndex {
  sessions: SessionIndexEntry[];
  sessions_root: string;
  exports_root: string;
  latest_id: string | null;
  count: number;
}

export async function fetchSessionsIndex(): Promise<SessionsIndex | null> {
  try {
    const res = await fetch("/api/sessions");
    if (!res.ok) return null;
    return (await res.json()) as SessionsIndex;
  } catch {
    return null;
  }
}

function sessionGame(entry: SessionIndexEntry): ReplayGame {
  return entry.game ?? "ac";
}

function fmtLap(ms: number | null | undefined) {
  if (!ms) return "—";
  return (ms / 1000).toFixed(3) + "s";
}

interface Props {
  index: SessionsIndex;
  onSelect: (session: SessionIndexEntry) => void;
}

export function SessionPicker({ index, onSelect }: Props) {
  const [gameFilter, setGameFilter] = useState<ReplayGame>("ac");

  const filtered = useMemo(
    () => index.sessions.filter((s) => sessionGame(s) === gameFilter),
    [index.sessions, gameFilter],
  );

  const installLabel =
    gameFilter === "acc" ? "Assetto Corsa Competizione" : "Assetto Corsa";

  const isAccChrome = gameFilter === "acc";

  return (
    <div
      className={isAccChrome ? "session-picker session-picker--acc" : "session-picker"}
      style={{ padding: 32, maxWidth: 720, margin: "0 auto" }}
    >
      <h1 style={{ margin: "0 0 8px", color: "#f1f5f9" }}>
        VRE Replay
        {isAccChrome && (
          <span className="acc-badge acc-badge--lg" style={{ marginLeft: 12, verticalAlign: "middle" }}>
            ACC
          </span>
        )}
      </h1>
      <div className="game-filter-toggle" role="group" aria-label="Game filter">
        <button
          type="button"
          className={gameFilter === "ac" ? "active" : ""}
          onClick={() => setGameFilter("ac")}
        >
          AC
        </button>
        <button
          type="button"
          className={gameFilter === "acc" ? "active" : ""}
          onClick={() => setGameFilter("acc")}
        >
          ACC
        </button>
      </div>
      <p style={{ color: "#94a3b8", marginBottom: 24 }}>
        {filtered.length} session{filtered.length !== 1 ? "s" : ""}
        {gameFilter === "ac" ? " from your AC install" : ` from ${installLabel}`}
        {gameFilter === "acc" && filtered.length === 0 && (
          <> — none exported yet; drive with VRE on ACC and run replay sync.</>
        )}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {filtered.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s)}
            className={isAccChrome ? "session-picker-card session-picker-card--acc" : "session-picker-card"}
            style={{
              textAlign: "left",
              padding: "14px 16px",
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: 8,
              color: "#e2e8f0",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", minWidth: 0 }}>
                {sessionGame(s) === "acc" && (
                  <span className="acc-badge" title="Assetto Corsa Competizione">
                    ACC
                  </span>
                )}
                <strong style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{s.track}</strong>
              </div>
              <span style={{ color: "#22c55e", flexShrink: 0 }}>{fmtLap(s.best_lap_ms)}</span>
            </div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{s.id}</div>
            {s.source && (
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>Source: {s.source}</div>
            )}
            {s.lap_count > 0 && (
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>
                {s.lap_count} laps
                {s.theoretical_best_ms && s.best_lap_ms && (
                  <> · potential {fmtLap(s.theoretical_best_ms)}</>
                )}
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}