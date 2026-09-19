import type { AttentionItem } from "../../api/client";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { StatePill } from "../imp-ui/StatePill";
import { buildOpportunityQueueScan } from "../opportunity/opportunityOperatorBrief";
import {
  attentionItemFromOpportunity,
  canOpenOpportunityWorkspace,
  derivePresentationState,
  evidenceInputsSummary,
  OPPORTUNITY_STATE_LABEL,
  OPPORTUNITY_STATE_TONE,
  opportunityRankLabel,
  opportunitySymbol,
  stableOpportunityKey,
} from "../opportunity/opportunityPresentation";

type Props = {
  items: OpportunityReviewRow[];
  selectedStableKey?: string | null;
  readOnly?: boolean;
  paperActions?: boolean;
  onSelectRow?: (row: OpportunityReviewRow) => void;
  onExplain?: (item: AttentionItem) => void;
  onInspect?: (item: AttentionItem) => void;
  onOpenWorkspace?: (item: AttentionItem) => void;
};

/**
 * Ranked queue scan. Each row answers operator questions without opening
 * details: what happened vs inferred, freshness, providers, conflicts,
 * unknowns, invalidation, and why action may be refused. next_safe_action is
 * a research-gate token inside refusal — not a trade CTA column.
 */
export function RadarQueueTable({
  items,
  selectedStableKey = null,
  readOnly = false,
  paperActions = false,
  onSelectRow,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: Props) {
  return (
    <div className="imp-radar-queue-wrap" data-testid="imp-radar-queue">
      <table className="imp-radar-queue-table">
        <caption className="imp-visually-hidden">
          Ranked opportunity queue. Provenance scan answers what happened versus
          inferred, freshness, providers, conflicts, unknowns, invalidation, and
          refusal. Select a row for the full operator brief.
        </caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Symbol</th>
            <th scope="col">State</th>
            <th scope="col">Evidence</th>
            <th scope="col">Provenance scan</th>
            <th scope="col">
              <span className="imp-visually-hidden">Row actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => {
            const attention = attentionItemFromOpportunity(row);
            const canOpen = canOpenOpportunityWorkspace(row);
            const rowKey = stableOpportunityKey(row);
            const selected = selectedStableKey === rowKey;
            const presentation = derivePresentationState(row);
            const scan = buildOpportunityQueueScan(row, null, { readOnly, paperActions });
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
                </td>
                <td>
                  <StatePill
                    tone={OPPORTUNITY_STATE_TONE[presentation]}
                    label={OPPORTUNITY_STATE_LABEL[presentation]}
                    raw={presentation}
                    size="sm"
                  />
                </td>
                <td>{evidenceInputsSummary(row)}</td>
                <td>
                  <dl
                    className="imp-radar-queue-scan"
                    data-testid="imp-radar-queue-scan"
                    aria-label={`Provenance scan for ${opportunitySymbol(row)}`}
                  >
                    {scan.map((item) => (
                      <div
                        key={item.question}
                        className="imp-radar-queue-scan-row"
                        data-honesty={item.honesty}
                      >
                        <dt>{item.question}</dt>
                        <dd>
                          {item.answer}
                          <span className="imp-radar-brief-honesty">{item.honesty}</span>
                        </dd>
                      </div>
                    ))}
                  </dl>
                </td>
                <td className="imp-radar-queue-actions">
                  {onExplain ? (
                    <button
                      type="button"
                      aria-label={`Explain ${opportunitySymbol(row)}`}
                      onClick={() => onExplain(attention)}
                    >
                      Explain
                    </button>
                  ) : null}
                  {onInspect ? (
                    <button
                      type="button"
                      aria-label={`Inspect ${opportunitySymbol(row)}`}
                      onClick={() => onInspect(attention)}
                    >
                      Inspect
                    </button>
                  ) : null}
                  {canOpen && onOpenWorkspace ? (
                    <button
                      type="button"
                      aria-label={`Open workspace for ${opportunitySymbol(row)}`}
                      onClick={() => onOpenWorkspace(attention)}
                    >
                      Workspace
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
