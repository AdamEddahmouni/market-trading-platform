import { useOpportunitiesSummaryQuery, type OpportunityReviewRow } from "../../api/opportunitiesClient";

export type OpportunityReviewCardProps = {
  row: OpportunityReviewRow;
  mode: "DEMO" | "PAPER";
  accountId?: string;
  onExplain?: (row: OpportunityReviewRow) => void;
  onInspect?: (row: OpportunityReviewRow) => void;
  onOpenWorkspace?: (instrumentId: string) => void;
};

function dimensionLine(row: OpportunityReviewRow): string {
  const dimensions = row.ranking_vector?.dimensions ?? [];
  const present = dimensions.filter((item) => item.status === "PRESENT");
  if (!present.length) return "Ranking dimensions unavailable.";
  return present
    .slice(0, 4)
    .map((item) => `${item.name}: ${item.value ?? "UNAVAILABLE"}`)
    .join(" · ");
}

export function OpportunityReviewCard({
  row,
  mode,
  accountId,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: OpportunityReviewCardProps) {
  const eligible = row.eligibility_state === "ELIGIBLE" || row.lifecycle_state === "RANKED";
  const canPreview = mode === "PAPER" && eligible && Boolean(row.instrument_id);
  const basis = row.ranking_vector?.basis;
  const provisional = basis != null && basis !== "COMPARATOR_LEXICOGRAPHIC";
  const identity = row.identity_kind === "OPPORTUNITY_V1" ? row.opportunity_id ?? row.summary_id : "not OpportunityV1";
  const qualityStatus =
    row.data_quality && typeof row.data_quality.status === "string"
      ? row.data_quality.status
      : "UNAVAILABLE";

  return (
    <article className="opportunity-review-card attention-card" data-identity={row.identity_kind ?? "UNAVAILABLE"}>
      <div className="card-head">
        <h3>{row.headline}</h3>
        {row.instrument_id ? <span className="symbol">{row.instrument_id}</span> : null}
      </div>
      <p className="muted">
        {identity}
        {row.rank_order != null ? ` · rank ${row.rank_order}` : ""}
        {accountId ? ` · account ${accountId}` : ""}
      </p>
      {provisional ? (
        <p className="unavailable">Provisional order — not FTEP-tuned / not campaign-calibrated.</p>
      ) : null}
      <p>{dimensionLine(row)}</p>
      <p className="muted">Data quality: {qualityStatus}</p>
      {row.decision_support ? (
        <p className="muted">
          Risk overlay {row.decision_support.authority} — not used for ranking.
        </p>
      ) : null}
      <p>Next: {row.next_safe_action ?? "NONE"}</p>
      <div className="card-actions">
        {onExplain ? (
          <button type="button" onClick={() => onExplain(row)}>
            Explain
          </button>
        ) : null}
        {onInspect ? (
          <button type="button" onClick={() => onInspect(row)}>
            Inspect
          </button>
        ) : null}
        {canPreview && row.instrument_id && onOpenWorkspace ? (
          <button type="button" onClick={() => onOpenWorkspace(row.instrument_id as string)}>
            Open Paper workspace
          </button>
        ) : null}
        {!eligible ? <span className="unavailable">Ineligible — no preview.</span> : null}
        {mode === "DEMO" ? <span className="muted">Demo is read-only.</span> : null}
      </div>
    </article>
  );
}

export type OpportunityReviewQueueProps = {
  mode: "DEMO" | "PAPER";
  accountId?: string;
  onExplain?: (row: OpportunityReviewRow) => void;
  onInspect?: (row: OpportunityReviewRow) => void;
  onOpenWorkspace?: (instrumentId: string) => void;
};

export function OpportunityReviewQueue({
  mode,
  accountId,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: OpportunityReviewQueueProps) {
  const query = useOpportunitiesSummaryQuery(true);
  if (query.isLoading) return <p role="status">Loading opportunity review…</p>;
  if (query.isError || !query.data) return <p role="alert">Opportunity review unavailable.</p>;
  const feed = query.data;
  if (feed.feed_status === "UNAVAILABLE") {
    return <p className="unavailable">{feed.reason ?? "Opportunity Engine is not available in this mode."}</p>;
  }
  if (feed.feed_status === "UNREADY") {
    return (
      <p className="unavailable">
        Opportunity queue is unready. {feed.unready_reason ?? "Operator readiness is not PASS."}{" "}
        <a href={feed.next_action ?? "/control"}>Open Control</a>
      </p>
    );
  }
  if (!feed.items.length) {
    return <p className="unavailable">No governed opportunities. An empty queue is valid when nothing is MATCHED.</p>;
  }
  return (
    <div className="opportunity-review-queue">
      {feed.items.map((row) => (
        <OpportunityReviewCard
          key={row.summary_id}
          row={row}
          mode={mode}
          accountId={accountId}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      ))}
    </div>
  );
}

