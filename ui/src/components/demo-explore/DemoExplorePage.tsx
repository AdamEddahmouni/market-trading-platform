import {
  ExploreObservability,
  type ExploreObservabilityProps,
} from "../explore-shared/ExploreObservability";

type Props = ExploreObservabilityProps;

export function DemoExplorePage({ onExplain }: Props) {
  return (
    <section className="page explore-page demo-explore-page">
      <header className="demo-explore-header">
        <div>
          <span className="demo-eyebrow">Demo · Historical research</span>
          <h1>Explore</h1>
          <p>
            Browse frozen donor screeners, catalyst bridges, and futures depth snapshots. All links open
            read-only workspace lanes — no execution authority in Demo.
          </p>
        </div>
        <span className="demo-state-badge">Research bridges</span>
      </header>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Demo is exploration only.</strong>
        <p>Scanner and bridge data are observational. Switch to Paper mode to route candidates into simulation.</p>
      </aside>

      <ExploreObservability onExplain={onExplain} />
    </section>
  );
}
