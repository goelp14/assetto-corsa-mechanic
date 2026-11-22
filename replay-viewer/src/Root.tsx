// Entry: Lap Studio for ACC replay bundles, the classic viewer for AC/VRE sessions.
import { useEffect, useState } from "react";
import App from "./App";
import { LapStudio } from "./lab/LapStudio";
import { LAB_SCHEMA } from "./lab/types";
import { fmtLap } from "./lab/data";

interface Entry {
  id: string;
  schema?: string;
  game?: string;
  track?: string;
  track_id?: string;
  car_id?: string;
  best_lap_ms?: number | null;
  bundle_url: string;
  created?: string;
  drivers?: string[];
}

function param(k: string) {
  return new URLSearchParams(window.location.search).get(k) ?? "";
}

export default function Root() {
  const [index, setIndex] = useState<Entry[] | null>(null);
  const [sel, setSel] = useState<string>(param("session") || param("bundle"));

  useEffect(() => {
    fetch("/api/sessions")
      .then((r) => (r.ok ? r.json() : { sessions: [] }))
      .then((j) => setIndex(j.sessions ?? []))
      .catch(() => setIndex([]));
  }, []);

  const go = (id: string) => {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("session", id);
    else url.searchParams.delete("session");
    url.searchParams.delete("bundle");
    url.searchParams.delete("pick");
    window.history.pushState({}, "", url.toString());
    setSel(id);
  };
  useEffect(() => {
    const onPop = () => setSel(param("session") || param("bundle"));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  if (index === null) return <div style={{ padding: 40, color: "#94a3b8", background: "#0a0f1a", height: "100vh" }}>Loading…</div>;
  const lab = index.filter((e) => e.schema === LAB_SCHEMA);
  const entry = index.find((e) => e.id === sel || e.bundle_url === sel);
  if (entry?.schema === LAB_SCHEMA) return <LapStudio key={entry.id} base={entry.bundle_url} onBack={() => go("")} />;
  if (sel.startsWith("/bundles/lab_")) return <LapStudio key={sel} base={sel} onBack={() => go("")} />;
  if (sel || param("pick") || !lab.length) return <App />;
  return <Home lab={lab} others={index.filter((e) => e.schema !== LAB_SCHEMA)} go={go} />;
}

function Home({ lab, others, go }: { lab: Entry[]; others: Entry[]; go: (id: string) => void }) {
  return (
    <div className="home">
      <header>
        <h1>VRE Replay</h1>
        <p>Frame-by-frame lap comparison, coaching and video review.</p>
      </header>
      <section>
        <h2>Lap Studio · ACC replays</h2>
        <div className="home-grid">
          {lab.map((e) => (
            <button key={e.id} className="home-card" onClick={() => go(e.id)}>
              <span className="home-badge">ACC</span>
              <b>{e.track}</b>
              <span className="home-car">{(e.car_id ?? "").replace(/_/g, " ")}</span>
              <span className="home-drivers">{(e.drivers ?? []).join(" vs ")}</span>
              <span className="home-best">{fmtLap(e.best_lap_ms ?? null)}</span>
              <span className="home-id">{e.created?.replace("T", " ") ?? e.id}</span>
            </button>
          ))}
        </div>
        <p className="home-hint">
          New comparison: <code>./replay.sh --rpy mine.rpy:You --ref faster.rpy:Ref</code>
        </p>
      </section>
      {others.length > 0 && (
        <section>
          <h2>VRE sessions ({others.length})</h2>
          <button className="home-more" onClick={() => (window.location.search = "?pick=1")}>
            Browse AC / ACC live-telemetry sessions →
          </button>
        </section>
      )}
    </div>
  );
}
