import type { AttentionItem } from "../../api/client";
import type { OpportunityAckAction, OpportunityReviewRow } from "../../api/opportunityClient";
import { humanizeEnum } from "../../state/semanticState";
import { AttentionBanner } from "../imp-ui/AttentionBanner";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { StatePill } from "../imp-ui/StatePill";
import {
  attentionItemFromOpportunity,
  canAckOpportunity,
  canOpenOpportunityWorkspace,
  derivePresentationState,
  evidenceInputsSummary,
  hasProvisionalOrder,
  isOpportunityIneligible,
  OPPORTUNITY_STATE_LABEL,
  OPPORTUNITY_STATE_TONE,
  opportunityNextActionState,
  opportunityRankLabel,
  opportunitySymbol,
  stableOpportunityKey,
} from "./opportunityPresentation";

export type OpportunityCardProps = {
  row: OpportunityReviewRow;
  /** Paper account context: ack actions render only with paper authority. */
  paperAccountId?: string;
  readOnly?: boolean;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
};

/**
 * The compact opportunity card for Command and Paper queues — the same
 * semantic state, evidence, freshness, and next-action primitives as Radar,
 * at glance density. Deep detail lives on Radar; this card leads there.
 * Visibility is not actionability: no control here grants authority.
 */
export function OpportunityCard({
  row,
  paperAccountId,
  readOnly = false,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
}: OpportunityCardProps) {
  const attention = attentionItemFromOpportunity(row);
  const presentation = derivePresentationState(row);
  const nextAction = opportunityNextActionState(row);
  const ineligible = isOpportunityIneligible(row);
  const canOpen = canOpenOpportunityWorkspace(row);
  const canAck = Boolean(paperAccountId && onAck && !readOnly && canAckOpportunity(row));
  const rank = opportunityRankLabel(row);
  const freshness = row.data_quality?.freshness;
  const eligibility = row.eligibility_state;
  const showEligibility =
    eligibility != null && eligibility !== "" && eligibility !== "ELIGIBLE" && !ineligible;

  return (
    <article
      className="imp-opportunity-card"
      data-presentation={presentation}
      data-stable-key={stableOpportunityKey(row)}
      data-testid="imp-opportunity-card"
    >
      <header className="imp-opportunity-card-head">
        <div className="imp-opportunity-card-state-row">
          <StatePill
            tone={OPPORTUNITY_STATE_TONE[presentation]}
            label={OPPORTUNITY_STATE_LABEL[presentation]}
            raw={presentation}
            size="sm"
          />
          {ineligible ? (
            <StatePill tone="critical" label="Not eligible" raw={row.eligibility_state ?? "STOP"} size="sm" />
          ) : showEligibility ? (
            <StatePill tone="neutral" label={humanizeEnum(eligibility)} raw={eligibility} size="sm" />
          ) : null}
          {row.identity_kind === "OPPORTUNITY_V1" ? (
            <StatePill tone="research" label="OpportunityV1" raw={row.identity_kind} size="sm" />
          ) : null}
        </div>
        <h3 className="imp-opportunity-card-title">{row.headline}</h3>
        <p className="imp-opportunity-card-identity">
          <code>{opportunitySymbol(row)}</code>
          {rank ? ` · Rank ${rank}` : ""}
        </p>
      </header>

      {hasProvisionalOrder(row) ? (
        <AttentionBanner tone="caution">
          Provisional order — not FTEP-tuned or campaign-calibrated.
        </AttentionBanner>
      ) : null}
      {ineligible ? (
        <AttentionBanner tone="critical">
          Eligibility gate failed. Do not act on this opportunity.
        </AttentionBanner>
      ) : null}

      <dl className="imp-opportunity-card-meta">
        <div>
          <dt>Evidence</dt>
          <dd>{evidenceInputsSummary(row)}</dd>
        </div>
        <div>
          <dt>Freshness</dt>
          <dd>
            <FreshnessIndicator backendLabel={freshness == null ? null : String(freshness)} />
          </dd>
        </div>
        <div>
          <dt>Next action</dt>
          <dd>
            <StatePill tone={nextAction.tone} label={nextAction.label} raw={nextAction.raw} size="sm" />
          </dd>
        </div>
      </dl>

      <div className="imp-opportunity-card-actions">
        {canOpen ? (
          <button type="button" onClick={() => onOpenWorkspace(attention)}>
            Open workspace
          </button>
        ) : null}
        <button type="button" onClick={() => onExplain(attention)}>
          Explain
        </button>
        <button type="button" onClick={() => onInspect(attention)}>
          Inspect
        </button>
        {canAck ? (
          <>
            <button type="button" onClick={() => onAck?.(row, "watch")}>
              Watch
            </button>
            <button type="button" onClick={() => onAck?.(row, "review")}>
              Mark reviewed
            </button>
            <button type="button" onClick={() => onAck?.(row, "dismiss")}>
              Dismiss
            </button>
          </>
        ) : null}
        {readOnly ? <span className="imp-opportunity-muted">Read-only in this mode.</span> : null}
      </div>
      <p className="imp-opportunity-muted imp-opportunity-visibility-note">
        Visibility is not actionability. Presentation state does not grant execution authority.
      </p>
    </article>
  );
}
