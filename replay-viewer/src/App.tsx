import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { TrackMap, type TrackMapHandle } from "./components/TrackMap";
import { TelemetryCharts } from "./components/TelemetryCharts";
import { GuidedChartStack } from "./components/GuidedChartStack";
import { Inspector } from "./components/Inspector";
import { SetupTimeline } from "./components/SetupTimeline";
import { LayerPanel } from "./components/LayerPanel";
import { ZoomToolbar } from "./components/ZoomToolbar";
import { KpiStrip } from "./components/KpiStrip";
import { SessionPlanCard } from "./components/SessionPlanCard";
import { AnalysisStepHeader, deriveAnalysisStep } from "./components/AnalysisStepHeader";
import { CursorReadout } from "./components/CursorReadout";
import { FormativeCheck } from "./components/FormativeCheck";
import { StintComparison } from "./components/StintComparison";
import { CoachPanel } from "./components/CoachPanel";
import { CoachNotesPanel } from "./components/CoachNotesPanel";
import {
  fetchSessionsIndex,
  SessionPicker,
  type SessionIndexEntry,
  type SessionsIndex,
} from "./components/SessionPicker";
import { computeDelta, computeStitchedDelta, useReplayData } from "./hooks/useReplayData";
import {
  detectChannelAvailability,
  mergeLayersWithAvailability,
} from "./utils/channelAvailability";
import { preparePlotSeries } from "./utils/telemetryDerived";
import { contractViewRange, expandViewRange, MIN_SELECT_SPAN, normalizeSplineRange, padSplineRange } from "./utils/viewRange";
import { throttle } from "./utils/throttle";
import { lapTimeLabel } from "./utils/formatCoachDrill";
import { defaultLayers, type Annotation, type ChannelAvailability, type CornerTimeLoss, type LayerState } from "./types";
import "uplot/dist/uPlot.min.css";

function cleanLapTrap(summary: { potential_gap_s?: number } | null) {
  if (!summary?.potential_gap_s || summary.potential_gap_s < 0.5) return null;
  return summary;
}

function sessionFromUrl(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get("session") ?? params.get("bundle") ?? "";
}

function setSessionUrl(id: string) {
  const url = new URL(window.location.href);
  if (id) {
    url.searchParams.set("session", id);
    url.searchParams.delete("bundle");
  } else {
    url.searchParams.delete("session");
    url.searchParams.delete("bundle");
  }
  window.history.replaceState({}, "", url.toString());
}

function loadViewMode(): "guided" | "explore" {
  try {
    const saved = localStorage.getItem("vre_view_mode");
    if (saved === "explore" || saved === "guided") return saved;
    if (localStorage.getItem("vre_expertise") === "expert") return "explore";
  } catch {
    /* ignore */
  }
  return "guided";
}

export default function App() {
  const [sessionsIndex, setSessionsIndex] = useState<SessionsIndex | null>(null);
  const [indexLoading, setIndexLoading] = useState(true);
  const [showPicker, setShowPicker] = useState(false);
  const [activeSession, setActiveSession] = useState<SessionIndexEntry | null>(null);
  const [bundlePath, setBundlePath] = useState(sessionFromUrl());

  const bundleBase = useMemo(() => {
    if (activeSession) return activeSession.bundle_url;
    if (bundlePath.startsWith("/bundles/")) return bundlePath;
    if (bundlePath) return bundlePath;
    return null;
  }, [activeSession, bundlePath]);

  const { data, loading, error, load } = useReplayData(bundleBase);

  const [selectedLap, setSelectedLap] = useState<number | null>(null);
  const [compareLap, setCompareLap] = useState<number | null>(null);
  const [playheadSpline, setPlayheadSpline] = useState(0);
  const [selectedAnnotation, setSelectedAnnotation] = useState<Annotation | null>(null);
  const [selectedCorner, setSelectedCorner] = useState<string | null>(null);
  const [viewRange, setViewRange] = useState<[number, number] | null>(null);
  const [previewRange, setPreviewRange] = useState<[number, number] | null>(null);
  const [layers, setLayers] = useState<LayerState>(defaultLayers);
  const [channelAvailability, setChannelAvailability] = useState<ChannelAvailability | null>(null);
  const [viewMode, setViewMode] = useState<"guided" | "explore">(loadViewMode);
  const [cornerListOpen, setCornerListOpen] = useState(false);
  const [exploreDrawerOpen, setExploreDrawerOpen] = useState(false);
  const [formativeDone, setFormativeDone] = useState(false);
  const [expertise, setExpertise] = useState(
    () => localStorage.getItem("vre_expertise") === "expert",
  );
  const mapRef = useRef<TrackMapHandle>(null);

  const setViewModePersist = useCallback((mode: "guided" | "explore") => {
    setViewMode(mode);
    localStorage.setItem("vre_view_mode", mode);
    if (mode === "explore") setExploreDrawerOpen(true);
  }, []);

  const throttledPlayhead = useMemo(
    () => throttle((s: number) => setPlayheadSpline(s), 32),
    [],
  );

  const onLayersChange = useCallback((l: LayerState) => {
    setLayers(l);
    localStorage.setItem("vre_layers", JSON.stringify(l));
  }, []);

  const openSession = useCallback(
    (entry: SessionIndexEntry) => {
      setActiveSession(entry);
      setShowPicker(false);
      setSessionUrl(entry.id);
      setSelectedLap(null);
      setCompareLap(null);
      setSelectedAnnotation(null);
      load(entry.bundle_url);
    },
    [load],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setIndexLoading(true);
      const index = await fetchSessionsIndex();
      if (cancelled) return;
      setSessionsIndex(index);
      setIndexLoading(false);

      if (!index || index.count === 0) return;

      const urlId = sessionFromUrl();
      const pick = urlId === "pick" || new URLSearchParams(window.location.search).get("pick") === "1";

      if (pick) {
        setShowPicker(true);
        return;
      }

      const target =
        index.sessions.find((s) => s.id === urlId) ??
        index.sessions.find((s) => s.bundle_url === urlId) ??
        (urlId ? null : index.sessions[0]);

      if (target) {
        setActiveSession(target);
        setSessionUrl(target.id);
        load(target.bundle_url);
      } else if (urlId) {
        setBundlePath(urlId);
        load(urlId);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const lapNums = useMemo(
    () => (data ? [...data.laps.keys()].sort((a, b) => a - b) : []),
    [data],
  );

  const bestLapNum = useMemo(() => {
    if (!data?.manifest.laps.length) return null;
    const fromManifest = data.manifest.laps.find(
      (l) => l.lap_time_ms === data.manifest.best_lap_ms,
    )?.lap;
    return fromManifest ?? lapNums[0] ?? null;
  }, [data, lapNums]);

  const activeLap = selectedLap ?? bestLapNum ?? lapNums[lapNums.length - 1] ?? null;

  const compareSamples = useMemo(() => {
    if (compareLap == null || activeLap == null || compareLap === activeLap || !data) return [];
    return data.laps.get(compareLap)?.samples ?? [];
  }, [compareLap, activeLap, data]);
  const allBundleSamples = useMemo(() => {
    if (!data) return [];
    const out: typeof samples = [];
    for (const lap of data.laps.values()) out.push(...lap.samples);
    return out;
  }, [data]);

  useEffect(() => {
    if (!data || !allBundleSamples.length) return;
    let saved: Partial<LayerState> | null = null;
    try {
      const raw = localStorage.getItem("vre_layers");
      if (raw) saved = JSON.parse(raw);
    } catch {
      saved = null;
    }
    const avail =
      data.manifest.channel_availability ??
      detectChannelAvailability(allBundleSamples, {
        hasGgEnvelope: !!data.ggEnvelope?.peak_ay?.length,
        hasTimeLoss: !!data.timeLoss,
        hasWorldCoords: data.manifest.has_world_coords,
        hasProjectedCoords: data.manifest.has_projected_coords,
      });
    setChannelAvailability(avail);
    setLayers(mergeLayersWithAvailability(saved, avail));
  }, [data, allBundleSamples]);

  const samples = activeLap != null ? data?.laps.get(activeLap)?.samples ?? [] : [];
  const plotSamples = useMemo(() => preparePlotSeries(samples), [samples]);
  const plotCompare = useMemo(() => preparePlotSeries(compareSamples), [compareSamples]);

  const trackLengthM = data?.timeLoss?.track_length_m ?? data?.manifest.track_length_m ?? 3337;

  const delta = useMemo(
    () =>
      plotSamples.length && plotCompare.length
        ? computeDelta(plotSamples, plotCompare, trackLengthM)
        : [],
    [plotSamples, plotCompare, trackLengthM],
  );

  useEffect(() => {
    if (!data || selectedLap != null || bestLapNum == null) return;
    setSelectedLap(bestLapNum);
  }, [data, bestLapNum, selectedLap]);

  useEffect(() => {
    if (compareLap != null && activeLap != null && compareLap === activeLap) {
      setCompareLap(null);
    }
  }, [activeLap, compareLap]);

  const activeTimeLoss = useMemo(() => {
    if (!data?.timeLoss || activeLap == null) return null;
    return data.timeLoss.laps[String(activeLap)] ?? null;
  }, [data?.timeLoss, activeLap]);

  const stitchedLoss = useMemo(() => {
    const tl = data?.timeLoss;
    if (!tl?.stitched_bucket_speed_kmh?.length || !plotSamples.length) return [];
    return computeStitchedDelta(
      plotSamples,
      tl.stitched_bucket_speed_kmh,
      tl.track_length_m,
      tl.num_buckets,
    );
  }, [data?.timeLoss, plotSamples]);

  const potentialGapS = useMemo(() => {
    if (activeTimeLoss?.potential_gap_s != null) return activeTimeLoss.potential_gap_s;
    return data?.stintSummary?.potential_gap_s ?? data?.timeLoss?.potential_gap_s ?? 0;
  }, [activeTimeLoss, data?.stintSummary, data?.timeLoss]);

  const cornerRange = useMemo((): [number, number] | null => {
    if (viewRange) return viewRange;
    if (!selectedCorner || !data?.geometry) return null;
    const c = data.geometry.corners.find((x) => x.id === selectedCorner);
    return c ? [c.spline_start, c.spline_end] : null;
  }, [selectedCorner, data?.geometry, viewRange]);

  const zoomToRange = useCallback((range: [number, number], keepCorner = false) => {
    setViewRange(range);
    if (!keepCorner) setSelectedCorner(null);
    setPlayheadSpline((range[0] + range[1]) / 2);
  }, []);

  const resetZoom = useCallback(() => {
    setPreviewRange(null);
    setViewRange(null);
    setSelectedCorner(null);
    setSelectedAnnotation(null);
    mapRef.current?.resetView();
  }, []);

  const commitMapRange = useCallback(
    (range: [number, number]) => {
      setPreviewRange(null);
      const [lo, hi] = normalizeSplineRange(range[0], range[1]);
      if (hi - lo < MIN_SELECT_SPAN) return;
      zoomToRange(padSplineRange([lo, hi]), false);
      const corner = data?.geometry?.corners.find(
        (c) => lo <= c.spline_end && hi >= c.spline_start,
      );
      if (corner) setSelectedCorner(corner.id);
    },
    [zoomToRange, data?.geometry],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPreviewRange(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const zoomInTelemetry = useCallback(() => {
    setViewRange((prev) => {
      const base = prev ?? cornerRange ?? [0, 1];
      return contractViewRange(base);
    });
  }, [cornerRange]);

  const zoomOutTelemetry = useCallback(() => {
    setViewRange((prev) => {
      const base = prev ?? cornerRange ?? [0, 1];
      const next = expandViewRange(base);
      if (next[0] <= 0.001 && next[1] >= 0.999) return null;
      return next;
    });
  }, [cornerRange]);

  const clearSelection = useCallback(() => {
    setSelectedCorner(null);
    setSelectedAnnotation(null);
    setPreviewRange(null);
    setViewRange(null);
  }, []);

  const effectiveChartRange = previewRange ? null : cornerRange;
  const chartHighlight = previewRange;

  const displayAnnotations = useMemo(
    () => [...(data?.annotations ?? []), ...(data?.coachNotes ?? [])],
    [data?.annotations, data?.coachNotes],
  );

  const focusCorner = useCallback(
    (cornerId: string) => {
      if (selectedCorner === cornerId) {
        clearSelection();
        mapRef.current?.resetView();
        return;
      }
      setSelectedCorner(cornerId);
      setSelectedAnnotation(null);
      const c = data?.geometry?.corners.find((x) => x.id === cornerId);
      if (c) {
        const pad = 0.008;
        zoomToRange(
          [Math.max(0, c.spline_start - pad), Math.min(1, c.spline_end + pad)],
          true,
        );
        const ann = displayAnnotations.find(
          (a) => a.corner === cornerId && (activeLap == null || !a.lap || a.lap === activeLap),
        );
        if (ann) setSelectedAnnotation(ann);
      }
    },
    [selectedCorner, clearSelection, data?.geometry, displayAnnotations, activeLap, zoomToRange],
  );

  const selectAnnotation = useCallback(
    (ann: Annotation) => {
      setSelectedAnnotation(ann);
      if (ann.lap != null) setSelectedLap(ann.lap);
      setPlayheadSpline(ann.spline);
      if (ann.spline_start != null && ann.spline_end != null) {
        if (ann.corner) setSelectedCorner(ann.corner);
        zoomToRange([ann.spline_start, ann.spline_end], !!ann.corner);
      } else if (ann.corner) {
        const c = data?.geometry?.corners.find((x) => x.id === ann.corner);
        if (c) {
          setSelectedCorner(ann.corner);
          const pad = 0.008;
          zoomToRange(
            [Math.max(0, c.spline_start - pad), Math.min(1, c.spline_end + pad)],
            true,
          );
        }
      }
    },
    [zoomToRange, data?.geometry],
  );

  const onTimeLossCorner = useCallback(
    (corner: CornerTimeLoss) => {
      setSelectedCorner(corner.corner);
      const fix = corner.fixes?.[0];
      if (fix) {
        setSelectedAnnotation({
          id: `loss_${corner.corner}`,
          spline: (corner.spline_start + corner.spline_end) / 2,
          spline_start: corner.spline_start,
          spline_end: corner.spline_end,
          corner: corner.corner,
          corner_display: corner.corner_display,
          category: fix.category as Annotation["category"],
          title: fix.title || corner.primary_title,
          what: fix.what,
          action: fix.action || corner.primary_action,
          subtype: fix.subtype,
          phase: fix.phase,
        });
      }
      const pad = 0.006;
      zoomToRange(
        [
          Math.max(0, corner.spline_start - pad),
          Math.min(1, corner.spline_end + pad),
        ],
        true,
      );
    },
    [zoomToRange],
  );

  const trap = cleanLapTrap(data?.stintSummary ?? null);

  const analysisStep = deriveAnalysisStep(
    viewMode,
    selectedCorner,
    !!selectedAnnotation,
  );

  const chartProps = {
    samples,
    compareSamples,
    delta,
    stitchedLoss,
    playheadSpline,
    annotations: displayAnnotations,
    activeLap,
    viewRange: effectiveChartRange,
    highlightRange: chartHighlight,
    potentialGapS,
    theoreticalBestMs:
      data?.timeLoss?.theoretical_best_ms ?? data?.stintSummary?.theoretical_best_ms,
    lapTimeMs: activeTimeLoss?.lap_time_ms,
    onSplineChange: setPlayheadSpline,
    onViewRangeChange: (range: [number, number]) => {
      setPreviewRange(null);
      zoomToRange(padSplineRange(normalizeSplineRange(range[0], range[1])), false);
    },
    onTimeLossCorner,
  };

  if (indexLoading && !data) {
    return (
      <div style={{ padding: 40, color: "#94a3b8", background: "#0f172a", minHeight: "100vh" }}>
        Loading sessions…
      </div>
    );
  }

  if (showPicker && sessionsIndex && sessionsIndex.count > 0) {
    return (
      <div style={{ minHeight: "100vh", background: "#0f172a" }}>
        <SessionPicker index={sessionsIndex} onSelect={openSession} />
      </div>
    );
  }

  if (!data && !loading && !indexLoading) {
    return (
      <div style={{ padding: 40, color: "#e2e8f0", background: "#0f172a", minHeight: "100vh" }}>
        <h1>VRE Replay Viewer</h1>
        <p style={{ color: "#94a3b8" }}>
          {sessionsIndex?.count
            ? "Select a session or run ./replay.sh from the repo root."
            : "No sessions found. Run ./replay.sh after driving with Virtual Race Engineer."}
        </p>
        {error && <p style={{ color: "#ef4444" }}>{error}</p>}
        {sessionsIndex && sessionsIndex.count > 0 && (
          <button type="button" onClick={() => setShowPicker(true)} style={{ marginTop: 16 }}>
            Choose session ({sessionsIndex.count})
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header
        style={{
          padding: "12px 20px",
          borderBottom: "1px solid #334155",
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <strong>
          {data?.manifest.track_display ?? "VRE Replay"}
          {data?.manifest.car_id && (
            <span style={{ fontWeight: 400, color: "#64748b", marginLeft: 8, fontSize: 12 }}>
              {data.manifest.car_id.replace(/_/g, " ")}
            </span>
          )}
        </strong>
        {sessionsIndex && sessionsIndex.count > 1 && (
          <select
            value={activeSession?.id ?? ""}
            onChange={(e) => {
              const entry = sessionsIndex.sessions.find((s) => s.id === e.target.value);
              if (entry) openSession(entry);
            }}
            style={{ maxWidth: 280 }}
          >
            {sessionsIndex.sessions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.track} — {s.id.slice(0, 10)}… ({((s.best_lap_ms ?? 0) / 1000).toFixed(3)}s)
              </option>
            ))}
          </select>
        )}
        {data?.manifest.session_id && sessionsIndex && sessionsIndex.count <= 1 && (
          <span style={{ fontSize: 12, color: "#64748b" }}>{data.manifest.session_id}</span>
        )}
        {data?.manifest.archive_note && (
          <span style={{ fontSize: 12, color: "#94a3b8" }}>{data.manifest.archive_note}</span>
        )}
        {data?.stintSummary?.best_lap_ms && (
          <span style={{ fontSize: 13 }}>
            Best {(data.stintSummary.best_lap_ms / 1000).toFixed(3)}s
            {data.stintSummary.theoretical_best_ms && (
              <> · Potential {(data.stintSummary.theoretical_best_ms / 1000).toFixed(3)}s</>
            )}
          </span>
        )}
        {sessionsIndex && sessionsIndex.count > 1 && (
          <button
            type="button"
            onClick={() => setShowPicker(true)}
            style={{ marginLeft: "auto", fontSize: 12, padding: "6px 10px" }}
          >
            All sessions
          </button>
        )}
        {(viewRange || previewRange) && (
          <ZoomToolbar
            hasZoom={!!viewRange}
            previewActive={!!previewRange}
            onZoomIn={zoomInTelemetry}
            onZoomOut={zoomOutTelemetry}
            onReset={resetZoom}
          />
        )}
        <div className="lap-selectors">
          <label className="lap-select-label">
            Viewing
            <select
              value={activeLap ?? ""}
              onChange={(e) => setSelectedLap(Number(e.target.value))}
            >
              {lapNums.map((n) => (
                <option key={n} value={n}>
                  {lapTimeLabel(data!.manifest.laps, n)}
                  {n === bestLapNum ? " ★ best" : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="lap-select-label">
            Compare trace
            <select
              value={compareLap ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setCompareLap(v === "" ? null : Number(v));
              }}
            >
              <option value="">None — single lap only</option>
              {lapNums
                .filter((n) => n !== activeLap)
                .map((n) => (
                  <option key={n} value={n}>
                    + {lapTimeLabel(data!.manifest.laps, n)}
                    {n === bestLapNum ? " ★ best" : ""}
                  </option>
                ))}
            </select>
          </label>
        </div>
        {compareLap != null && activeLap != null && (
          <span className="compare-legend">
            Green = {lapTimeLabel(data!.manifest.laps, activeLap)} · dashed blue ={" "}
            {lapTimeLabel(data!.manifest.laps, compareLap)}
          </span>
        )}
        <div className="view-mode-toggle" role="group" aria-label="View mode">
          <button
            type="button"
            className={viewMode === "guided" ? "active" : ""}
            onClick={() => setViewModePersist("guided")}
          >
            Guided
          </button>
          <button
            type="button"
            className={viewMode === "explore" ? "active" : ""}
            onClick={() => setViewModePersist("explore")}
          >
            Explore
          </button>
        </div>
        <label className="expertise-toggle" title="Experts default to Explore mode">
          <input
            type="checkbox"
            checked={expertise}
            onChange={(e) => {
              const on = e.target.checked;
              setExpertise(on);
              localStorage.setItem("vre_expertise", on ? "expert" : "novice");
            }}
          />
          Expert
        </label>
      </header>

      {data && (
        <KpiStrip
          potentialGapS={potentialGapS}
          bestLapMs={data.stintSummary?.best_lap_ms ?? data.manifest.best_lap_ms ?? undefined}
          theoreticalBestMs={
            data.timeLoss?.theoretical_best_ms ?? data.stintSummary?.theoretical_best_ms ?? undefined
          }
          lapTimeMs={activeTimeLoss?.lap_time_ms}
          lapLabel={activeLap != null ? `Lap ${activeLap}` : undefined}
        />
      )}

      {data && (
        <div className="guided-toolbar">
          <SessionPlanCard
            sessionPlan={data.sessionPlan}
            timeLossCorners={activeTimeLoss?.corners ?? []}
            onSelectCorner={focusCorner}
          />
          <AnalysisStepHeader activeStep={analysisStep} viewMode={viewMode} />
        </div>
      )}

      {data && samples.length > 0 && (
        <CursorReadout
          samples={samples}
          compareSamples={compareSamples}
          playheadSpline={playheadSpline}
        />
      )}

      {sessionsIndex && activeSession && data && (
        <StintComparison
          sessions={sessionsIndex.sessions}
          currentId={activeSession.id}
          focusCorner={selectedCorner}
        />
      )}

      {trap && (
        <div
          style={{
            background: "#164e63",
            padding: "8px 20px",
            fontSize: 13,
            color: "#a5f3fc",
          }}
        >
          {trap.potential_gap_s?.toFixed(2)}s in your sectors — see the time-loss breakdown
          above the charts for where and how to recover it.
        </div>
      )}

      {loading && <div style={{ padding: 20 }}>Loading stint…</div>}
      {error && <div style={{ padding: 20, color: "#ef4444" }}>{error}</div>}

      {data?.geometry && samples.length > 0 && (
        <div className="app-main">
          <aside className="app-sidebar-left">
            {viewMode === "explore" && (
              <LayerPanel
                layers={layers}
                availability={channelAvailability ?? detectChannelAvailability(samples)}
                onChange={onLayersChange}
              />
            )}
            <TrackMap
              ref={mapRef}
              geometry={data.geometry}
              samples={samples}
              compareSamples={compareSamples.length ? compareSamples : undefined}
              playheadSpline={playheadSpline}
              layers={layers}
              annotations={displayAnnotations}
              selectedCorner={selectedCorner}
              focusSplineRange={cornerRange}
              previewRange={previewRange}
              onPreviewRangeChange={setPreviewRange}
              onCommitRange={commitMapRange}
              onSplineHover={throttledPlayhead}
              onSplineClick={setPlayheadSpline}
              onCornerSelect={focusCorner}
              onFocusSplineRange={(range) => zoomToRange(range)}
              onAnnotationClick={selectAnnotation}
            />
            {(data.coachNotes?.length ?? 0) > 0 && (
              <CoachNotesPanel
                notes={data.coachNotes}
                selectedId={selectedAnnotation?.id}
                onSelect={selectAnnotation}
              />
            )}
            {viewMode === "guided" ? (
              <button
                type="button"
                className="corner-list-toggle"
                onClick={() => setCornerListOpen((o) => !o)}
              >
                {cornerListOpen ? "Hide corner list" : "Show corner list"}
              </button>
            ) : null}
            {(viewMode === "explore" || cornerListOpen) && (
              <div className="corner-list">
                {data.geometry.corners.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => focusCorner(c.id)}
                    className={selectedCorner === c.id ? "selected" : ""}
                  >
                    {c.display_name}
                  </button>
                ))}
              </div>
            )}
          </aside>

          <main className="app-charts">
            {viewMode === "guided" && !selectedCorner && !viewRange && !previewRange ? (
              <div className="guided-overview-banner">
                {!formativeDone && activeTimeLoss?.corners?.length ? (
                  <FormativeCheck
                    corners={activeTimeLoss.corners}
                    onReveal={() => setFormativeDone(true)}
                    onGuess={focusCorner}
                  />
                ) : (
                  <p className="guided-overview-hint-line">
                    Full-lap telemetry below — drag on the map (or Shift+drag) to highlight a
                    section, release to zoom. Drag charts to zoom too. Reset anytime.
                  </p>
                )}
              </div>
            ) : null}
            {viewMode === "guided" ? (
              <GuidedChartStack
                {...chartProps}
                timeLossCorners={activeTimeLoss?.corners ?? []}
                availability={channelAvailability ?? detectChannelAvailability(samples)}
              />
            ) : (
              <TelemetryCharts
                {...chartProps}
                layers={layers}
                availability={channelAvailability ?? detectChannelAvailability(samples)}
                peakAy={data.ggEnvelope?.peak_ay}
                timeLossCorners={activeTimeLoss?.corners ?? []}
              />
            )}
          </main>

          <aside className="app-sidebar-right">
            <CoachPanel
              sessionId={activeSession?.id ?? data?.manifest.session_id ?? null}
              corner={selectedCorner}
              cornerDisplay={
                selectedCorner
                  ? data.geometry.corners.find((c) => c.id === selectedCorner)?.display_name
                  : undefined
              }
              lap={activeLap}
              playheadSpline={playheadSpline}
            />
            <Inspector
              annotation={selectedAnnotation}
              narrative={data.narrative}
              narrativeSections={data.narrativeSections}
              cornerId={selectedCorner}
              cornerDisplay={
                selectedCorner
                  ? data.geometry.corners.find((c) => c.id === selectedCorner)?.display_name
                  : undefined
              }
              timeLossCorner={
                selectedCorner
                  ? activeTimeLoss?.corners.find((c) => c.corner === selectedCorner)
                  : undefined
              }
              sessionPlanDrill={
                data.sessionPlan?.items.find((i) => i.corner === selectedCorner)?.drill
              }
              viewMode={viewMode}
              onClearSelection={clearSelection}
            />
          </aside>
        </div>
      )}

      {viewMode === "explore" && exploreDrawerOpen && data?.geometry && (
        <div className="explore-drawer">
          <div className="explore-drawer-header">
            <strong>Explore layers</strong>
            <button type="button" onClick={() => setExploreDrawerOpen(false)}>
              Close
            </button>
          </div>
          <LayerPanel
            layers={layers}
            availability={channelAvailability ?? detectChannelAvailability(samples)}
            onChange={onLayersChange}
            compact
          />
        </div>
      )}

      {layers.setupPanel && (
        <SetupTimeline
          episodes={data?.setupEpisodes?.length ? data.setupEpisodes : (data?.setupTimeline ?? [])}
          visible={layers.setup}
          activeLap={activeLap}
          onSelectEpisode={(ep) => {
            const ann = data?.annotations.find(
              (a) => a.id === `setup_${ep.episode_id}` || a.id === `setup_${ep.tweak_id}`,
            );
            if (ann) {
              setSelectedAnnotation(ann);
              setPlayheadSpline(ep.detected_spline ?? ann.spline);
              if (ep.detected_spline_start != null && ep.detected_spline_end != null) {
                if (ep.detected_corner) setSelectedCorner(ep.detected_corner);
                zoomToRange([ep.detected_spline_start, ep.detected_spline_end], !!ep.detected_corner);
              } else if (ep.detected_corner) {
                focusCorner(ep.detected_corner);
              }
            }
          }}
        />
      )}
    </div>
  );
}
