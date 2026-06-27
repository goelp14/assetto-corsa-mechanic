export interface SessionIndexEntry {
  id: string;
  track: string;
  track_id: string;
  best_lap_ms: number | null;
  theoretical_best_ms: number | null;
  lap_count: number;
  bundle_url: string;
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

function fmtLap(ms: number | null | undefined) {
  if (!ms) return "—";
  return (ms / 1000).toFixed(3) + "s";
}

interface Props {
  index: SessionsIndex;
  onSelect: (session: SessionIndexEntry) => void;
}

export function SessionPicker({ index, onSelect }: Props) {
  return (
    <div style={{ padding: 32, maxWidth: 720, margin: "0 auto" }}>
      <h1 style={{ margin: "0 0 8px", color: "#f1f5f9" }}>VRE Replay</h1>
      <p style={{ color: "#94a3b8", marginBottom: 24 }}>
        {index.count} session{index.count !== 1 ? "s" : ""} from your AC install
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {index.sessions.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onSelect(s)}
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
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <strong>{s.track}</strong>
              <span style={{ color: "#22c55e" }}>{fmtLap(s.best_lap_ms)}</span>
            </div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>{s.id}</div>
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
