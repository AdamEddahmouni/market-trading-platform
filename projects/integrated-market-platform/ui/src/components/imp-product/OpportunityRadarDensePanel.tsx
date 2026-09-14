import type { AttentionItem } from "../../api/client";
import { useOpportunitiesSummaryQuery } from "../../api/opportunityClient";
import { opportunityRankLabel, opportunitySymbol, opportunityTags } from "./impOpportunityDisplay";
import { attentionItemFromOpportunity } from "../now/OpportunityReviewCard";

type Props = {
  readOnly?: boolean;
  onExplain?: (item: AttentionItem) => void;
  onInspect?: (item: AttentionItem) => void;
  onOpenWorkspace?: (item: AttentionItem) => void;
};

export function OpportunityRadarDensePanel({
  readOnly = false,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: Props) {
  const query = useOpportunitiesSummaryQuery(true);
  const state = query.isLoading ? "loading" : query.isError || !query.data ? "error" : "ready";
  const items = query.data?.items ?? [];

  return (
    <section className="imp-radar-dense-panel" aria-labelledby="imp-radar-dense-title">
      <header className="imp-radar-dense-header">
        <div>
          <p className="imp-section-eyebrow">Ranked queue</p>
          <h2 id="imp-radar-dense-title">Opportunity review density</h2>
        </div>
        {query.data?.feed_status ? (
          <span className="imp-radar-dense-feed" data-status={query.data.feed_status}>
            Feed {query.data.feed_status}
          </span>
        ) : null}
      </header>
      {state === "loading" ? <p role="status">Loading opportunity queue…</p> : null}
      {state === "error" ? <p className="unavailable" role="alert">Opportunity queue unavailable.</p> : null}
      {state === "ready" && query.data?.feed_status === "UNREADY" ? (
        <p className="unavailable" role="status">
          Queue unready{query.data.unready_reason ? ` (${query.data.unready_reason})` : ""}.
        </p>
      ) : null}
      {state === "ready" && query.data?.feed_status !== "UNREADY" && !items.length ? (
        <p className="unavailable">No candidates in the ranked queue.</p>
      ) : null}
      {state === "ready" && query.data?.feed_status !== "UNREADY" && items.length ? (
        <div className="imp-radar-dense-table-wrap">
          <table className="imp-radar-dense-table">
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Symbol</th>
                <th scope="col">Headline</th>
                <th scope="col">Signals</th>
                <th scope="col">Next</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const attention = attentionItemFromOpportunity(row);
                const ineligible = row.eligibility_state === "INELIGIBLE" || row.next_safe_action === "STOP";
                const canOpen = Boolean(
                  row.instrument_id && row.next_safe_action === "OPEN_WORKSPACE" && !ineligible,
                );
                const tags = opportunityTags(row, 4);
                return (
                  <tr key={row.summary_id}>
                    <td>{opportunityRankLabel(row) ?? "—"}</td>
                    <td><code>{opportunitySymbol(row)}</code></td>
                    <td className="imp-radar-dense-headline">{row.headline}</td>
                    <td>
                      {tags.length ? (
                        <ul className="imp-top-opportunity-tags imp-radar-dense-tags">
                          {tags.map((tag) => (
                            <li key={tag}>{tag}</li>
                          ))}
                        </ul>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>{ineligible ? "STOP" : row.next_safe_action ?? "—"}</td>
                    <td className="imp-radar-dense-actions">
                      {onExplain ? (
                        <button type="button" onClick={() => onExplain(attention)}>Explain</button>
                      ) : null}
                      {onInspect ? (
                        <button type="button" onClick={() => onInspect(attention)}>Inspect</button>
                      ) : null}
                      {canOpen && onOpenWorkspace ? (
                        <button type="button" onClick={() => onOpenWorkspace(attention)}>Workspace</button>
                      ) : null}
                      {readOnly ? <span className="muted">Read-only</span> : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
