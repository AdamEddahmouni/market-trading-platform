import { useEffect, useState, type ReactNode } from "react";
import {
  defaultModeReadinessTask,
  defaultReadinessTask,
  type Mode,
  type ModeReadinessTask,
  type ReadinessTask,
} from "./types";

type StartupState = "STARTING" | "READY" | "ERROR";

type Props = {
  children: (mode: Mode, switchMode: () => void) => ReactNode;
  readinessTask?: ReadinessTask;
  modeReadinessTask?: ModeReadinessTask;
};

export function ApplicationBootstrap({
  readinessTask = defaultReadinessTask,
  modeReadinessTask: _modeReadinessTask = defaultModeReadinessTask,
  children: _children,
}: Props) {
  const [startupState, setStartupState] = useState<StartupState>("STARTING");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setStartupState("STARTING");
    void readinessTask().then(
      () => {
        if (active) setStartupState("READY");
      },
      () => {
        if (active) setStartupState("ERROR");
      },
    );
    return () => {
      active = false;
    };
  }, [attempt, readinessTask]);

  if (startupState === "STARTING") {
    return (
      <main className="mode-session mode-session-startup">
        <section className="mode-progress-surface" aria-labelledby="startup-heading">
          <p className="mode-session-eyebrow">Initialize session</p>
          <h1 id="startup-heading">Starting interface</h1>
          <div role="status" aria-live="polite">
            Connecting to platform
          </div>
          <div
            className="mode-progress-track"
            role="progressbar"
            aria-label="Platform startup progress"
          >
            <span className="mode-progress-value" />
          </div>
        </section>
      </main>
    );
  }

  if (startupState === "ERROR") {
    return (
      <main className="mode-session mode-session-startup">
        <section className="mode-progress-surface" aria-labelledby="startup-error-heading">
          <p className="mode-session-eyebrow">Platform unavailable</p>
          <h1 id="startup-error-heading">Could not connect to the platform</h1>
          <p>Check that the local platform is running, then try the readiness check again.</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>
            Retry
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="mode-session mode-session-launcher">
      <h1>Choose how you enter the market.</h1>
    </main>
  );
}
