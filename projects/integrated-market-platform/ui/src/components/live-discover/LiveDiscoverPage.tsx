import { Link } from "react-router-dom";
import type { DiscoverInspectorActions } from "../discover-shared/discoverInspectorActions";
import { DiscoverMixedScreenerSection, DiscoverRankedQueueSection } from "../discover-shared/DiscoverPageSections";
import { DiscoverObservability } from "../discover-shared/DiscoverObservability";
import { OpportunityRadarDensePanel } from "../imp-product/OpportunityRadarDensePanel";
import { OpportunityRadarIntro } from "../imp-product/OpportunityRadarIntro";

type Props = DiscoverInspectorActions;

export function LiveDiscoverPage({ onExplain, onInspect, onOpenWorkspace }: Props) {
  return (
    <section className="page discover-page live-discover-page">
      <header className="live-discover-header">
        <div>
          <span className="live-eyebrow">Live · Read-only observational</span>
          <h1>Opportunity Radar</h1>
          <p>
            Monitor the mixed live screener without discovery mutations or workspace promotion. Use the live
            canary for operational safety review.
          </p>
        </div>
        <Link to="/live-canary">Open live canary</Link>
      </header>

      <OpportunityRadarIntro>
        Live monitor only — no discovery mutations or workspace promotion.
      </OpportunityRadarIntro>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Live is read-only here.</strong>
        <p>Refresh and promote controls are hidden. Workspace links navigate without changing live analysis subscriptions.</p>
      </aside>

      <DiscoverRankedQueueSection>
        <OpportunityRadarDensePanel
          readOnly
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      </DiscoverRankedQueueSection>

      <DiscoverMixedScreenerSection>
        <DiscoverObservability />
      </DiscoverMixedScreenerSection>
    </section>
  );
}
