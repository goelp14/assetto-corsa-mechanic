import { useMemo } from "react";
import type { Annotation, ChannelAvailability, CornerTimeLoss, LapSample, LayerState } from "../types";
import { enrichSamples } from "../utils/telemetryDerived";
import { DistanceChart } from "./charts/DistanceChart";
import { GgDiagram } from "./charts/GgDiagram";
import { SteeringArea } from "./charts/SteeringArea";
import { LazyChartRow } from "./charts/LazyChartRow";
import { TimeLossPanel } from "./TimeLossPanel";

interface Props {
  samples: LapSample[];
  compareSamples?: LapSample[];
  delta: number[];
  stitchedLoss?: number[];
  playheadSpline: number;
  layers: LayerState;
  availability: ChannelAvailability;
  annotations: Annotation[];
  activeLap?: number | null;
  viewRange?: [number, number] | null;
  highlightRange?: [number, number] | null;
  peakAy?: number[];
  timeLossCorners?: CornerTimeLoss[];
  potentialGapS?: number;
  theoreticalBestMs?: number;
  lapTimeMs?: number;
  onSplineChange: (spline: number) => void;
  onViewRangeChange?: (range: [number, number]) => void;
  onTimeLossCorner?: (corner: CornerTimeLoss) => void;
}

export function TelemetryCharts({
  samples: rawSamples,
  compareSamples: rawCompare,
  delta,
  stitchedLoss,
  playheadSpline,
  layers,
  availability,
  annotations,
  activeLap,
  viewRange,
  highlightRange,
  peakAy,
  timeLossCorners = [],
  potentialGapS = 0,
  theoreticalBestMs,
  lapTimeMs,
  onSplineChange,
  onViewRangeChange,
  onTimeLossCorner,
}: Props) {
  const samples = useMemo(() => enrichSamples(rawSamples), [rawSamples]);
  const compareSamples = useMemo(
    () => (rawCompare?.length ? enrichSamples(rawCompare) : undefined),
    [rawCompare],
  );

  const showPhaseBands = layers.chartPhase;
  const distCommon = {
    samples,
    compareSamples,
    playheadSpline,
    viewRange,
    highlightRange,
    annotations,
    timeLossCorners,
    activeLap,
    showPhaseBands,
    onSplineChange,
    onViewRangeChange,
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8, flexShrink: 0 }}>
        {annotations
          .filter((a) => a.spline > 0 && (activeLap == null || !a.lap || a.lap === activeLap))
          .slice(0, 12)
          .map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => onSplineChange(a.spline)}
              onDoubleClick={() => {
                if (a.spline_start != null && a.spline_end != null) {
                  onViewRangeChange?.([a.spline_start, a.spline_end]);
                }
              }}
              style={{
                fontSize: 10,
                padding: "3px 8px",
                borderRadius: 4,
                border: "none",
                cursor: "pointer",
                background: a.category === "opportunity" ? "#164e63" : "#431407",
                color: "#e2e8f0",
              }}
              title={a.action || a.what}
            >
              {a.corner_display || a.title?.slice(0, 48)}
            </button>
          ))}
      </div>

      {layers.chartTimeLoss && availability.time_loss && (
        <TimeLossPanel
          potentialGapS={potentialGapS}
          theoreticalBestMs={theoreticalBestMs}
          lapTimeMs={lapTimeMs}
          corners={timeLossCorners}
          onSelectCorner={(c) => onTimeLossCorner?.(c)}
        />
      )}

      <div className="chart-scroll">
        {layers.chartTimeLoss && stitchedLoss && stitchedLoss.length > 0 && (
          <LazyChartRow minHeight={120}>
            <DistanceChart {...distCommon} delta={stitchedLoss} mode="timeloss" />
          </LazyChartRow>
        )}

        {layers.chartSpeed && (
          <LazyChartRow minHeight={120}>
            <DistanceChart {...distCommon} mode="speed" />
          </LazyChartRow>
        )}

        {layers.chartLatG && availability.acc_g_lat && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="latg" />
          </LazyChartRow>
        )}

        {layers.chartGg && availability.gg_envelope && availability.acc_g_long && (
          <LazyChartRow minHeight={200}>
            <GgDiagram
              samples={samples}
              playheadSpline={playheadSpline}
              viewRange={viewRange}
              peakAy={peakAy}
              onSplineChange={onSplineChange}
            />
          </LazyChartRow>
        )}

        {layers.chartGrip && availability.gg_envelope && peakAy?.length && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="grip" peakAy={peakAy} />
          </LazyChartRow>
        )}

        {layers.chartLongG && availability.acc_g_long && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="longg" />
          </LazyChartRow>
        )}

        {layers.chartBalance && availability.delta_us_deg && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="balance" />
          </LazyChartRow>
        )}

        {layers.chartBeta && availability.beta_deg && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="beta" />
          </LazyChartRow>
        )}

        {layers.chartYaw && availability.yaw_rate && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="yaw" />
          </LazyChartRow>
        )}

        {layers.chartWheelLoad && availability.wheel_load && (
          <LazyChartRow minHeight={110}>
            <DistanceChart {...distCommon} mode="wheel_load" />
          </LazyChartRow>
        )}

        {layers.chartSuspension && availability.susp_ratio && (
          <LazyChartRow minHeight={110}>
            <DistanceChart {...distCommon} mode="suspension" />
          </LazyChartRow>
        )}

        {layers.chartBrake && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="brake" showBrake showThrottle={false} />
          </LazyChartRow>
        )}
        {layers.chartThrottle && (
          <LazyChartRow>
            <DistanceChart {...distCommon} mode="throttle" showBrake={false} showThrottle />
          </LazyChartRow>
        )}

        {layers.chartSteer && (
          <>
            <LazyChartRow minHeight={80}>
              <SteeringArea
                samples={samples}
                playheadSpline={playheadSpline}
                viewRange={viewRange}
                onSplineChange={onSplineChange}
              />
            </LazyChartRow>
            <LazyChartRow>
              <DistanceChart {...distCommon} mode="steering" />
            </LazyChartRow>
          </>
        )}

        {layers.chartDelta && delta.length > 0 && (
          <LazyChartRow>
            <DistanceChart {...distCommon} delta={delta} mode="delta" />
          </LazyChartRow>
        )}
      </div>
    </div>
  );
}
