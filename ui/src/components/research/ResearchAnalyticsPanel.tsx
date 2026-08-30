import type { ResearchAnalyticsResponse } from "../../api/schemas";
import { CountBarChartPanel, SignalTimelineChartPanel } from "../charts/ResearchChartPanels";

type Props = {
  payload: ResearchAnalyticsResponse;
};

export function ResearchAnalyticsPanel({ payload }: Props) {
  const panels = payload.panels;

  return (
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
        title="Historical squeeze cohort (Phase 3F calibration)"
        series={panels.squeeze_historical_cohort.series}
        provenance={{
          source: String(panels.squeeze_historical_cohort.provenance.source ?? "cohort fixture"),
          method: String(
            panels.squeeze_historical_cohort.provenance.method ?? "historical cohort projection",
          ),
        }}
        emptyMessage="Historical cohort summary unavailable."
        ariaLabel="Historical squeeze cohort bar chart"
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
        timeline={panels.strategy_outcomes.signal_timeline ?? []}
        provenance={{
          source: panels.strategy_outcomes.provenance.source,
          method: "Cumulative signal count by observation index at cutoff",
        }}
        ariaLabel="Walk-forward signal timeline chart"
      />
    </div>
  );
}
