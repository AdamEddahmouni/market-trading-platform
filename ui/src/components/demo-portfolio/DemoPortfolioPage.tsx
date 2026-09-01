import { usePaperPortfolioQuery } from "../../api/hooks";
import { PaperPortfolioObservability } from "../portfolio-shared/PaperPortfolioObservability";

export function DemoPortfolioPage() {
  const portfolioQuery = usePaperPortfolioQuery();

  if (portfolioQuery.isLoading) {
    return (
      <section className="page portfolio-page demo-portfolio-page">
        <h1>Demo Portfolio</h1>
        <p role="status">Loading simulated portfolio…</p>
      </section>
    );
  }

  if (portfolioQuery.isError || !portfolioQuery.data) {
    return (
      <section className="page portfolio-page demo-portfolio-page">
        <h1>Demo Portfolio</h1>
        <div className="capability-panel unavailable">
          <p>Simulated portfolio unavailable.</p>
        </div>
      </section>
    );
  }

  const data = portfolioQuery.data;
  const { account, data_health } = data;

  return (
    <section className="page portfolio-page demo-portfolio-page">
      <header className="demo-portfolio-header">
        <div>
          <span className="demo-eyebrow">Demo · exploration only</span>
          <h1>Demo Portfolio</h1>
          <p>
            Simulated account, positions, and fills are shown for learning and replay context. Order
            and session controls are unavailable in Demo.
          </p>
          <p className="portfolio-provenance">
            DATA: {account.data_mode.replace(/_/g, " ")} · {account.data_provider} · QUALITY{" "}
            {data_health.state}
            {" · "}
            EXEC: {account.execution_mode.replace(/_/g, " ")} · AUTH {account.execution_authority}
          </p>
        </div>
        <span className="demo-state-badge">Observational snapshot</span>
      </header>

      <aside className="panel mode-restriction-note" role="note">
        <strong>Demo is exploration only.</strong>
        <p>Order and session controls are unavailable. Switch to Paper mode to manage simulation sessions.</p>
      </aside>

      <PaperPortfolioObservability data={data} />
    </section>
  );
}
