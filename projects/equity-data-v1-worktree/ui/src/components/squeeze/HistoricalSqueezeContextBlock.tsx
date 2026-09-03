import type { WorkspaceSqueezeResponse } from "../../api/client";

type HistoricalContext = NonNullable<WorkspaceSqueezeResponse["historical_context"]>;

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function HistoricalSqueezeContextBlock({
  context,
}: {
  context: HistoricalContext | undefined;
}) {
  if (!context) {
    return null;
  }

  if (!context.available) {
    return (
      <section className="historical-squeeze-context unavailable">
        <h3>Historical squeeze context</h3>
        <p>{context.reason ?? "Symbol is not in the Phase 3F historical calibration cohort."}</p>
        {context.case_boundary_count ? (
          <p className="historical-cohort-meta">
            Cohort size: {context.case_boundary_count} case boundaries · Policy review{" "}
            {context.policy_review_status ?? "UNKNOWN"} ({context.policy_review_date ?? "—"})
          </p>
        ) : null}
      </section>
    );
  }

  const boundaries = context.case_boundaries ?? (context.primary_case ? [context.primary_case] : []);

  return (
    <section className="historical-squeeze-context available">
      <h3>Historical squeeze context</h3>
      <p className="historical-cohort-meta">
        Cohort {context.cohort_id} · {context.case_boundary_count} boundaries ·{" "}
        {context.unique_symbol_count} symbols · Policy review {context.policy_review_status} (
        {context.policy_review_date})
      </p>
      {context.disclaimer ? <p className="squeeze-disclaimer">{context.disclaimer}</p> : null}
      {boundaries.map((entry) => (
        <dl key={entry.case_id} className="squeeze-detail-grid historical-case-grid">
          <div>
            <dt>Case</dt>
            <dd>{entry.case_id}</dd>
          </div>
          <div>
            <dt>Outcome label</dt>
            <dd>{entry.outcome_label}</dd>
          </div>
          <div>
            <dt>Research classification</dt>
            <dd>{entry.research_classification}</dd>
          </div>
          <div>
            <dt>Detection status</dt>
            <dd>{entry.research_detection_status}</dd>
          </div>
          <div>
            <dt>Max move (24h)</dt>
            <dd>{formatPercent(entry.maximum_observed_move_percent)}</dd>
          </div>
          <div>
            <dt>Max adverse move</dt>
            <dd>{formatPercent(entry.maximum_adverse_move_percent)}</dd>
          </div>
          <div>
            <dt>Boundary</dt>
            <dd>{entry.evaluation_as_of}</dd>
          </div>
          <div>
            <dt>Frozen demo overlap</dt>
            <dd>{entry.in_frozen_demo ? "Yes" : "No"}</dd>
          </div>
        </dl>
      ))}
      <p className="historical-policy-meta">
        Policies: detection {context.detection_policy} · outcome {context.outcome_policy}
      </p>
    </section>
  );
}
