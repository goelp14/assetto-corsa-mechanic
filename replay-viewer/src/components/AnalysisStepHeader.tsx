export type AnalysisStep = 1 | 2 | 3 | 4 | 5;

const STEPS = [
  { n: 1 as const, label: "Overview", hint: "Where is time on the table?" },
  { n: 2 as const, label: "Segment", hint: "Pick one corner" },
  { n: 3 as const, label: "Relate", hint: "Speed · brake · throttle vs ref" },
  { n: 4 as const, label: "Tutor", hint: "Evidence → drill" },
  { n: 5 as const, label: "Explore", hint: "Physics & export layers" },
];

interface Props {
  activeStep: AnalysisStep;
  viewMode: "guided" | "explore";
}

export function AnalysisStepHeader({ activeStep, viewMode }: Props) {
  return (
    <div className="analysis-steps">
      {STEPS.map((s) => {
        const active = viewMode === "explore" ? s.n === 5 : s.n === activeStep;
        const done = viewMode === "guided" && s.n < activeStep;
        return (
          <div
            key={s.n}
            className={[
              "analysis-step",
              active ? "active" : "",
              done ? "done" : "",
            ].join(" ")}
            title={s.hint}
          >
            <span className="analysis-step-num">{s.n}</span>
            <span className="analysis-step-label">{s.label}</span>
          </div>
        );
      })}
    </div>
  );
}

export function deriveAnalysisStep(
  viewMode: "guided" | "explore",
  selectedCorner: string | null,
  hasAnnotation: boolean,
): AnalysisStep {
  if (viewMode === "explore") return 5;
  if (hasAnnotation) return 4;
  if (selectedCorner) return 3;
  return 1;
}
