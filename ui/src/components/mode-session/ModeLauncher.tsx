import { useRef, useState } from "react";
import { LiveModeConfirmation } from "./LiveModeConfirmation";
import type { Mode } from "./types";

type ModeLauncherProps = {
  onSelect: (mode: Mode) => void;
};

const directModes = [
  {
    description: "Explore historical market conditions with replay data and no execution.",
    label: "Demo",
    mode: "DEMO",
    status: "Historical replay",
  },
  {
    description: "Practice decisions and place simulated orders against market data.",
    label: "Paper",
    mode: "PAPER",
    status: "Simulated execution",
  },
] as const;

export function ModeLauncher({ onSelect }: ModeLauncherProps) {
  const [liveConfirmationOpen, setLiveConfirmationOpen] = useState(false);
  const liveTriggerRef = useRef<HTMLButtonElement>(null);

  return (
    <main className="mode-session-surface">
      <section className="mode-launcher" aria-labelledby="mode-launcher-title">
        <header className="mode-launcher-header">
          <p className="mode-eyebrow">Initialize session</p>
          <h1 id="mode-launcher-title">Choose how you enter the market.</h1>
          <p>
            Set the environment for this session. You can switch modes later without leaving the
            workstation.
          </p>
        </header>
        <div className="mode-card-grid">
          {directModes.map((option) => (
            <button
              type="button"
              className={`mode-card mode-card-${option.mode.toLowerCase()}`}
              key={option.mode}
              onClick={() => onSelect(option.mode)}
            >
              <span className="mode-card-status">{option.status}</span>
              <strong>{option.label}</strong>
              <span>{option.description}</span>
            </button>
          ))}
          <button
            ref={liveTriggerRef}
            type="button"
            className="mode-card mode-card-live"
            onClick={() => setLiveConfirmationOpen(true)}
          >
            <span className="mode-card-status">Read-only current data</span>
            <strong>Live</strong>
            <span>Watch current market data. Order execution remains locked by default.</span>
          </button>
        </div>
      </section>
      {liveConfirmationOpen ? (
        <LiveModeConfirmation
          triggerRef={liveTriggerRef}
          onCancel={() => setLiveConfirmationOpen(false)}
          onConfirm={() => onSelect("LIVE")}
        />
      ) : null}
    </main>
  );
}
