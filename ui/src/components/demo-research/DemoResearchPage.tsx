import { ResearchObservability } from "../research-shared/ResearchObservability";

export function DemoResearchPage() {
  return (
    <section className="page research-page demo-research-page">
      <header className="demo-research-header">
        <div>
          <span className="demo-eyebrow">Demo · Historical research</span>
          <h1>Research</h1>
          <p>Replay-bound research projections. No trade authority — inspect analytics, models, and simulation output only.</p>
        </div>
        <span className="demo-state-badge">Read-only research</span>
      </header>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Demo is exploration only.</strong>
        <p>Research surfaces never grant execution authority. Switch to Paper mode to connect findings to simulation.</p>
      </aside>

      <ResearchObservability />
    </section>
  );
}
