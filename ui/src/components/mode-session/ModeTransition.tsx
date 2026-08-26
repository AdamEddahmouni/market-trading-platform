import { useEffect, useState, type ReactNode } from "react";
import type { Mode, ModeReadinessTask } from "./types";

type ModeTransitionProps = {
  children: ReactNode;
  mode: Mode;
  onReturn: () => void;
  readinessTask: ModeReadinessTask;
};

function titleCaseMode(mode: Mode) {
  return mode.charAt(0) + mode.slice(1).toLowerCase();
}

type TransitionState = "ERROR" | "LOADING" | "READY";

export function ModeTransition({ children, mode, onReturn, readinessTask }: ModeTransitionProps) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<TransitionState>("LOADING");

  useEffect(() => {
    let active = true;
    setState("LOADING");
    void readinessTask(mode).then(
      () => {
        if (active) setState("READY");
      },
      () => {
        if (active) setState("ERROR");
      },
    );
    return () => {
      active = false;
    };
  }, [attempt, mode, readinessTask]);

  if (state === "READY") return children;

  if (state === "ERROR") {
    const modeLabel = titleCaseMode(mode);
    return (
      <main className="mode-session-surface">
        <section className="mode-transition mode-transition-error" role="alert">
          <p className="mode-eyebrow">{modeLabel} environment</p>
          <h1>Could not prepare {modeLabel}</h1>
          <p>The environment readiness check failed. Retry, or return to mode selection.</p>
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
    <main className="mode-session-surface">
      <section className="mode-transition" role="status" aria-live="polite">
        <p className="mode-eyebrow">Preparing environment</p>
        <h1>Preparing {titleCaseMode(mode)}</h1>
        <ol className="mode-transition-steps">
          <li data-state="complete">Session selected</li>
          <li data-state="active">Checking environment readiness</li>
          <li data-state="pending">Opening dashboard</li>
        </ol>
        <div role="progressbar" aria-label={`${titleCaseMode(mode)} environment readiness`} />
      </section>
    </main>
  );
}
