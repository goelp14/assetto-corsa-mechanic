import { useCallback, useRef, useState } from "react";

/** Shared playhead spline — ref for charts, throttled state for React UI. */
export function usePlayhead(initial = 0, throttleMs = 32) {
  const ref = useRef(initial);
  const [spline, setSpline] = useState(initial);
  const lastEmit = useRef(0);

  const setPlayhead = useCallback(
    (s: number) => {
      ref.current = s;
      const now = performance.now();
      if (now - lastEmit.current >= throttleMs) {
        lastEmit.current = now;
        setSpline(s);
      }
    },
    [throttleMs],
  );

  const flushPlayhead = useCallback(() => {
    setSpline(ref.current);
  }, []);

  return { playheadRef: ref, playheadSpline: spline, setPlayhead, flushPlayhead };
}
