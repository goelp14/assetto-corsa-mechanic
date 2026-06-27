export function expandViewRange(range: [number, number], factor = 0.2): [number, number] {
  const [a, b] = range;
  const span = b - a;
  const pad = span * factor;
  return [Math.max(0, a - pad), Math.min(1, b + pad)];
}

export function contractViewRange(range: [number, number], factor = 0.15): [number, number] {
  const [a, b] = range;
  const span = b - a;
  const cut = (span * factor) / 2;
  if (span - 2 * cut < 0.008) return range;
  return [a + cut, b - cut];
}

/** Normalize two spline endpoints into [lo, hi] clamped to [0, 1]. */
export function normalizeSplineRange(a: number, b: number): [number, number] {
  const lo = Math.max(0, Math.min(a, b));
  const hi = Math.min(1, Math.max(a, b));
  return [lo, hi];
}

/** Small padding so corner zoom isn't clipped at edges. */
export function padSplineRange(range: [number, number], padFraction = 0.04): [number, number] {
  const [a, b] = range;
  const span = b - a;
  const pad = Math.max(0.002, span * padFraction);
  return [Math.max(0, a - pad), Math.min(1, b + pad)];
}

export const MIN_SELECT_SPAN = 0.008;
