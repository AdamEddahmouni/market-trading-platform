import { useEffect, useState } from "react";
import type { Mode, ModeReadinessTask } from "./types";

type Props = {
  mode: Mode;
  readinessTask: ModeReadinessTask;
  onReady: () => void;
  onReturn: () => void;
};

function modeTitle(mode: Mode) {
  return mode === "DEMO" ? "Demo" : mode === "PAPER" ? "Paper" : "Live";
}

export function ModeTransition({ mode, readinessTask, onReady, onReturn }: Props) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const label = modeTitle(mode);

  useEffect(() => {
    let active = true;
    setFailed(false);
    void readinessTask(mode).then(
      () => {
        if (active) onReady();
      },
      () => {
        if (active) setFailed(true);
      },
    );
    return () => {
      active = false;
    };
  }, [attempt, mode, onReady, readinessTask]);

  if (failed) {
    return (
      <main className="mode-session mode-session-transition" data-mode={mode}>
        <section className="mode-progress-surface" aria-labelledby="mode-transition-error-heading">
          <p className="mode-session-eyebrow">{label} environment</p>
          <h1 id="mode-transition-error-heading">Could not prepare {label}</h1>
          <p>The environment readiness check did not complete. No authority was changed.</p>
          <div className="mode-transition-actions">
            <button type="button" onClick={() => setAttempt((value) => value + 1)}>
              Retry
            </button>
            <button type="button" onClick={onReturn}>
              Return to mode selection
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="mode-session mode-session-transition" data-mode={mode}>
      <section className="mode-progress-surface" aria-labelledby="mode-transition-heading">
        <p className="mode-session-eyebrow">Environment selected · {mode}</p>
        <h1 id="mode-transition-heading">Preparing {label}</h1>
        <div role="status" aria-live="polite">
          Preparing {label} environment
        </div>
        <div
          className="mode-progress-track"
          role="progressbar"
          aria-label={`${label} environment preparation`}
        >
          <span className="mode-progress-value" />
        </div>
        <ol className="mode-stage-list" aria-label="Environment readiness stages">
          <li data-state="complete">Session mode selected</li>
          <li data-state="active">Checking environment readiness</li>
          <li data-state="pending">Open dashboard</li>
        </ol>
      </section>
    </main>
  );
}
