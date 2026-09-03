import { useEffect, useState, type ReactNode } from "react";
import { ModeLauncher } from "./ModeLauncher";
import { ModeTransition } from "./ModeTransition";
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
  modeReadinessTask = defaultModeReadinessTask,
  children,
}: Props) {
  const [startupState, setStartupState] = useState<StartupState>("STARTING");
  const [attempt, setAttempt] = useState(0);
  const [selectedMode, setSelectedMode] = useState<Mode | null>(null);
  const [readyMode, setReadyMode] = useState<Mode | null>(null);

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

  if (!selectedMode) {
    return (
      <ModeLauncher
        onSelect={(mode) => {
          setReadyMode(null);
          setSelectedMode(mode);
        }}
      />
    );
  }

  const switchMode = () => {
    setReadyMode(null);
    setSelectedMode(null);
  };

  if (readyMode === selectedMode) return children(selectedMode, switchMode);

  return (
    <ModeTransition
      mode={selectedMode}
      readinessTask={modeReadinessTask}
      onReady={() => setReadyMode(selectedMode)}
      onReturn={switchMode}
    />
  );
}
