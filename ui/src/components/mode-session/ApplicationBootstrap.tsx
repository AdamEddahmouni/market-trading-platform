import { useEffect, useState, type ReactNode } from "react";
import { ModeLauncher } from "./ModeLauncher";
import type { Mode, ReadinessTask } from "./types";

type ApplicationBootstrapProps = {
  children: (mode: Mode, switchMode: () => void) => ReactNode;
  readinessTask: ReadinessTask;
};

type StartupState = "CONNECTING" | "ERROR" | "READY";

export function ApplicationBootstrap({ children, readinessTask }: ApplicationBootstrapProps) {
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
          <p>Starting interface</p>
          <h1>Connecting to platform</h1>
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

  if (mode) return children(mode, () => setMode(null));

  return <ModeLauncher onSelect={setMode} />;
}
