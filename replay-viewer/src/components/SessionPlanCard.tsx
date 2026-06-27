import type { CornerTimeLoss, SessionPlan, SessionPlanItem } from "../types";
import { formatCornerCoaching } from "../utils/formatCoachDrill";

interface Props {
  sessionPlan: SessionPlan | null;
  timeLossCorners: CornerTimeLoss[];
  onSelectCorner: (cornerId: string) => void;
}

function planItems(sessionPlan: SessionPlan | null, corners: CornerTimeLoss[]): SessionPlanItem[] {
  if (sessionPlan?.items?.length) return sessionPlan.items.slice(0, 2);
  return corners.slice(0, 2).map((c) => ({
    corner: c.corner,
    corner_display: c.corner_display,
    loss_s: c.loss_s,
    drill: formatCornerCoaching(c).drill,
    spline_start: c.spline_start,
    spline_end: c.spline_end,
  }));
}

export function SessionPlanCard({ sessionPlan, timeLossCorners, onSelectCorner }: Props) {
  const items = planItems(sessionPlan, timeLossCorners);
  if (!items.length) return null;

  return (
    <div className="session-plan-card">
      <div className="session-plan-header">
        <strong>Session plan</strong>
        <span className="session-plan-hint">Top 2 fixes for next stint</span>
      </div>
      <div className="session-plan-items">
        {items.map((item, i) => (
          <button
            key={item.corner}
            type="button"
            className="session-plan-item"
            onClick={() => onSelectCorner(item.corner)}
          >
            <span className="session-plan-rank">{i + 1}</span>
            <span className="session-plan-body">
              <span className="session-plan-corner">{item.corner_display}</span>
              {item.loss_s > 0 && (
                <span className="session-plan-loss">+{item.loss_s.toFixed(2)}s</span>
              )}
              {item.drill && <span className="session-plan-drill">{item.drill}</span>}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
