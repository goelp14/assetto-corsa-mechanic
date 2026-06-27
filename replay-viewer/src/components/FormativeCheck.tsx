import { useState } from "react";
import type { CornerTimeLoss } from "../types";

interface Props {
  corners: CornerTimeLoss[];
  onReveal: () => void;
  onGuess: (cornerId: string) => void;
}

/** MIT active-learning self-check before revealing ranked losses. */
export function FormativeCheck({ corners, onReveal, onGuess }: Props) {
  const [guessed, setGuessed] = useState<string | null>(null);
  const [revealed, setRevealed] = useState(false);
  const top = corners[0];
  if (!top || top.loss_s < 0.02) return null;

  const options = corners.slice(0, 4);
  const correct = guessed === top.corner;

  if (revealed) return null;

  return (
    <div className="formative-check">
      <p>Before the reveal: which corner cost you the most time this lap?</p>
      <div className="formative-options">
        {options.map((c) => (
          <button
            key={c.corner}
            type="button"
            className={guessed === c.corner ? "selected" : ""}
            onClick={() => setGuessed(c.corner)}
          >
            {c.corner_display}
          </button>
        ))}
      </div>
      {guessed && (
        <div className="formative-result">
          {correct ? (
            <span className="ok">Correct — {top.corner_display} (+{top.loss_s.toFixed(2)}s)</span>
          ) : (
            <span className="miss">
              Actually {top.corner_display} (+{top.loss_s.toFixed(2)}s)
            </span>
          )}
          <button
            type="button"
            onClick={() => {
              setRevealed(true);
              onReveal();
              onGuess(top.corner);
            }}
          >
            Show session plan
          </button>
        </div>
      )}
    </div>
  );
}
