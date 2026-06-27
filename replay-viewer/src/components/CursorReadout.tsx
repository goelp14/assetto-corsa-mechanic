import type { LapSample } from "../types";

interface Props {
  samples: LapSample[];
  compareSamples?: LapSample[];
  playheadSpline: number;
}

function sampleAtSpline(samples: LapSample[], spline: number): LapSample | null {
  if (!samples.length) return null;
  let best = samples[0];
  let bestD = Math.abs(best.spline - spline);
  for (const s of samples) {
    const d = Math.abs(s.spline - spline);
    if (d < bestD) {
      bestD = d;
      best = s;
    }
  }
  return best;
}

export function CursorReadout({ samples, compareSamples, playheadSpline }: Props) {
  const s = sampleAtSpline(samples, playheadSpline);
  if (!s) return null;

  const ref = compareSamples?.length ? sampleAtSpline(compareSamples, playheadSpline) : null;
  const deltaKmh = ref ? s.speed_kmh - ref.speed_kmh : null;

  return (
    <div className="cursor-readout">
      <span>
        <strong>{Math.round(s.speed_kmh)}</strong> km/h
        {deltaKmh != null && (
          <span className={deltaKmh >= 0 ? "delta-pos" : "delta-neg"}>
            {" "}
            ({deltaKmh >= 0 ? "+" : ""}
            {deltaKmh.toFixed(0)} vs ref)
          </span>
        )}
      </span>
      <span>
        Brake <strong>{Math.round(s.brake * 100)}</strong>%
      </span>
      <span>
        Throttle <strong>{Math.round(s.throttle * 100)}</strong>%
      </span>
      {s.corner && <span className="cursor-readout-corner">{s.corner}</span>}
    </div>
  );
}
