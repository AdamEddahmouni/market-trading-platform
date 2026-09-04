import { useMemo, useState } from "react";
import type { PaperPortfolioResponse } from "../../api/client";
import { usePaperOrderHistoryInfiniteQuery } from "../../api/hooks";
import { LoadingState } from "../shared/LoadingState";
import {
  buildPaperOrderHistoryFromPortfolio,
  buildPaperOrderHistoryRows,
  DEFAULT_PAPER_ORDER_HISTORY_FILTERS,
  type PaperOrderHistoryFilters,
  type PaperOrderHistoryRow,
} from "./paperOrderHistoryModel";
import { PaperOrderHistoryTable } from "./PaperOrderHistoryTable";

type Props = {
  data: PaperPortfolioResponse;
  onViewTrace?: (intentId?: string, orderId?: string) => void;
};

function dedupeHistoryRows(rows: PaperOrderHistoryRow[]): PaperOrderHistoryRow[] {
  const seen = new Set<string>();
  const unique: PaperOrderHistoryRow[] = [];
  for (const row of rows) {
    if (seen.has(row.rowId)) continue;
    seen.add(row.rowId);
    unique.push(row);
  }
  return unique;
}

export function PaperOrderHistory({ data, onViewTrace }: Props) {
  const [filters, setFilters] = useState<PaperOrderHistoryFilters>(DEFAULT_PAPER_ORDER_HISTORY_FILTERS);
  const portfolioModel = useMemo(() => buildPaperOrderHistoryFromPortfolio(data), [data]);
  const historyQuery = usePaperOrderHistoryInfiniteQuery();

  const paginatedHistoryRows = useMemo(() => {
    if (!historyQuery.data?.pages.length) return [];
    const orders = historyQuery.data.pages.flatMap((page) => page.orders);
    const fills = historyQuery.data.pages.flatMap((page) => page.fills);
    return dedupeHistoryRows(buildPaperOrderHistoryRows(orders, fills).filter((row) => !row.isOpen));
  }, [historyQuery.data?.pages]);

  const totalTerminalCount = historyQuery.data?.pages[0]?.total_count ?? paginatedHistoryRows.length;
  const metrics = portfolioModel.metrics;
  const historyEmptyMessage =
    totalTerminalCount === 0 && !historyQuery.isLoading
      ? "No simulated orders yet. Decisions submitted from Paper Workspace or Paper Command will appear here."
      : "No completed simulated orders match the current filters.";

  return (
    <div className="paper-order-history-stack">
      <section className="panel paper-order-metrics-panel" aria-label="Paper order summary">
        <h2>Order activity</h2>
        <dl className="metric-list paper-order-metrics-grid">
          <div>
            <dt>Open orders</dt>
            <dd>{metrics.openOrders}</dd>
          </div>
          <div>
            <dt>Filled</dt>
            <dd>{metrics.filled}</dd>
          </div>
          <div>
            <dt>Rejected</dt>
            <dd>{metrics.rejected}</dd>
          </div>
          <div>
            <dt>Paper Command sourced</dt>
            <dd>{metrics.paperCommandSourced}</dd>
          </div>
          <div>
            <dt>Lane sourced</dt>
            <dd>{metrics.laneSourced}</dd>
          </div>
        </dl>
      </section>

      {portfolioModel.openOrders.length > 0 ? (
        <PaperOrderHistoryTable
          title="Open orders"
          rows={portfolioModel.openOrders}
          emptyMessage="No open simulated orders."
          onViewTrace={onViewTrace}
        />
      ) : null}

      {historyQuery.isLoading ? (
        <section className="panel paper-order-history-panel">
          <h2>Order history</h2>
          <LoadingState label="Loading order history…" />
        </section>
      ) : null}

      {historyQuery.isError ? (
        <section className="panel paper-order-history-panel unavailable">
          <h2>Order history</h2>
          <p>Order history is temporarily unavailable. Open orders and account summary remain current.</p>
        </section>
      ) : null}

      {!historyQuery.isLoading && !historyQuery.isError ? (
        <PaperOrderHistoryTable
          title="Order history"
          rows={paginatedHistoryRows}
          emptyMessage={historyEmptyMessage}
          onViewTrace={onViewTrace}
          showFilters={paginatedHistoryRows.length > 0 || totalTerminalCount > 0}
          filters={filters}
          onFiltersChange={setFilters}
          pagination={
            historyQuery.hasNextPage || paginatedHistoryRows.length > 0
              ? {
                  loadedCount: paginatedHistoryRows.length,
                  totalCount: totalTerminalCount,
                  hasMore: Boolean(historyQuery.hasNextPage),
                  loadingMore: historyQuery.isFetchingNextPage,
                  onLoadMore: () => void historyQuery.fetchNextPage(),
                }
              : undefined
          }
        />
      ) : null}
    </div>
  );
}
