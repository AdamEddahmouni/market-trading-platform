import type { ReactNode } from "react";
import type { Mode } from "./types";

type Props = {
  mode: Mode;
  onSwitchMode: () => void;
  children?: ReactNode;
};

const dashboardCopy: Record<Mode, { title: string; boundary: string; description: string }> = {
  DEMO: {
    title: "Demo",
    boundary: "Historical replay · No execution",
    description: "Explore the platform using deterministic replay data.",
  },
  PAPER: {
    title: "Paper",
    boundary: "Simulated orders · No live execution",
    description: "Practice decisions in an environment where orders remain simulated.",
  },
  LIVE: {
    title: "Live",
    boundary: "Current market data · Execution authority locked",
    description: "Observe current data without enabling, staging, or submitting live orders.",
  },
};

export function ModePlaceholderDashboard({ mode, onSwitchMode, children }: Props) {
  const copy = dashboardCopy[mode];
  return (
    <main className="mode-session mode-dashboard" data-mode={mode}>
      <section className="mode-dashboard-card" aria-labelledby="mode-dashboard-heading">
        <p className="mode-session-eyebrow">Active environment · {mode}</p>
        <h1 id="mode-dashboard-heading">{copy.title} environment ready</h1>
        <p className="mode-dashboard-boundary">{copy.boundary}</p>
        <p>{copy.description}</p>
        <button type="button" onClick={onSwitchMode}>
          Switch mode
        </button>
      </section>
      {children ? <div className="mode-dashboard-content">{children}</div> : null}
    </main>
  );
}
