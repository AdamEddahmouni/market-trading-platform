import type { PaperPortfolioResponse } from "../../api/client";

export function portfolioMetrics(portfolio: PaperPortfolioResponse) {
  return [
    { label: "Cash", value: portfolio.account.cash_display },
    { label: "Total P&L", value: portfolio.pnl?.total_display ?? portfolio.account.realized_pnl_display },
    { label: "Gross exposure", value: `${portfolio.exposure?.gross_shares ?? 0} shares` },
    { label: "Open orders", value: String(portfolio.risk.open_order_count) },
  ];
}

type Props = {
  state: "loading" | "ready" | "error";
  portfolio?: PaperPortfolioResponse;
};

export function DemoPortfolioSummary({ state, portfolio }: Props) {
  const available = state === "ready" && portfolio;
  return (
    <section className="demo-now-panel demo-portfolio-panel" aria-labelledby="demo-portfolio-title">
      <div className="demo-panel-heading">
        <div>
          <p className="demo-eyebrow">Simulation account</p>
          <h2 id="demo-portfolio-title">Simulated portfolio</h2>
        </div>
        <span className="demo-state-badge">Observational snapshot</span>
      </div>
      {state === "loading" ? <p role="status">Loading simulated portfolio…</p> : null}
      {!available && state !== "loading" ? <p className="unavailable">Simulated portfolio unavailable.</p> : null}
      {available ? (
        <dl className="demo-metric-grid">
          {portfolioMetrics(portfolio).map((metric) => (
            <div key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      <p className="demo-panel-note">Values are simulated and read-only in Demo.</p>
    </section>
  );
}
