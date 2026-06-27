import { useMemo } from "react";
import type { Annotation, ChannelAvailability, CornerTimeLoss, LapSample } from "../types";
import { enrichSamples } from "../utils/telemetryDerived";
import { DistanceChart } from "./charts/DistanceChart";
import { TimeLossPanel } from "./TimeLossPanel";

interface Props {
  samples: LapSample[];
  compareSamples?: LapSample[];
  stitchedLoss: number[];
  playheadSpline: number;
  viewRange?: [number, number] | null;
  highlightRange?: [number, number] | null;
  annotations: Annotation[];
  activeLap?: number | null;
  timeLossCorners: CornerTimeLoss[];
  potentialGapS: number;
  theoreticalBestMs?: number;
  lapTimeMs?: number;
  availability: ChannelAvailability;
  onSplineChange: (spline: number) => void;
  onViewRangeChange?: (range: [number, number]) => void;
  onTimeLossCorner?: (corner: CornerTimeLoss) => void;
}

export function GuidedChartStack({
  samples: rawSamples,
  compareSamples: rawCompare,
  stitchedLoss,
  playheadSpline,
  viewRange,
  highlightRange,
  annotations,
  activeLap,
  timeLossCorners,
  potentialGapS,
  theoreticalBestMs,
  lapTimeMs,
  availability,
  onSplineChange,
  onViewRangeChange,
  onTimeLossCorner,
}: Props) {
  const samples = useMemo(() => enrichSamples(rawSamples), [rawSamples]);
  const compareSamples = useMemo(
    () => (rawCompare?.length ? enrichSamples(rawCompare) : undefined),
    [rawCompare],
  );

  const distCommon = {
    samples,
    compareSamples,
    playheadSpline,
    viewRange,
    highlightRange,
    annotations,
    timeLossCorners,
    activeLap,
    showPhaseBands: false,
    onSplineChange,
    onViewRangeChange,
  };

  return (
    <div className="guided-chart-stack">
      {availability.time_loss && (
        <TimeLossPanel
          potentialGapS={potentialGapS}
          theoreticalBestMs={theoreticalBestMs}
          lapTimeMs={lapTimeMs}
          corners={timeLossCorners}
          onSelectCorner={(c) => onTimeLossCorner?.(c)}
        />
      )}
      <div className="chart-scroll">
        <DistanceChart {...distCommon} mode="speed" />
        <DistanceChart {...distCommon} mode="brake" showBrake showThrottle={false} />
        <DistanceChart {...distCommon} mode="throttle" showBrake={false} showThrottle />
        {stitchedLoss.length > 0 && (
          <DistanceChart {...distCommon} delta={stitchedLoss} mode="timeloss" />
        )}
      </div>
    </div>
  );
}
