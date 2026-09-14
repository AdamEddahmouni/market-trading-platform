import { DiscoverObservability } from "../discover-shared/DiscoverObservability";
import { OpportunityRadarDensePanel } from "../imp-product/OpportunityRadarDensePanel";
import { OpportunityRadarIntro } from "../imp-product/OpportunityRadarIntro";

export function PaperDiscoverPage() {
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

      <OpportunityRadarDensePanel />

      <DiscoverObservability allowMutations autoRefreshOnMount />
    </section>
  );
}
