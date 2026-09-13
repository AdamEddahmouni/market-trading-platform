import type { AttentionItem } from "../../api/client";
import type { OpportunityReviewRow } from "../../api/opportunityClient";

export type OpportunityReviewCardProps = {
  row: OpportunityReviewRow;
  paperAccountId?: string;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function explanationRefForRow(row: OpportunityReviewRow): string {
  if (row.explanation_ref) return row.explanation_ref;
  if (row.opportunity_id) return `explain:opportunity:${row.opportunity_id}`;
  return `explain:summary:${row.summary_id}`;
}

export function attentionItemFromOpportunity(row: OpportunityReviewRow): AttentionItem {
  return {
    attention_id: row.summary_id,
    priority_rank: row.rank_order ?? 0,
    headline: row.headline,
    instrument_id: row.instrument_id ?? undefined,
    explanation_ref: explanationRefForRow(row),
    reasons: [],
  };
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "UNAVAILABLE";
  return String(value);
}

export function OpportunityReviewCard({
  row,
  paperAccountId,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: OpportunityReviewCardProps) {
  const attention = attentionItemFromOpportunity(row);
  const identity = row.identity_kind === "OPPORTUNITY_V1" ? "OpportunityV1" : "not OpportunityV1";
  const basis = row.ranking_vector?.basis;
  const provisional = Boolean(basis && basis !== "COMPARATOR_LEXICOGRAPHIC");
  const dimensions = row.ranking_vector?.dimensions ?? [];
  const quality = row.data_quality ?? {};
  const qualityStatus = displayValue(quality.status);
  const ineligible = row.eligibility_state === "INELIGIBLE" || row.next_safe_action === "STOP";
  const canOpen = Boolean(row.instrument_id && row.next_safe_action === "OPEN_WORKSPACE" && !ineligible);
  const overlay = row.decision_support;

  return (
    <article className="opportunity-review-card" data-identity={row.identity_kind ?? "NOT_OPPORTUNITY_V1"}>
      <div className="card-head">
        <h3>{row.headline}</h3>
        {row.instrument_id ? <code>{row.instrument_id}</code> : <span className="unavailable">Instrument UNAVAILABLE</span>}
      </div>
      <p className="opportunity-identity">
        {identity}
        {row.rank_order != null ? ` · rank ${row.rank_order}` : ""}
        {row.lifecycle_state ? ` · ${row.lifecycle_state}` : ""}
      </p>
      {provisional ? (
        <p className="opportunity-provisional">Provisional order — not FTEP-tuned / not campaign-calibrated</p>
      ) : null}
      <ul className="reason-codes">
        {dimensions.map((dimension) => (
          <li key={dimension.name}>
            <code>{dimension.name}</code>{" "}
            {dimension.status === "PRESENT" ? displayValue(dimension.value) : "UNAVAILABLE"}
            {dimension.unit && dimension.status === "PRESENT" ? ` ${dimension.unit}` : ""}
            {dimension.reason_code ? ` (${dimension.reason_code})` : ""}
          </li>
        ))}
      </ul>
      <p className="opportunity-quality">
        Data quality {qualityStatus}
        {quality.freshness ? ` · freshness ${displayValue(quality.freshness)}` : ""}
      </p>
      {paperAccountId ? (
        <p className="opportunity-account">
          Paper account <code>{paperAccountId}</code>
        </p>
      ) : null}
      {overlay ? (
        <p className="opportunity-decision-support">
          Risk overlay {overlay.authority ?? "DOWNSTREAM_RISK_NOT_RANKING"} · kill switch{" "}
          {overlay.kill_switch ?? "UNAVAILABLE"}
        </p>
      ) : null}
      <p className="opportunity-next">
        Next safe action: {ineligible ? "STOP" : row.next_safe_action ?? "NONE"}
      </p>
      <div className="card-actions">
        <button type="button" onClick={() => onExplain(attention)}>
          Explain
        </button>
        <button type="button" onClick={() => onInspect(attention)}>
          Inspect
        </button>
        {canOpen ? (
          <button type="button" onClick={() => onOpenWorkspace(attention)}>
            Open workspace
          </button>
        ) : null}
      </div>
    </article>
  );
}

export type OpportunityReviewListProps = {
  items: OpportunityReviewRow[];
  state: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  paperAccountId?: string;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

export function OpportunityReviewList({
  items,
  state,
  feedStatus,
  unreadyReason,
  nextAction,
  paperAccountId,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: OpportunityReviewListProps) {
  if (state === "loading") return <p role="status">Loading opportunity review…</p>;
  if (state === "error") return <p role="alert">Opportunity review unavailable.</p>;
  if (feedStatus === "UNREADY") {
    return (
      <p role="status" className="unavailable">
        Opportunity review is unready{unreadyReason ? ` (${unreadyReason})` : ""}.{" "}
        <a href={nextAction || "/control"}>Open Control Center</a>
      </p>
    );
  }
  if (!items.length) {
    return (
      <p className="unavailable">
        No OpportunityV1 candidates. An empty queue is valid when nothing has been minted.
      </p>
    );
  }
  return (
    <div className="opportunity-review-list">
      {items.map((row) => (
        <OpportunityReviewCard
          key={row.summary_id}
          row={row}
          paperAccountId={paperAccountId}
          onExplain={onExplain}
          onInspect={onInspect}
          onOpenWorkspace={onOpenWorkspace}
        />
      ))}
    </div>
  );
}
