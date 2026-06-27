import type { CornerTimeLoss } from "../types";

const GENERIC_ACTION =
  /^Target \+\d+\.\d+s by improving (entry|mid|exit) phase\.?$/i;

/** Turn time-loss rows into plain-language issue + drill (works on old exports too). */
export function formatCornerCoaching(corner: CornerTimeLoss): {
  issue?: string;
  drill: string;
} {
  const fix = corner.fixes?.[0];
  const rawAction = corner.primary_action || fix?.action || "";
  const title = corner.primary_title || fix?.title || "";
  const what = fix?.what || "";

  let issue = title || what || undefined;
  if (issue && GENERIC_ACTION.test(issue)) issue = undefined;

  let drill = rawAction;
  if (!drill || GENERIC_ACTION.test(drill)) {
    if (what && !GENERIC_ACTION.test(what)) drill = what;
    else if (title && !GENERIC_ACTION.test(title)) drill = title;
    else if (fix?.phase) {
      drill = `Open the ${fix.phase} trace here — compare speed and throttle to your best lap at ${corner.corner_display}.`;
    } else {
      drill = `Inspect speed, brake, and throttle at ${corner.corner_display}.`;
    }
  }

  if (issue && issue === drill) issue = undefined;

  return { issue, drill };
}

export function lapTimeLabel(
  laps: { lap: number; lap_time_ms: number }[],
  lapNum: number,
): string {
  const row = laps.find((l) => l.lap === lapNum);
  if (!row?.lap_time_ms) return `L${lapNum}`;
  return `L${lapNum} (${(row.lap_time_ms / 1000).toFixed(3)}s)`;
}
