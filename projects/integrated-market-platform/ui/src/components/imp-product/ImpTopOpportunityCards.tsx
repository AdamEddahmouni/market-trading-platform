import { Link } from "react-router-dom";
import type { AttentionItem } from "../../api/client";
import type { OpportunityReviewRow } from "../../api/opportunityClient";
import { attentionItemFromOpportunity } from "../now/OpportunityReviewCard";
import { opportunityRankLabel, opportunitySymbol, opportunityTags } from "./impOpportunityDisplay";

export type ImpTopOpportunityCardsProps = {
  items: OpportunityReviewRow[];
  state: "loading" | "ready" | "error";
  feedStatus?: string;
  unreadyReason?: string;
  nextAction?: string;
  discoverPath?: string;
  maxCards?: number;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
};

function CompactOpportunityCard({
  row,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: {
  row: OpportunityReviewRow;
  onExplain: (item: AttentionItem) => void;
  onInspect: (item: AttentionItem) => void;
  onOpenWorkspace: (item: AttentionItem) => void;
}) {
  const attention = attentionItemFromOpportunity(row);
  const ineligible = row.eligibility_state === "INELIGIBLE" || row.next_safe_action === "STOP";
  const canOpen = Boolean(row.instrument_id && row.next_safe_action === "OPEN_WORKSPACE" && !ineligible);
  const rank = opportunityRankLabel(row);
  const tags = opportunityTags(row);

  return (
    <article className="imp-top-opportunity-card">
      <header className="imp-top-opportunity-card-head">
        <div>
          {rank ? <span className="imp-top-opportunity-rank">{rank}</span> : null}
          <code className="imp-top-opportunity-symbol">{opportunitySymbol(row)}</code>
        </div>
        {row.eligibility_state ? (
          <span className={`imp-top-opportunity-chip ${ineligible ? "chip-stop" : "chip-ok"}`}>
            {ineligible ? "Ineligible" : row.eligibility_state}
          </span>
        ) : null}
      </header>
      <p className="imp-top-opportunity-headline">{row.headline}</p>
      {tags.length ? (
        <ul className="imp-top-opportunity-tags" aria-label="Ranking dimensions">
          {tags.map((tag) => (
            <li key={tag}>{tag}</li>
          ))}
        </ul>
      ) : (
        <p className="imp-top-opportunity-tags imp-top-opportunity-tags-empty">No ranked dimensions</p>
      )}
      <div className="imp-top-opportunity-actions">
        <button type="button" onClick={() => onExplain(attention)}>Explain</button>
        <button type="button" onClick={() => onInspect(attention)}>Inspect</button>
        {canOpen ? (
          <button type="button" onClick={() => onOpenWorkspace(attention)}>Workspace</button>
        ) : null}
      </div>
    </article>
  );
}

export function ImpTopOpportunityCards({
  items,
  state,
  feedStatus,
  unreadyReason,
  nextAction,
  discoverPath = "/discover",
  maxCards = 4,
  onExplain,
  onInspect,
  onOpenWorkspace,
}: ImpTopOpportunityCardsProps) {
  const visible = items.slice(0, maxCards);

  return (
    <section className="imp-top-opportunities" aria-labelledby="imp-top-opportunities-title">
      <header className="imp-top-opportunities-header">
        <div>
          <p className="imp-section-eyebrow">Opportunity Radar</p>
          <h2 id="imp-top-opportunities-title">Top opportunities</h2>
        </div>
        <Link className="imp-top-opportunities-link" to={discoverPath}>
          Open full radar
        </Link>
      </header>
      {state === "loading" ? <p role="status">Loading ranked opportunities…</p> : null}
      {state === "error" ? (
        <p className="unavailable" role="alert">Opportunity ranking unavailable.</p>
      ) : null}
      {state === "ready" && feedStatus === "UNREADY" ? (
        <p className="unavailable" role="status">
          Radar unready{unreadyReason ? ` (${unreadyReason})` : ""}.{" "}
          <a href={nextAction || "/control"}>Open Control Center</a>
        </p>
      ) : null}
      {state === "ready" && feedStatus !== "UNREADY" && !visible.length ? (
        <p className="unavailable">
          No ranked candidates yet. An empty queue is valid when nothing has been minted.
        </p>
      ) : null}
      {state === "ready" && feedStatus !== "UNREADY" && visible.length ? (
        <div className="imp-top-opportunity-grid">
          {visible.map((row) => (
            <CompactOpportunityCard
              key={row.summary_id}
              row={row}
              onExplain={onExplain}
              onInspect={onInspect}
              onOpenWorkspace={onOpenWorkspace}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
