import { useCallback, useRef, useState } from "react";

export interface MapBounds {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}

export interface MapViewport {
  /** World-space center */
  cx: number;
  cz: number;
  /** Pixels per world unit */
  scale: number;
}

const DEFAULT_SCALE = 1.2;

export function boundsFromPoints(pts: [number, number][]): MapBounds {
  let minX = Infinity,
    maxX = -Infinity,
    minZ = Infinity,
    maxZ = -Infinity;
  for (const [x, z] of pts) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minZ = Math.min(minZ, z);
    maxZ = Math.max(maxZ, z);
  }
  return { minX, maxX, minZ, maxZ };
}

export function initialViewport(b: MapBounds): MapViewport {
  return {
    cx: (b.minX + b.maxX) / 2,
    cz: (b.minZ + b.maxZ) / 2,
    scale: DEFAULT_SCALE,
  };
}

export function viewportForWorldRect(
  b: MapBounds,
  minX: number,
  maxX: number,
  minZ: number,
  maxZ: number,
  w: number,
  h: number,
  pad = 0.15,
): MapViewport {
  const ww = Math.max(maxX - minX, 10);
  const wz = Math.max(maxZ - minZ, 10);
  const cx = (minX + maxX) / 2;
  const cz = (minZ + maxZ) / 2;
  const scaleX = (w * (1 - pad)) / ww;
  const scaleZ = (h * (1 - pad)) / wz;
  return { cx, cz, scale: Math.min(scaleX, scaleZ) };
}

// AC world is viewed from above with +z pointing down the screen (same as AC's map.png);
// drawing +z up mirrors the track and turns right-handers into left-handers.
export function worldToScreen(
  x: number,
  z: number,
  w: number,
  h: number,
  vp: MapViewport,
) {
  return {
    x: w / 2 + (x - vp.cx) * vp.scale,
    y: h / 2 + (z - vp.cz) * vp.scale,
  };
}

export function screenToWorld(
  sx: number,
  sy: number,
  w: number,
  h: number,
  vp: MapViewport,
) {
  return {
    x: vp.cx + (sx - w / 2) / vp.scale,
    z: vp.cz + (sy - h / 2) / vp.scale,
  };
}

export function useMapViewport(initial: MapViewport) {
  const [vp, setVp] = useState<MapViewport>(initial);
  const vpRef = useRef(vp);
  vpRef.current = vp;
  const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);

  const reset = useCallback((next: MapViewport) => setVp(next), []);

  const zoomAt = useCallback((sx: number, sy: number, w: number, h: number, factor: number) => {
    setVp((prev) => {
      const before = screenToWorld(sx, sy, w, h, prev);
      const scale = Math.max(0.05, Math.min(80, prev.scale * factor));
      const after = screenToWorld(sx, sy, w, h, { ...prev, scale });
      return {
        cx: prev.cx + (before.x - after.x),
        cz: prev.cz + (before.z - after.z),
        scale,
      };
    });
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    setDrag({ x: e.clientX, y: e.clientY });
  }, []);

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      setDrag({ x: e.clientX, y: e.clientY });
      setVp((prev) => ({
        ...prev,
        cx: prev.cx - dx / prev.scale,
        cz: prev.cz - dy / prev.scale,
      }));
    },
    [drag],
  );

  const onPointerUp = useCallback(() => setDrag(null), []);

  return {
    vp,
    vpRef,
    setVp,
    reset,
    zoomAt,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    dragging: drag !== null,
  };
}
