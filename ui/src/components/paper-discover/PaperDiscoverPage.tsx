import { DiscoverObservability } from "../discover-shared/DiscoverObservability";

export function PaperDiscoverPage() {
  return (
    <section className="page discover-page paper-discover-page">
      <header className="paper-discover-header">
        <div>
          <span className="paper-eyebrow">Paper · Discovery desk</span>
          <h1>Discover</h1>
          <p>
            Run the mixed live screener, rank candidates, and promote instruments into workspace lanes for
            paper simulation review.
          </p>
        </div>
      </header>

      <DiscoverObservability allowMutations autoRefreshOnMount />
    </section>
  );
}
