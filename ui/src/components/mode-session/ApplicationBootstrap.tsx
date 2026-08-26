import { useEffect, useState, type ReactNode } from "react";
import { ModeLauncher } from "./ModeLauncher";
import { ModeTransition } from "./ModeTransition";
import type { Mode, ModeReadinessTask, ReadinessTask } from "./types";

type ApplicationBootstrapProps = {
  children: (mode: Mode, switchMode: () => void) => ReactNode;
  modeReadinessTask?: ModeReadinessTask;
  readinessTask?: ReadinessTask;
};

type StartupState = "CONNECTING" | "ERROR" | "READY";

const defaultModeReadinessTask: ModeReadinessTask = () => Promise.resolve();

export const defaultReadinessTask: ReadinessTask = async () => {
  const response = await fetch("/context", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Platform readiness check failed");
};

export function ApplicationBootstrap({
  children,
  modeReadinessTask = defaultModeReadinessTask,
  readinessTask = defaultReadinessTask,
}: ApplicationBootstrapProps) {
  const [attempt, setAttempt] = useState(0);
  const [mode, setMode] = useState<Mode | null>(null);
  const [startupState, setStartupState] = useState<StartupState>("CONNECTING");

  useEffect(() => {
    let active = true;
    setStartupState("CONNECTING");
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

  if (startupState === "CONNECTING") {
    return (
      <main className="mode-session-surface">
        <section className="startup-progress" role="status" aria-live="polite">
          <p className="mode-eyebrow">Application launch</p>
          <h1>Opening market workstation</h1>
          <ol className="mode-transition-steps" aria-label="Application startup stages">
            <li data-state="complete">Starting interface</li>
            <li data-state="active">Connecting to platform</li>
            <li data-state="pending">Checking environment readiness</li>
            <li data-state="pending">Ready</li>
          </ol>
          <div role="progressbar" aria-label="Application startup" />
        </section>
      </main>
    );
  }

  if (startupState === "ERROR") {
    return (
      <main className="mode-session-surface">
        <section className="startup-progress" role="alert">
          <p>Environment readiness check failed</p>
          <h1>Could not connect to the platform.</h1>
          <p>Check that the platform service is available, then try again.</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>
            Retry
          </button>
        </section>
      </main>
    );
  }

  if (mode) {
    return (
      <ModeTransition
        mode={mode}
        readinessTask={modeReadinessTask}
        onReturn={() => setMode(null)}
      >
        {children(mode, () => setMode(null))}
      </ModeTransition>
    );
  }

  return <ModeLauncher onSelect={setMode} />;
}
