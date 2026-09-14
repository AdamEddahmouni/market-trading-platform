import { DiscoverObservability } from "../discover-shared/DiscoverObservability";
import { OpportunityRadarDensePanel } from "../imp-product/OpportunityRadarDensePanel";
import { OpportunityRadarIntro } from "../imp-product/OpportunityRadarIntro";

export function DemoDiscoverPage() {
  return (
    <section className="page discover-page demo-discover-page">
      <header className="demo-discover-header">
        <div>
          <span className="demo-eyebrow">Demo · Historical research</span>
          <h1>Opportunity Radar</h1>
          <p>
            Inspect the mixed live screener queue without triggering discovery refreshes or workspace
            promotion. Workspace links are read-only navigation.
          </p>
        </div>
        <span className="demo-state-badge">Observational queue</span>
      </header>

      <OpportunityRadarIntro>
        Demo inspects the queue without discovery refresh or promotion.
      </OpportunityRadarIntro>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Demo is exploration only.</strong>
        <p>Discovery refresh and promote actions are unavailable. Switch to Paper mode to run the full discovery desk.</p>
      </aside>

      <OpportunityRadarDensePanel readOnly />

      <DiscoverObservability />
    </section>
  );
}
