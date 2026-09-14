import type { DiscoverInspectorActions } from "../discover-shared/discoverInspectorActions";
import { DiscoverMixedScreenerSection, DiscoverRankedQueueSection } from "../discover-shared/DiscoverPageSections";
import { DiscoverObservability } from "../discover-shared/DiscoverObservability";
import { OpportunityRadarDensePanel } from "../imp-product/OpportunityRadarDensePanel";
import { OpportunityRadarIntro } from "../imp-product/OpportunityRadarIntro";

type Props = DiscoverInspectorActions;

export function PaperDiscoverPage({ onExplain, onInspect, onOpenWorkspace }: Props) {
  return (
    <section className="page discover-page paper-discover-page">
      <header className="paper-discover-header">
        <div>
          <span className="paper-eyebrow">Paper · Discovery desk</span>
          <h1>Opportunity Radar</h1>
          <p>
            Run the mixed live screener, rank candidates, and promote instruments into workspace lanes for
            paper simulation review.
          </p>
        </div>
      </header>

      <OpportunityRadarIntro>
        Promote candidates into workspace lanes for paper simulation review; broker execution stays off.
      </OpportunityRadarIntro>

      <DiscoverRankedQueueSection>
        <OpportunityRadarDensePanel
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      </DiscoverRankedQueueSection>

      <DiscoverMixedScreenerSection>
        <DiscoverObservability allowMutations autoRefreshOnMount />
      </DiscoverMixedScreenerSection>
    </section>
  );
}
