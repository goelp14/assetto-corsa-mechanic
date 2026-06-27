import type { SessionIndexEntry } from "./SessionPicker";

interface Props {
  sessions: SessionIndexEntry[];
  currentId: string;
  focusCorner?: string | null;
}

/** Stint-to-stint hint when a prior session exists for the same track. */
export function StintComparison({ sessions, currentId, focusCorner }: Props) {
  const idx = sessions.findIndex((s) => s.id === currentId);
  const prior = idx > 0 ? sessions[idx - 1] : null;
  if (!prior || !focusCorner) return null;

  const cur = sessions[idx];
  const improved =
    cur.best_lap_ms != null &&
    prior.best_lap_ms != null &&
    cur.best_lap_ms < prior.best_lap_ms;

  return (
    <div className="stint-comparison">
      <span>vs prior stint ({prior.id.slice(0, 10)}…)</span>
      {improved ? (
        <span className="ok">
          Best lap improved by {((prior.best_lap_ms! - cur.best_lap_ms!) / 1000).toFixed(3)}s
        </span>
      ) : (
        <span>Track {focusCorner} — did the drill stick?</span>
      )}
    </div>
  );
}
