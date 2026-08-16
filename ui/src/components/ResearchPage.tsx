import { useResearchAnalyticsQuery } from "../api/hooks";
import { CountBarChartPanel, SignalTimelineChartPanel } from "./charts/ResearchChartPanels";

export function ResearchPage() {
  const analyticsQuery = useResearchAnalyticsQuery();

  if (analyticsQuery.isLoading) {
    return <div className="app-loading">Loading research analytics…</div>;
  }

  if (analyticsQuery.error || !analyticsQuery.data) {
    return (
      <section className="page gated-page">
        <h1>RESEARCH</h1>
        <p>Research analytics unavailable.</p>
      </section>
    );
  }

  const payload = analyticsQuery.data;
  const panels = payload.panels;

  return (
    <section className="page research-page">
      <header className="page-header">
        <h1>Research analytics</h1>
        <p>{payload.disclaimer}</p>
        <p className="research-meta">
          Epistemic class: {payload.epistemic_class} · Boundary: {payload.authority_boundary}
        </p>
      </header>
      <div className="chart-grid">
        <CountBarChartPanel
          title="Attention tier distribution"
          series={panels.attention_tiers.series}
          provenance={{
            source: panels.attention_tiers.provenance.source,
            method: panels.attention_tiers.provenance.method,
          }}
          ariaLabel="Attention tier bar chart"
        />
        <CountBarChartPanel
          title="Squeeze screener outcomes"
          series={panels.squeeze_outcomes.series}
          provenance={{
            source: panels.squeeze_outcomes.provenance.source,
            method: panels.squeeze_outcomes.provenance.method,
          }}
          emptyMessage={
            panels.squeeze_outcomes.available
              ? "No squeeze rows in donor bridge."
              : panels.squeeze_outcomes.reason ?? "Donor bridge unavailable."
          }
          ariaLabel="Squeeze outcome bar chart"
        />
        <CountBarChartPanel
          title="Strategy interpretation outcomes"
          series={panels.strategy_outcomes.series}
          provenance={{
            source: panels.strategy_outcomes.provenance.source,
            method: panels.strategy_outcomes.provenance.method,
          }}
          ariaLabel="Strategy outcome bar chart"
        />
        <CountBarChartPanel
          title="Risk simulation decisions"
          series={panels.risk_decisions.series}
          provenance={{
            source: panels.risk_decisions.provenance.source,
            method: panels.risk_decisions.provenance.method,
          }}
          ariaLabel="Risk decision bar chart"
        />
        <SignalTimelineChartPanel
          title="Cumulative strategy signals (walk-forward)"
          timeline={panels.strategy_outcomes.signal_timeline}
          provenance={{
            source: panels.strategy_outcomes.provenance.source,
            method: "Cumulative signal count by observation index at cutoff",
          }}
          ariaLabel="Walk-forward signal timeline chart"
        />
      </div>
    </section>
  );
}
