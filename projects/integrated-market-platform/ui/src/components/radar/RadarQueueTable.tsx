import type { AttentionItem } from "../../api/client";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { StatePill } from "../imp-ui/StatePill";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import {
  collectOpportunityProviderLabels,
  opportunityFreshnessQueueLabel,
} from "../opportunity/opportunityOperatorBrief";
import {
  attentionItemFromOpportunity,
  canOpenOpportunityWorkspace,
  derivePresentationState,
  evidenceInputsSummary,
  OPPORTUNITY_STATE_LABEL,
  OPPORTUNITY_STATE_TONE,
  opportunityNextActionState,
  opportunityRankLabel,
  opportunitySymbol,
  stableOpportunityKey,
} from "../opportunity/opportunityPresentation";

type Props = {
  items: OpportunityReviewRow[];
  selectedStableKey?: string | null;
  readOnly?: boolean;
  onSelectRow?: (row: OpportunityReviewRow) => void;
  onExplain?: (item: AttentionItem) => void;
  onInspect?: (item: AttentionItem) => void;
  onOpenWorkspace?: (item: AttentionItem) => void;
};

/**
 * The ranked opportunity queue. Each row answers without opening details:
 * instrument, what/why-now, state, evidence strength, freshness, attached
 * providers (or UNKNOWN), and next safe action. Rows are keyboard selectable
 * (Enter/Space) with aria-selected.
 */
export function RadarQueueTable({
  items,
  selectedStableKey = null,
  readOnly = false,
  onSelectRow,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: Props) {
  return (
    <div className="imp-radar-queue-wrap" data-testid="imp-radar-queue">
      <table className="imp-radar-queue-table">
        <caption className="imp-visually-hidden">
          Ranked opportunity queue. Select a row to inspect the opportunity.
        </caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Symbol</th>
            <th scope="col">What / why now</th>
            <th scope="col">State</th>
            <th scope="col">Evidence</th>
            <th scope="col">Freshness</th>
            <th scope="col">Providers</th>
            <th scope="col">Next action</th>
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
            const nextAction = opportunityNextActionState(row);
            const freshnessLabel = opportunityFreshnessQueueLabel(row);
            const providers = collectOpportunityProviderLabels(row);
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
                <td className="imp-radar-queue-headline">{row.headline}</td>
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
                  <FreshnessIndicator backendLabel={freshnessLabel} />
                </td>
                <td>{providers.length ? providers.join(", ") : "UNKNOWN"}</td>
                <td>
                  <StatePill
                    tone={nextAction.tone}
                    label={nextAction.label}
                    raw={nextAction.raw}
                    size="sm"
                  />
                </td>
                <td className="imp-radar-queue-actions">
                  {onExplain ? (
                    <button type="button" onClick={() => onExplain(attention)}>
                      Explain
                    </button>
                  ) : null}
                  {onInspect ? (
                    <button type="button" onClick={() => onInspect(attention)}>
                      Inspect
                    </button>
                  ) : null}
                  {canOpen && onOpenWorkspace ? (
                    <button type="button" onClick={() => onOpenWorkspace(attention)}>
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
