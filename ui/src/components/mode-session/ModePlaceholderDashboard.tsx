import type { Mode } from "./types";

type ModePlaceholderDashboardProps = {
  mode: Mode;
  onSwitchMode: () => void;
};

const modeDetails: Record<
  Mode,
  { boundary: string; description: string; label: string; readiness: string }
> = {
  DEMO: {
    boundary: "Historical replay · No execution",
    description: "A clean starting point for exploring replay data and learning the workstation.",
    label: "Demo",
    readiness: "Replay workspace standing by",
  },
  PAPER: {
    boundary: "Simulated orders · No live execution",
    description: "Practice market decisions in a simulated environment without real-money authority.",
    label: "Paper",
    readiness: "Simulation workspace standing by",
  },
  LIVE: {
    boundary: "Current market data · Execution authority locked",
    description: "Observe current market data in read-only mode. Live trading is not enabled.",
    label: "Live",
    readiness: "Read-only workspace standing by",
  },
};

export function ModePlaceholderDashboard({ mode, onSwitchMode }: ModePlaceholderDashboardProps) {
  const details = modeDetails[mode];

  return (
    <main className="mode-session-surface mode-dashboard" data-mode={mode.toLowerCase()}>
      <header className="mode-dashboard-bar">
        <div>
          <span className="mode-dashboard-indicator" aria-hidden="true" />
          <span>{details.label} session</span>
        </div>
        <button type="button" onClick={onSwitchMode}>
          Switch mode
        </button>
      </header>
      <section className="mode-dashboard-placeholder" aria-labelledby="mode-dashboard-title">
        <p className="mode-eyebrow">Environment initialized</p>
        <h1 id="mode-dashboard-title">{details.label} environment ready</h1>
        <p className="mode-dashboard-boundary">{details.boundary}</p>
        <p>{details.description}</p>
        <div className="mode-dashboard-empty">
          <span>{details.readiness}</span>
          <p>This dashboard will be designed piece by piece.</p>
        </div>
      </section>
    </main>
  );
}
