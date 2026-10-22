import type { TradeLifecycle, TradeLifecycleList } from "../../../api/screenerLifecycle";
import LifecycleCard from "./LifecycleCard";
import { codeText, marketDataLabel, money } from "./lifecyclePresentation";

function Group({ title, note, rows, total, runId, testId }: { title: string; note: string; rows: TradeLifecycle[]; total: number; runId: string | null; testId: string }) {
  if (!rows.length) return null;
  return <section className="lifecycle-group" aria-label={title} data-testid={testId}>
    <h3 className="lifecycle-group-title">{title} <span className="lifecycle-meta">· {rows.length}{total > rows.length ? ` of ${total}` : ""}</span></h3>
    <p className="lifecycle-meta">{note}</p>
    {rows.map((row) => <LifecycleCard key={row.lifecycle_id} lifecycle={row} runId={runId} />)}
  </section>;
}

/** The data/execution boundary, stated once: market data may be live; execution here is always simulated. */
export function LifecycleBoundary({ list }: { list: TradeLifecycleList }) {
  const experiment = list.experiment;
  return <div className="lifecycle-boundary" data-testid="lifecycle-boundary">
    <p><span>Market data: <strong>{marketDataLabel(list.market_data)}</strong></span> · <span>Execution: <strong>SIMULATED PAPER</strong></span>
      {experiment && <> · Paper experiment equity {money(experiment.equity_minor, list.currency)} · cash {money(experiment.cash_minor, list.currency)}</>}</p>
    {list.limitations.length > 0 && <p role="status">{list.limitations.map(codeText).join("; ")}</p>}
  </div>;
}

/**
 * Lifecycles that do not depend on the newest candidate list: positions opened
 * from earlier runs, Paper activity with no AI lineage, and recent closed episodes.
 */
export default function TradeLifecycleGroups({ list, runId }: { list: TradeLifecycleList; runId: string | null }) {
  return <>
    <Group title="Active managed positions" testId="lifecycle-active-managed" rows={list.active_managed} total={list.counts.active_managed} runId={runId}
      note="Open Paper positions that the latest AI Screener run did not select. They stay here until a simulated close fill." />
    <Group title="Unlinked Paper activity" testId="lifecycle-unlinked" rows={list.unlinked} total={list.counts.unlinked} runId={runId}
      note="Paper positions with no recorded AI candidate or decision. Shown for completeness; not AI-selected." />
    <Group title="Recent closed episodes" testId="lifecycle-recent-closed" rows={list.recent_closed} total={list.counts.recent_closed} runId={runId}
      note="Each closed episode shows its own entry, exit and realized Paper P&L. One outcome says nothing about decision quality." />
  </>;
}
