import type { Annotation } from "../types";

interface Props {
  notes: Annotation[];
  selectedId?: string | null;
  onSelect: (note: Annotation) => void;
}

export function CoachNotesPanel({ notes, selectedId, onSelect }: Props) {
  if (!notes.length) return null;

  const sorted = [...notes].sort((a, b) => {
    const la = a.lap ?? 0;
    const lb = b.lap ?? 0;
    if (la !== lb) return la - lb;
    return (a.spline ?? 0) - (b.spline ?? 0);
  });

  return (
    <div className="coach-notes-panel">
      <div className="coach-notes-panel-title">Coach notes ({notes.length})</div>
      <ul className="coach-notes-list">
        {sorted.map((n) => (
          <li key={n.id}>
            <button
              type="button"
              className={selectedId === n.id ? "selected" : ""}
              onClick={() => onSelect(n)}
            >
              <span className="coach-note-lap">L{n.lap ?? "?"}</span>
              <span className="coach-note-body">
                <strong>{n.title ?? "Coach note"}</strong>
                <span className="coach-note-loc">
                  {n.corner_display ?? n.corner ?? "track"}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
