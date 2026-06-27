import { useCallback, useState } from "react";
import type { CoachResponse } from "../types";

const COACH_API = "/coach/ask";

const SUGGESTED = [
  "Why did I lose time here?",
  "Explain this spin",
  "What's my drill for next session?",
  "What should I do in this corner?",
];

export interface CoachPanelProps {
  sessionId: string | null;
  corner?: string | null;
  cornerDisplay?: string;
  lap?: number | null;
  playheadSpline?: number;
}

export function CoachPanel({
  sessionId,
  corner,
  cornerDisplay,
  lap,
  playheadSpline,
}: CoachPanelProps) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<CoachResponse | null>(null);

  const ask = useCallback(
    async (q: string) => {
      if (!sessionId || !q.trim()) return;
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(COACH_API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            bundle_id: sessionId,
            question: q.trim(),
            corner: corner ?? undefined,
            lap: lap ?? undefined,
            spline: playheadSpline,
          }),
        });
        if (!res.ok) {
          throw new Error("Coach request failed (%d)".replace("%d", String(res.status)));
        }
        const data = (await res.json()) as CoachResponse;
        setResponse(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        setLoading(false);
      }
    },
    [sessionId, corner, lap, playheadSpline],
  );

  const scope =
    [cornerDisplay ?? corner, lap != null ? `Lap ${lap}` : null].filter(Boolean).join(" · ") ||
    "Full stint";

  return (
    <section className="coach-panel">
      <header className="coach-panel-header">
        <strong>Race Engineer</strong>
        <span className="coach-scope">{scope}</span>
      </header>

      <div className="coach-suggestions">
        {SUGGESTED.map((s) => (
          <button
            key={s}
            type="button"
            className="coach-chip"
            disabled={loading || !sessionId}
            onClick={() => {
              setQuestion(s);
              void ask(s);
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <form
        className="coach-form"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this corner or incident…"
          disabled={loading || !sessionId}
        />
        <button type="submit" disabled={loading || !sessionId || !question.trim()}>
          {loading ? "…" : "Ask"}
        </button>
      </form>

      {error && <p className="coach-error">{error}</p>}

      {response && (
        <div className="coach-response">
          {response.summary && <p className="coach-summary">{response.summary}</p>}
          {response.what && (
            <div className="coach-block">
              <span className="coach-label">What</span>
              <p>{response.what}</p>
            </div>
          )}
          {response.why && (
            <div className="coach-block">
              <span className="coach-label">Why</span>
              <p>{response.why}</p>
            </div>
          )}
          {(response.how || response.drill) && (
            <div className="coach-block coach-drill">
              <span className="coach-label">Drill</span>
              <p>{response.drill || response.how}</p>
            </div>
          )}
          {response.citations?.length > 0 && (
            <div className="coach-citations">
              {response.citations.map((c) => (
                <span key={c} className="coach-cite">
                  {c}
                </span>
              ))}
            </div>
          )}
          <footer className="coach-meta">
            {response.confidence != null && (
              <span>Confidence {(response.confidence * 100).toFixed(0)}%</span>
            )}
            {response.status === "insufficient_evidence" && (
              <span className="coach-warn">Insufficient evidence</span>
            )}
          </footer>
        </div>
      )}
    </section>
  );
}
