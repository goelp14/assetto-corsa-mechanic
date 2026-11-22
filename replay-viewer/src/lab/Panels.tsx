// Side panels: Coaching, Corners, Setup, Limits. Visual first; every row links back to the replay.
import { useMemo } from "react";
import { COLORS, fmtDelta, fmtLap } from "./data";
import { carLengthM, gapText, relPos } from "./landmarks";
import type { CornerEvent, Fix, LabBundle, Slot } from "./types";

export interface StudioApi {
  bundle: LabBundle;
  A: Slot | null;
  B: Slot | null;
  focusCorner: (key: string, play?: boolean) => void;
  seek: (s: number) => void;
  setSlot: (which: "A" | "B", s: Slot) => void;
  playRange: (s0: number, s1: number) => void;
}

function eventsFor(api: StudioApi, slot: Slot | null, key: string): CornerEvent | null {
  if (!slot) return null;
  const c = api.bundle.analysis?.drivers[slot.driver]?.corners[key];
  return c?.laps.find((l) => l.lap_index === slot.lap) ?? null;
}

// ---------------- Coaching ----------------

export function CoachingPanel({ api }: { api: StudioApi }) {
  const c = api.bundle.coaching;
  if (!c) return <Empty text="No coaching in this bundle." />;
  const habits = c.habits?.habits ?? [];
  const maxImpact = Math.max(0.01, ...habits.map((h) => Math.abs(h.pace_impact_s)));
  return (
    <div className="lab-panel">
      <h3>Fix these first</h3>
      <p className="lab-muted">At most two changes per session — the biggest, most repeatable time.</p>
      {c.fixes.map((f, i) => (
        <FixCard key={f.id} f={f} n={i + 1} api={api} primary />
      ))}
      {c.later?.length > 0 && (
        <details className="lab-details">
          <summary>Next up ({c.later.length})</summary>
          {c.later.map((f, i) => (
            <FixCard key={f.id} f={f} n={c.fixes.length + i + 1} api={api} />
          ))}
        </details>
      )}
      <h3>Habits</h3>
      <div className="lab-habits">
        {habits
          .slice()
          .sort((a, b) => Math.abs(b.pace_impact_s) - Math.abs(a.pace_impact_s))
          .map((h) => (
            <div key={h.id} className={`lab-habit lab-habit--${h.polarity}`} title={h.detail}>
              <div className="lab-habit-row">
                <span className="lab-habit-tag">{h.polarity === "strength" ? "strength" : "habit"}</span>
                <b>{h.title}</b>
                <span className="lab-habit-impact">{h.pace_impact_s.toFixed(2)} s</span>
              </div>
              <div className="lab-bar">
                <i
                  style={{
                    width: `${(Math.abs(h.pace_impact_s) / maxImpact) * 100}%`,
                    background: h.polarity === "strength" ? COLORS.gain : COLORS.lose,
                  }}
                />
              </div>
              <div className="lab-chips">
                {h.instances.slice(0, 6).map((inst) => (
                  <button key={inst.key} className="lab-chip" onClick={() => api.focusCorner(inst.key)}>
                    {inst.corner}
                  </button>
                ))}
              </div>
            </div>
          ))}
      </div>
      {c.persistent_habits?.length > 0 && (
        <>
          <h3>Seen on other tracks/cars</h3>
          <ul className="lab-list">
            {c.persistent_habits.map((p) => (
              <li key={p.id}>
                <b>{p.id.replace(/_/g, " ")}</b> — {p.where.length} combos
              </li>
            ))}
          </ul>
        </>
      )}
      {c.diagnosis?.corners?.length > 0 && (
        <>
          <h3>Why time is lost (per corner)</h3>
          <div className="lab-chips">
            {c.diagnosis.corners.map((r) => (
              <span key={r.corner} className={`lab-cause lab-cause--${r.cause}`} title={r.habits.join(", ")}>
                {r.corner} · {r.loss_s.toFixed(2)} s · {r.cause}
              </span>
            ))}
          </div>
          <p className="lab-muted">{c.diagnosis.order}</p>
        </>
      )}
    </div>
  );
}

function FixCard({ f, n, api, primary }: { f: Fix; n: number; api: StudioApi; primary?: boolean }) {
  const where = (f as Fix & { where?: string[] }).where ?? [];
  return (
    <div className={`lab-fix${primary ? " lab-fix--primary" : ""}`}>
      <div className="lab-fix-head">
        <span className="lab-fix-n">{n}</span>
        <div>
          <div className="lab-fix-corner">{f.corner}</div>
          <div className="lab-fix-gain">up to {f.pace_impact_s.toFixed(2)} s / lap · {f.confidence}</div>
        </div>
        <button className="lab-btn lab-btn--accent" onClick={() => api.focusCorner(f.corner_key, true)}>
          ▶ Show me
        </button>
      </div>
      <div className="lab-fix-model">
        <div>
          <span className="lab-x">✕</span> {f.belief}
        </div>
        <div>
          <span className="lab-check">✓</span> {f.correct_model}
        </div>
      </div>
      {where.length > 0 && (
        <ul className="lab-where">
          {where.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      <div className="lab-fix-drill">
        <b>Drill</b> {f.drill}
      </div>
      <div className="lab-fix-metric">
        <b>Success</b> {f.success_metric}
      </div>
      {f.cues?.length > 0 && <div className="lab-muted lab-small">Cues: {f.cues.join(" · ")}</div>}
    </div>
  );
}

// ---------------- Corners ----------------

export function CornersPanel({ api }: { api: StudioApi }) {
  const a = api.bundle.analysis;
  const corners = api.bundle.track?.corners ?? a?.pack.corners ?? [];
  const cl = carLengthM(a?.car_state?.[api.A?.driver ?? ""]?.wheelbase_m);
  const rows = useMemo(() => {
    if (!a) return [];
    return a.windows.map((w) => {
      const key = `${w.corner}#${w.index}`;
      const ea = eventsFor(api, api.A, key);
      const eb = eventsFor(api, api.B, key);
      const loss = ea?.section_time_s != null && eb?.section_time_s != null ? ea.section_time_s - eb.section_time_s : null;
      return { w, key, ea, eb, loss };
    });
  }, [a, api]);
  if (!a) return <Empty text="No analysis in this bundle." />;
  const maxLoss = Math.max(0.05, ...rows.map((r) => Math.abs(r.loss ?? 0)));
  const lbB = api.B?.driver ?? "ref";
  return (
    <div className="lab-panel">
      <h3>Time per corner (selected laps)</h3>
      <p className="lab-muted">
        Section time A − B, brake-to-brake windows. Red = A slower. Click a corner to frame it on the map and traces.
      </p>
      <div className="lab-lossbars">
        {rows.map((r) => (
          <button key={r.key} className="lab-lossbar" onClick={() => api.focusCorner(r.key)}>
            <span className="lab-lossbar-name">{r.w.corner}</span>
            <span className="lab-lossbar-track">
              <span className="lab-lossbar-mid" />
              {r.loss != null && (
                <i
                  style={{
                    left: r.loss > 0 ? "50%" : `${50 - (Math.abs(r.loss) / maxLoss) * 50}%`,
                    width: `${(Math.abs(r.loss) / maxLoss) * 50}%`,
                    background: r.loss > 0 ? COLORS.lose : COLORS.gain,
                  }}
                />
              )}
            </span>
            <span className="lab-lossbar-val" style={{ color: (r.loss ?? 0) > 0 ? COLORS.lose : COLORS.gain }}>
              {r.loss == null ? "—" : fmtDelta(r.loss, 2)}
            </span>
          </button>
        ))}
      </div>
      <h3>Corner report</h3>
      <p className="lab-muted">
        Positions are relative to the corner apex; gaps say where {lbB} does the same thing, in car lengths (≈{cl.toFixed(1)} m).
      </p>
      {rows.map(({ w, key, ea, eb, loss }) => (
        <details key={key} className="lab-corner">
          <summary>
            <b>{w.corner}</b>
            <span className="lab-muted">
              {w.speed_class} · {w.direction}
            </span>
            <span style={{ color: (loss ?? 0) > 0 ? COLORS.lose : COLORS.gain, marginLeft: "auto" }}>{loss == null ? "" : `${fmtDelta(loss, 2)} s`}</span>
          </summary>
          <table className="lab-table">
            <thead>
              <tr>
                <th />
                <th style={{ color: COLORS.A }}>{api.A?.driver}</th>
                <th>{api.B ? `${lbB} vs A` : ""}</th>
              </tr>
            </thead>
            <tbody>
              <Row label="Brake on" a={ea?.brake_on_m} b={eb?.brake_on_m} corners={corners} cl={cl} braking who={lbB} />
              <Row label="Full brake" a={ea?.brake_full_m} b={eb?.brake_full_m} corners={corners} cl={cl} braking who={lbB} />
              <Row label="Turn in" a={ea?.turn_in_m} b={eb?.turn_in_m} corners={corners} cl={cl} who={lbB} />
              <Row label="Slowest" a={ea?.vmin_m} b={eb?.vmin_m} corners={corners} cl={cl} who={lbB} />
              <Row label="Full throttle" a={ea?.full_throttle_m} b={eb?.full_throttle_m} corners={corners} cl={cl} who={lbB} />
              <NumRow label="Entry speed" a={ea?.brake_on_kmh} b={eb?.brake_on_kmh} unit="km/h" />
              <NumRow label="Turn-in speed" a={ea?.turn_in_kmh} b={eb?.turn_in_kmh} unit="km/h" />
              <NumRow label="Min speed" a={ea?.vmin_kmh} b={eb?.vmin_kmh} unit="km/h" higherBetter />
              <NumRow label="Brake build" a={ea?.brake_ramp_m} b={eb?.brake_ramp_m} unit="m" lowerBetter />
              <NumRow label="Coasting" a={ea?.coast_s} b={eb?.coast_s} unit="s" lowerBetter nd={2} />
              <NumRow label="Peak decel" a={ea?.decel_peak_g} b={eb?.decel_peak_g} unit="g" nd={2} higherBetter />
              <NumRow label="Section" a={ea?.section_time_s} b={eb?.section_time_s} unit="s" nd={3} lowerBetter />
            </tbody>
          </table>
          {ea?.terrain && ea.terrain.length > 0 && (
            <div className="lab-small lab-muted">
              Terrain:{" "}
              {ea.terrain.map((t) => (
                <span key={t.at_m}>
                  {t.kind} {relPos(t.at_m, corners)} ({t.expected_dg > 0 ? "+" : ""}
                  {(t.expected_dg * 100).toFixed(0)}% load) — you: brake {(t.brake * 100).toFixed(0)}%, throttle {(t.throttle * 100).toFixed(0)}%.{" "}
                </span>
              ))}
            </div>
          )}
          <div className="lab-row-btns">
            <button className="lab-btn" onClick={() => api.focusCorner(key)}>
              Frame
            </button>
            <button className="lab-btn lab-btn--accent" onClick={() => api.focusCorner(key, true)}>
              ▶ Play side by side
            </button>
          </div>
        </details>
      ))}
    </div>
  );
}

function Row({ label, a, b, corners, cl, braking, who }: { label: string; a?: number | null; b?: number | null; corners: Parameters<typeof relPos>[1]; cl: number; braking?: boolean; who: string }) {
  return (
    <tr>
      <td>{label}</td>
      <td>{a == null ? "—" : relPos(a, corners, braking)}</td>
      <td>{gapText(a, b, cl, who)}</td>
    </tr>
  );
}

function NumRow({ label, a, b, unit, nd = 0, higherBetter, lowerBetter }: { label: string; a?: number | null; b?: number | null; unit: string; nd?: number; higherBetter?: boolean; lowerBetter?: boolean }) {
  const d = a != null && b != null ? a - b : null;
  const good = d == null ? null : higherBetter ? d > 0 : lowerBetter ? d < 0 : null;
  return (
    <tr>
      <td>{label}</td>
      <td>{a == null ? "—" : `${a.toFixed(nd)} ${unit}`}</td>
      <td style={{ color: good == null || Math.abs(d ?? 0) < 1e-9 ? undefined : good ? COLORS.gain : COLORS.lose }}>
        {b == null ? "—" : `${b.toFixed(nd)} ${unit}`}
      </td>
    </tr>
  );
}

// ---------------- Setup ----------------

const NICE: Record<string, string> = {
  aero_load_coeff: "Downforce (load per v²)",
  aero_front_share: "Aero balance (front share)",
  brake_slip_front_share: "Braking slip, front share",
  diff_inside_spin: "Inside-wheel spin on exit (diff)",
  tc_estimate_rate: "TC activity (estimated)",
  abs_estimate_rate: "ABS activity (estimated)",
  roll_stiffness_front_share: "Roll stiffness, front share",
  pitch_per_g_braking: "Pitch per g under braking",
  rake_change_at_200kmh: "Rake change at 200 km/h",
};

export function SetupPanel({ api }: { api: StudioApi }) {
  const s = api.bundle.setup;
  const a = api.bundle.analysis;
  if (!s) return <Empty text="No setup data in this bundle." />;
  const me = s.label;
  const ref = s.reference?.label;
  const cs = a?.car_state?.[me] ?? {};
  const csR = ref ? a?.car_state?.[ref] ?? {} : {};
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  const gears = s.fingerprint.exact.kmh_per_1000rpm_by_gear ?? {};
  const gearsR = s.reference?.fingerprint.exact.kmh_per_1000rpm_by_gear ?? {};
  const gmax = Math.max(1, ...Object.values(gears), ...Object.values(gearsR));
  return (
    <div className="lab-panel">
      <p className="lab-muted">
        The car setup is not stored in ACC replays. What follows is measured from how the car behaved (exact: gearing, tyre radii,
        mass; estimated: balance and stiffness signatures), plus setup files from your library that match this car and track.
      </p>
      <h3>Car balance</h3>
      <Split label="Static weight, front" a={num(cs.static_front_share)} b={num(csR.static_front_share)} me={me} refLabel={ref} />
      <Split label="Aero balance, front" a={num(cs.aero_front_share)} b={num(csR.aero_front_share)} me={me} refLabel={ref} />
      <Split label="Load on fronts under braking" a={num(cs.front_share_under_braking)} b={num(csR.front_share_under_braking)} me={me} refLabel={ref} />
      <Split label="Roll load transfer, front" a={num(cs.front_lat_transfer_share)} b={num(csR.front_lat_transfer_share)} me={me} refLabel={ref} />
      <Gauge
        label="Understeer gradient"
        unit="°/g"
        a={num(cs.understeer_gradient_deg_per_g)}
        b={num(csR.understeer_gradient_deg_per_g)}
        min={-2}
        max={4}
        left="oversteer"
        right="understeer"
        note={String(cs.understeer_note ?? "")}
      />
      <div className="lab-kv">
        <span>Mass (measured)</span>
        <b>{num(cs.mass_kg)?.toFixed(0) ?? "—"} kg</b>
        <span>Downforce at 200 km/h</span>
        <b>{num(cs.downforce_at_200kmh_n) ? `${((cs.downforce_at_200kmh_n as number) / 9.81).toFixed(0)} kg` : "—"}</b>
        <span>Wheelbase</span>
        <b>{num(cs.wheelbase_m)?.toFixed(2) ?? "—"} m</b>
      </div>

      {s.comparison && s.comparison.length > 0 && (
        <>
          <h3>Behaviour fingerprint vs {ref}</h3>
          <p className="lab-muted">Dots = each driver, band = lap-to-lap noise. Inside the band we can't tell the setups apart.</p>
          {s.comparison.map((c) => {
            const va = c[me] as number | undefined;
            const vb = ref ? (c[ref] as number | undefined) : undefined;
            if (va == null || vb == null) return null;
            const lo = Math.min(va, vb) - Math.max(c.noise, Math.abs(va - vb) * 0.3);
            const hi = Math.max(va, vb) + Math.max(c.noise, Math.abs(va - vb) * 0.3);
            const X = (v: number) => `${((v - lo) / (hi - lo || 1)) * 100}%`;
            const tell = c.verdict !== "can't tell";
            return (
              <div key={c.item} className="lab-dumbbell" title={(s.fingerprint.estimated[c.item]?.note as string) || ""}>
                <div className="lab-dumbbell-head">
                  <span>{NICE[c.item] ?? c.item}</span>
                  <span className={tell ? "lab-verdict" : "lab-muted"}>{c.verdict}</span>
                </div>
                <div className="lab-dumbbell-track">
                  <span className="lab-noise" style={{ left: X(vb - c.noise), width: `calc(${X(vb + c.noise)} - ${X(vb - c.noise)})` }} />
                  <span className="lab-dumbbell-line" style={{ left: X(Math.min(va, vb)), width: `calc(${X(Math.max(va, vb))} - ${X(Math.min(va, vb))})` }} />
                  <span className="lab-dot" style={{ left: X(vb), background: COLORS.B }} />
                  <span className="lab-dot" style={{ left: X(va), background: COLORS.A }} />
                </div>
                {tell && c.likely_levers && <div className="lab-small">Likely lever: {c.likely_levers}</div>}
              </div>
            );
          })}
        </>
      )}

      {Object.keys(gears).length > 0 && (
        <>
          <h3>Gearing (exact)</h3>
          <div className="lab-gears">
            {Object.keys({ ...gears, ...gearsR })
              .sort()
              .map((g) => (
                <div key={g} className="lab-gear-row">
                  <span>{g}</span>
                  <div className="lab-gear-bars">
                    <i style={{ width: `${((gears[g] ?? 0) / gmax) * 100}%`, background: COLORS.A }} />
                    {ref && <i style={{ width: `${((gearsR[g] ?? 0) / gmax) * 100}%`, background: COLORS.B }} />}
                  </div>
                  <span className="lab-mono">
                    {gears[g]?.toFixed(1) ?? "—"}
                    {ref ? ` / ${gearsR[g]?.toFixed(1) ?? "—"}` : ""}
                  </span>
                </div>
              ))}
          </div>
          <p className="lab-muted lab-small">km/h per 1000 rpm. Different numbers = different gear ratios or final drive.</p>
        </>
      )}

      {(api.bundle.coaching?.setup_checks?.length ?? 0) > 0 && (
        <>
          <h3>Checks</h3>
          {api.bundle.coaching!.setup_checks.map((c, i) => (
            <div key={i} className="lab-check-card">
              <b>{String(c.verdict)}</b>
              {c.direction ? <div>Try: {String(c.direction)} ({String(c.lever)})</div> : null}
              <div className="lab-small lab-muted">{String(c.test)}</div>
            </div>
          ))}
        </>
      )}
      {(api.bundle.coaching?.diagnosis?.setup_recommendations?.length ?? 0) > 0 && (
        <>
          <h3>Setup changes worth testing</h3>
          {api.bundle.coaching!.diagnosis.setup_recommendations.map((r) => (
            <div key={r.lever} className="lab-check-card">
              <b>
                {r.lever.split(".").pop()}: {r.direction}
              </b>
              <div>{r.why}</div>
              <div className="lab-small lab-muted">
                Test: {r.test} · Expect: {r.expect}
              </div>
            </div>
          ))}
        </>
      )}
      {s.library_candidates && s.library_candidates.length > 0 && (
        <>
          <h3>Matching setups in your library</h3>
          <ul className="lab-list">
            {s.library_candidates.map((c) => (
              <li key={c.name}>
                <b>{c.name}</b>
                <div className="lab-small lab-muted">
                  {Object.entries(c.physical)
                    .slice(0, 4)
                    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.join(" / ") : String(v)}`)
                    .join(" · ")}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Split({ label, a, b, me, refLabel }: { label: string; a: number | null; b: number | null; me: string; refLabel?: string }) {
  if (a == null) return null;
  return (
    <div className="lab-split">
      <div className="lab-split-head">
        <span>{label}</span>
        <span className="lab-mono">
          <span style={{ color: COLORS.A }}>{(a * 100).toFixed(1)}%</span>
          {b != null && (
            <>
              {" "}
              / <span style={{ color: COLORS.B }}>{(b * 100).toFixed(1)}%</span>
            </>
          )}
        </span>
      </div>
      <div className="lab-split-track" aria-label={`${me} ${(a * 100).toFixed(1)}% front`}>
        <span className="lab-split-mid" />
        <i style={{ left: `${a * 100}%`, background: COLORS.A }} />
        {b != null && <i style={{ left: `${b * 100}%`, background: COLORS.B }} title={refLabel} />}
        <em className="lab-split-l">front</em>
        <em className="lab-split-r">rear</em>
      </div>
    </div>
  );
}

function Gauge({ label, unit, a, b, min, max, left, right, note }: { label: string; unit: string; a: number | null; b: number | null; min: number; max: number; left: string; right: string; note?: string }) {
  if (a == null) return null;
  const X = (v: number) => `${((Math.max(min, Math.min(max, v)) - min) / (max - min)) * 100}%`;
  return (
    <div className="lab-split" title={note}>
      <div className="lab-split-head">
        <span>{label}</span>
        <span className="lab-mono">
          <span style={{ color: COLORS.A }}>
            {a.toFixed(2)} {unit}
          </span>
          {b != null && (
            <>
              {" "}
              / <span style={{ color: COLORS.B }}>{b.toFixed(2)}</span>
            </>
          )}
        </span>
      </div>
      <div className="lab-split-track lab-gauge">
        <span className="lab-split-mid" style={{ left: X(0) }} />
        <i style={{ left: X(a), background: COLORS.A }} />
        {b != null && <i style={{ left: X(b), background: COLORS.B }} />}
        <em className="lab-split-l">{left}</em>
        <em className="lab-split-r">{right}</em>
      </div>
    </div>
  );
}

// ---------------- Limits ----------------

export function LimitsPanel({ api }: { api: StudioApi }) {
  const L = api.bundle.limits;
  const corners = api.bundle.track?.corners ?? [];
  if (!L || L.error) return <Empty text={L?.error ? `Track limits unavailable: ${L.error}` : "No track-limit data."} />;
  return (
    <div className="lab-panel">
      <p className="lab-muted">
        ACC judges the first cut of a lap, with a delay. The game's verdict per lap is exact; which excursion caused it is attributed from
        the replay (zone model learned per track). Click a cut to jump there.
      </p>
      {L.drivers.map((d) => (
        <div key={d.label}>
          <h3>{d.label}</h3>
          <div className="lab-laps">
            {d.laps.map((l) => {
              const judged = l.excursions.filter((e) => e.status === "judged").length;
              const over = l.excursions.filter((e) => e.all4).length;
              return (
                <div key={l.lap_index} className={`lab-lap ${l.valid === false ? "lab-lap--bad" : ""}`}>
                  <button className="lab-lap-main" onClick={() => api.setSlot(d.label === api.B?.driver ? "B" : "A", { driver: d.label, lap: l.lap_index })}>
                    <b>L{l.lap_index}</b> {fmtLap(l.lap_ms)} {l.valid === false ? "✕ invalid" : "✓"}
                  </button>
                  <span className="lab-small lab-muted">
                    {over} over the line · {judged} judged
                  </span>
                  {l.cut?.cut_m != null && (
                    <button
                      className="lab-chip lab-chip--warn"
                      onClick={() => {
                        api.setSlot(d.label === api.B?.driver ? "B" : "A", { driver: d.label, lap: l.lap_index });
                        api.seek(l.cut!.cut_m!);
                      }}
                      title={`${l.cut.method}, confidence ${l.cut.confidence}; judged ~${l.cut.judged_after_s?.toFixed(1) ?? "?"} s later`}
                    >
                      cut {relPos(l.cut.cut_m, corners)} ({l.cut.side})
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
      {L.envelope && <Envelope env={L.envelope} />}
      {L.zones.length > 0 && (
        <>
          <h3>Learned cut zones</h3>
          <ul className="lab-list">
            {L.zones.map((z) => (
              <li key={`${z.cut_m}-${z.drop_m}`}>
                <button className="lab-chip" onClick={() => api.seek(z.cut_m)}>
                  {relPos(z.cut_m, corners)}
                </button>{" "}
                verdict ~{z.lag_s_median.toFixed(1)} s later · {z.laps} laps
              </li>
            ))}
          </ul>
        </>
      )}
      <ul className="lab-list lab-small lab-muted">
        {L.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </div>
  );
}

function Envelope({ env }: { env: { bin_m: number; left: number[]; right: number[]; note: string } }) {
  const W = 360,
    H = 90;
  const n = env.left.length;
  const m = 4;
  const Y = (v: number) => H / 2 - (Math.max(-m, Math.min(m, v)) / m) * (H / 2 - 4);
  const path = (arr: number[]) => arr.map((v, i) => `${i ? "L" : "M"}${((i / (n - 1)) * W).toFixed(1)},${Y(v ?? 0).toFixed(1)}`).join("");
  return (
    <>
      <h3>Track used beyond the edge</h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="lab-env" role="img" aria-label="Legal track use envelope along the lap">
        <line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="#475569" />
        <path d={path(env.left.map((v) => -Math.max(0, -v)))} stroke={COLORS.A} fill="none" />
        <path d={path(env.right.map((v) => Math.max(0, v)))} stroke={COLORS.B} fill="none" />
      </svg>
      <p className="lab-small lab-muted">{env.note}</p>
    </>
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="lab-panel lab-muted">{text}</div>;
}
