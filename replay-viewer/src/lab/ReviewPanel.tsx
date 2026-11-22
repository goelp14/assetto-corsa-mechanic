// Video review: play coach-style scenes (auto or AI-written) and build your own from the current view.
import { useEffect, useState } from "react";
import { bundleIdFromBase, loadReview } from "./data";
import { relPos } from "./landmarks";
import type { LabBundle, Review, Scene } from "./types";

interface Props {
  bundle: LabBundle;
  active: { review: Review; scene: number; pauseText: string | null } | null;
  openReview: (r: Review, scene?: number) => void;
  playScene: (r: Review, i: number) => void;
  stop: () => void;
  resume: () => void;
  currentView: [number, number] | null;
  cursor: number;
  reviewsNonce: number;
  draftScenes: Scene[];
  setDraftScenes: (s: Scene[]) => void;
}

export function ReviewPanel(p: Props) {
  const [names, setNames] = useState<string[]>(p.bundle.reviews);
  const [loaded, setLoaded] = useState<Record<string, Review>>({});
  const [title, setTitle] = useState("");
  const [narr, setNarr] = useState("");
  const [cites, setCites] = useState("");
  const [saveName, setSaveName] = useState("my_review");
  const [errs, setErrs] = useState<string[] | null>(null);
  const corners = p.bundle.track?.corners ?? [];
  const id = bundleIdFromBase(p.bundle.base);

  useEffect(() => {
    fetch(`/api/bundles/${id}/reviews`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => j?.reviews && setNames(j.reviews))
      .catch(() => undefined);
  }, [id, p.reviewsNonce]);

  useEffect(() => {
    names.forEach((n) => {
      if (loaded[n] && p.reviewsNonce === 0) return;
      loadReview(p.bundle.base, n).then((r) => r && setLoaded((m) => ({ ...m, [n]: r })));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [names, p.reviewsNonce]);

  const addScene = () => {
    if (!p.currentView) return;
    const [s0, s1] = p.currentView;
    const near = corners.find((c) => c.apex_m >= s0 && c.apex_m <= s1);
    const win = p.bundle.analysis?.windows.find((w) => w.apex_m >= s0 && w.apex_m <= s1);
    const key = win ? `${win.corner}#${win.index}` : undefined;
    const me = p.bundle.analysis?.labels.me;
    const autoCites = key && me ? [`analysis.drivers.${me}.corners.${key}.best_lap`, `coaching.landmarks.${key}`] : [];
    p.setDraftScenes([
      ...p.draftScenes,
      {
        title: title || near?.display_name || `${s0.toFixed(0)}–${s1.toFixed(0)} m`,
        corner_key: key,
        s0_m: Math.round(s0),
        s1_m: Math.round(s1),
        mode: "dist",
        rate: 0.5,
        laps: { me: "best", ref: "best" },
        narration: narr,
        pauses: [],
        overlays: [],
        citations: cites ? cites.split(/[\s,]+/).filter(Boolean) : autoCites,
        author: "user",
      },
    ]);
    setTitle("");
    setNarr("");
    setCites("");
  };

  const addPause = (i: number) => {
    const sc = [...p.draftScenes];
    const text = window.prompt(`Callout at ${relPos(p.cursor, corners)}:`);
    if (!text) return;
    sc[i] = { ...sc[i], pauses: [...(sc[i].pauses ?? []), { at_m: Math.round(p.cursor), text }].sort((a, b) => a.at_m - b.at_m) };
    p.setDraftScenes(sc);
  };

  const draft: Review = { schema: "vre.review.v1", title: saveName.replace(/_/g, " "), author: "user", scenes: p.draftScenes };

  const save = async () => {
    setErrs(null);
    const r = await fetch(`/api/bundles/${id}/reviews/${encodeURIComponent(saveName)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) setErrs(j.errors ?? [j.error ?? `HTTP ${r.status}`]);
    else setErrs([]);
  };

  return (
    <div className="lab-panel">
      {p.active && (
        <div className="lab-now">
          <div className="lab-now-head">
            <b>{p.active.review.title}</b>
            <span className="lab-muted">
              scene {p.active.scene + 1}/{p.active.review.scenes.length}
            </span>
          </div>
          <div className="lab-now-title">{p.active.review.scenes[p.active.scene]?.title}</div>
          <p>{p.active.review.scenes[p.active.scene]?.narration}</p>
          {p.active.pauseText && <div className="lab-callout">{p.active.pauseText}</div>}
          <div className="lab-row-btns">
            {p.active.pauseText && (
              <button className="lab-btn lab-btn--accent" onClick={p.resume}>
                Continue ▶
              </button>
            )}
            <button className="lab-btn" disabled={p.active.scene === 0} onClick={() => p.playScene(p.active!.review, p.active!.scene - 1)}>
              ◀ Prev
            </button>
            <button className="lab-btn" disabled={p.active.scene >= p.active.review.scenes.length - 1} onClick={() => p.playScene(p.active!.review, p.active!.scene + 1)}>
              Next ▶
            </button>
            <button className="lab-btn" onClick={p.stop}>
              ■ Stop
            </button>
          </div>
        </div>
      )}
      <h3>Reviews</h3>
      <p className="lab-muted">
        Coach-style walkthroughs. "auto" is generated from the analysis; the AI (viewer MCP tools) or you can write more. Every number in
        a review must come from the data it cites — the server rejects anything else.
      </p>
      {names.map((n) => {
        const r = loaded[n];
        return (
          <div key={n} className="lab-review">
            <div className="lab-review-head">
              <b>{r?.title ?? n}</b>
              <span className="lab-muted lab-small">{r?.author ?? ""}</span>
              <button className="lab-btn lab-btn--accent" disabled={!r} onClick={() => r && p.playScene(r, 0)}>
                ▶ Play
              </button>
            </div>
            {r && (
              <ol className="lab-scenes">
                {r.scenes.map((s, i) => (
                  <li key={i}>
                    <button className="lab-linkbtn" onClick={() => p.playScene(r, i)}>
                      {s.title}
                    </button>
                    <span className="lab-muted lab-small"> {relPos(s.s0_m, corners)}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        );
      })}

      <h3>Build a review</h3>
      <p className="lab-muted lab-small">Frame a stretch in the traces (drag), describe it, add callouts at the cursor, then save.</p>
      <input className="lab-input" placeholder="Scene title (default: corner name)" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea className="lab-input" rows={3} placeholder="Narration — what to watch for" value={narr} onChange={(e) => setNarr(e.target.value)} />
      <input className="lab-input" placeholder="Citations (optional; default: this corner's analysis + landmarks)" value={cites} onChange={(e) => setCites(e.target.value)} />
      <button className="lab-btn" disabled={!p.currentView} onClick={addScene} title={p.currentView ? "" : "Zoom the traces to a range first"}>
        + Scene from current view
      </button>
      {p.draftScenes.length > 0 && (
        <>
          <ol className="lab-scenes">
            {p.draftScenes.map((s, i) => (
              <li key={i}>
                <button className="lab-linkbtn" onClick={() => p.playScene(draft, i)}>
                  {s.title}
                </button>{" "}
                <span className="lab-muted lab-small">{s.pauses?.length ?? 0} callouts</span>{" "}
                <button className="lab-chip" onClick={() => addPause(i)}>
                  + callout at cursor
                </button>{" "}
                <button className="lab-chip" onClick={() => p.setDraftScenes(p.draftScenes.filter((_, k) => k !== i))}>
                  remove
                </button>
              </li>
            ))}
          </ol>
          <div className="lab-row-btns">
            <input className="lab-input" style={{ flex: 1 }} value={saveName} onChange={(e) => setSaveName(e.target.value.replace(/[^A-Za-z0-9_-]/g, "_"))} />
            <button className="lab-btn lab-btn--accent" onClick={save}>
              Save
            </button>
          </div>
          {errs && errs.length === 0 && <div className="lab-ok">Saved.</div>}
          {errs && errs.length > 0 && (
            <ul className="lab-errs">
              {errs.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
