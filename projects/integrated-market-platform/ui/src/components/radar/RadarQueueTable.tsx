import type { AttentionItem } from "../../api/client";
import type {
  OpportunityAckAction,
  OpportunityEvidenceResponse,
  OpportunityReviewRow,
} from "../../api/opportunityClient";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import { StatePill } from "../imp-ui/StatePill";
import {
  buildOpportunityQueuePrimary,
  opportunityFreshnessQueueLabel,
  type OperatorBriefFeedContext,
} from "../opportunity/opportunityOperatorBrief";
import { OperatorActionButton } from "../operator-action/OperatorActionButton";
import {
  attentionItemFromOpportunity,
  derivePresentationState,
  evidenceInputsSummary,
  OPPORTUNITY_STATE_LABEL,
  OPPORTUNITY_STATE_TONE,
  opportunityRankLabel,
  opportunitySymbol,
  stableOpportunityKey,
} from "../opportunity/opportunityPresentation";
import { radarOpportunityActions } from "./radarOperatorActions";

type Props = {
  items: OpportunityReviewRow[];
  selectedStableKey?: string | null;
  /** Evidence projection for the selected row only — enriches that row's scan. */
  selectedEvidence?: OpportunityEvidenceResponse | null;
  feed?: OperatorBriefFeedContext | null;
  readOnly?: boolean;
  paperActions?: boolean;
  /** Paper account present — ack buttons require this + paperActions + !readOnly. */
  paperAccountId?: string;
  onSelectRow?: (row: OpportunityReviewRow) => void;
  onExplain?: (item: AttentionItem) => void;
  onInspect?: (item: AttentionItem) => void;
  onOpenWorkspace?: (item: AttentionItem) => void;
  onAck?: (row: OpportunityReviewRow, action: OpportunityAckAction) => void;
  /** Stable key of the row whose ack is in flight, if any. */
  pendingAckKey?: string | null;
};

function truncate(text: string, max = 72): string {
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max - 1)}…`;
}

/**
 * Opportunity-first ranked queue. L1 columns answer why-now / freshness /
 * evidence / blockers at a glance. Full operator brief (9 questions) lives on
 * the selected detail card. Watch/Dismiss call existing ack APIs only when
 * paper-gated — never synthetic frontend opportunity state.
 */
export function RadarQueueTable({
  items,
  selectedStableKey = null,
  selectedEvidence = null,
  feed = null,
  readOnly = false,
  paperActions = false,
  paperAccountId,
  onSelectRow,
  onExplain,
  onInspect,
  onOpenWorkspace,
  onAck,
  pendingAckKey = null,
}: Props) {
  return (
    <div className="imp-radar-queue-wrap" data-testid="imp-radar-queue">
      <table className="imp-radar-queue-table" aria-label="Ranked opportunity queue">
        <caption className="imp-visually-hidden">
          Ranked opportunity queue. Columns cover why-now, freshness, evidence,
          providers, contradictions, and blocking reasons. Select a row for the
          full operator brief. Watch and Dismiss post to the opportunity ack API
          when paper actions are permitted.
        </caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Symbol</th>
            <th scope="col">Why now</th>
            <th scope="col">Fresh</th>
            <th scope="col">Evidence</th>
            <th scope="col">Blockers</th>
            <th scope="col">
              <span className="imp-visually-hidden">Row actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => {
            const attention = attentionItemFromOpportunity(row);
            const symbol = opportunitySymbol(row);
            const radarActions = radarOpportunityActions({
              row,
              sourceState: "ready",
              readOnly,
              paperActions,
              paperAccountId,
              surface: "queue",
            });
            const rowKey = stableOpportunityKey(row);
            const selected = selectedStableKey === rowKey;
            const presentation = derivePresentationState(row);
            const rowEvidence = selected && selectedEvidence ? selectedEvidence : null;
            const primary = buildOpportunityQueuePrimary(row, rowEvidence, {
              readOnly,
              paperActions,
              feed,
            });
            const freshnessWord = opportunityFreshnessQueueLabel(row, rowEvidence);

            return (
              <tr
                key={row.summary_id}
                data-stable-key={rowKey}
                tabIndex={onSelectRow ? 0 : undefined}
                aria-selected={onSelectRow ? selected : undefined}
                className={selected ? "imp-radar-row-selected" : undefined}
                onClick={onSelectRow ? () => onSelectRow(row) : undefined}
                onKeyDown={
                  onSelectRow
                    ? (event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          onSelectRow(row);
                        }
                      }
                    : undefined
                }
              >
                <td>{opportunityRankLabel(row) ?? "—"}</td>
                <td>
                  <code>{opportunitySymbol(row)}</code>
                  <div className="imp-radar-queue-state">
                    <StatePill
                      tone={OPPORTUNITY_STATE_TONE[presentation]}
                      label={OPPORTUNITY_STATE_LABEL[presentation]}
                      raw={presentation}
                      size="sm"
                    />
                  </div>
                </td>
                <td className="imp-radar-queue-why">
                  <p className="imp-radar-queue-headline">{truncate(row.headline)}</p>
                  <p className="imp-radar-muted imp-radar-queue-rank-basis">
                    Ranked on {primary.rankingBasis}
                  </p>
                  <dl
                    className="imp-radar-queue-scan"
                    data-testid="imp-radar-queue-scan"
                    aria-label={`Why-now scan for ${opportunitySymbol(row)}`}
                  >
                    <div className="imp-radar-queue-scan-row" data-honesty={primary.whyNow.honesty}>
                      <dt>Inference vs observation?</dt>
                      <dd>
                        {truncate(primary.whyNow.answer, 140)}
                        <span className="imp-radar-brief-honesty">{primary.whyNow.honesty}</span>
                      </dd>
                    </div>
                  </dl>
                </td>
                <td>
                  <FreshnessIndicator backendLabel={freshnessWord} />
                  <p className="imp-radar-queue-fresh-detail" title={primary.freshness.answer}>
                    {truncate(primary.freshness.answer, 96)}
                  </p>
                  <span className="imp-radar-brief-honesty">{primary.freshness.honesty}</span>
                </td>
                <td>
                  <strong>{evidenceInputsSummary(row)}</strong>
                  <p className="imp-radar-muted" title={primary.providers.answer}>
                    {primary.providers.answer.startsWith("UNKNOWN")
                      ? "Providers unknown"
                      : truncate(primary.providers.answer, 64)}
                  </p>
                  {primary.hasContradiction ? (
                    <p className="imp-radar-queue-conflict" data-honesty={primary.conflict.honesty}>
                      Conflict: {truncate(primary.conflict.answer, 80)}
                      <span className="imp-radar-brief-honesty">{primary.conflict.honesty}</span>
                    </p>
                  ) : (
                    <p
                      className="imp-radar-muted"
                      data-honesty={primary.conflict.honesty}
                      title={primary.conflict.answer}
                    >
                      {truncate(primary.conflict.answer, 96)}
                      <span className="imp-radar-brief-honesty">{primary.conflict.honesty}</span>
                    </p>
                  )}
                </td>
                <td className="imp-radar-queue-blockers">
                  <p title={primary.refusal.answer}>{primary.refusal.answer}</p>
                  <span className="imp-radar-brief-honesty">{primary.refusal.honesty}</span>
                </td>
                <td className="imp-radar-queue-actions">
                  <span
                    className="imp-radar-queue-action"
                    onClick={(event) => event.stopPropagation()}
                    onKeyDown={(event) => event.stopPropagation()}
                  >
                    <OperatorActionButton
                      action={radarActions.watch}
                      accessibleName={`Watch ${symbol}`}
                      pending={pendingAckKey === rowKey}
                      buttonClassName="imp-radar-ack-watch"
                      onActivate={() => onAck?.(row, "watch")}
                    />
                    <OperatorActionButton
                      action={radarActions.review}
                      accessibleName={`Review ${symbol}`}
                      pending={pendingAckKey === rowKey}
                      onActivate={() => onAck?.(row, "review")}
                    />
                    <OperatorActionButton
                      action={radarActions.dismiss}
                      accessibleName={`Dismiss ${symbol}`}
                      pending={pendingAckKey === rowKey}
                      buttonClassName="imp-radar-ack-dismiss"
                      onActivate={() => onAck?.(row, "dismiss")}
                    />
                    <OperatorActionButton
                      action={radarActions.openWorkspace}
                      accessibleName={`Open workspace for ${symbol}`}
                      onActivate={() => onOpenWorkspace?.(attention)}
                    />
                  </span>
                  {onExplain ? (
                    <button
                      type="button"
                      aria-label={`Explain ${opportunitySymbol(row)}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onExplain(attention);
                      }}
                    >
                      Explain
                    </button>
                  ) : null}
                  {onInspect ? (
                    <button
                      type="button"
                      aria-label={`Inspect ${opportunitySymbol(row)}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onInspect(attention);
                      }}
                    >
                      Inspect
                    </button>
                  ) : null}
                  {readOnly ? <span className="imp-radar-muted">Read-only</span> : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
