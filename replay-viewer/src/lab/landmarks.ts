// Driver-language positions (mirror of external/query_tools/coach/landmarks.py):
// "117 m before the La Source apex", gaps in car lengths, curated boards only.
import type { PackCorner } from "./types";

export function carLengthM(wheelbase: unknown): number {
  return typeof wheelbase === "number" && wheelbase > 2 && wheelbase < 3.5 ? +(1.72 * wheelbase).toFixed(2) : 4.6;
}

export function carLengths(dist: number, carLen: number): string {
  const n = Math.abs(dist) / carLen;
  if (n < 0.35) return "< ½ car";
  if (n < 0.75) return "½ car";
  if (n < 1.4) return "1 car";
  return `${Math.round(n)} cars`;
}

export function anchorCorner(s: number, corners: PackCorner[], braking = false): PackCorner | null {
  if (!corners.length) return null;
  if (braking) {
    const ahead = corners.filter((c) => c.apex_m > s + 5);
    return ahead.length ? ahead.reduce((a, b) => (b.apex_m < a.apex_m ? b : a)) : null;
  }
  const inside = corners.filter((c) => c.start_m - 40 <= s && s <= c.end_m + 60);
  const pool = inside.length ? inside : corners;
  return pool.reduce((a, b) => (Math.abs(b.apex_m - s) < Math.abs(a.apex_m - s) ? b : a));
}

/** "117 m before La Source apex" / "at La Source apex" / "40 m after Pouhon apex" / "820 m from S/F". */
export function relPos(s: number, corners: PackCorner[], braking = false): string {
  const c = anchorCorner(s, corners, braking);
  if (!c) return `${s.toFixed(0)} m`;
  const d = s - c.apex_m;
  const nm = c.display_name || c.name;
  if (Math.abs(d) > 600) return `${s.toFixed(0)} m from S/F`;
  if (Math.abs(d) <= 3) return `${nm} apex`;
  return `${Math.abs(d).toFixed(0)} m ${d < 0 ? "before" : "after"} ${nm} apex`;
}

/** Gap between where A and B do the same thing: "+6 m · 1 car later". */
export function gapText(a: number | null | undefined, b: number | null | undefined, carLen: number, whoB = "ref"): string {
  if (a == null || b == null) return "—";
  const g = b - a;
  if (Math.abs(g) < 0.35 * carLen) return "same place";
  return `${whoB} ${carLengths(g, carLen)} ${g > 0 ? "later" : "earlier"} (${Math.abs(g).toFixed(0)} m)`;
}
