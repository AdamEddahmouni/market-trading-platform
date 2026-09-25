import { useMemo, useState } from "react";
import type { PaperPortfolioResponse } from "../../api/client";
import { useCancelPaperOrderMutation, usePaperOrderHistoryInfiniteQuery } from "../../api/hooks";
import { LoadingState } from "../shared/LoadingState";
import {
  buildPaperOrderHistoryFromPortfolio,
  buildPaperOrderHistoryRows,
  DEFAULT_PAPER_ORDER_HISTORY_FILTERS,
  type PaperOrderHistoryFilters,
  type PaperOrderHistoryRow,
} from "./paperOrderHistoryModel";
import { PORTFOLIO_SECTIONS } from "./paperPortfolioPresentation";
import { PaperOrderHistoryTable } from "./PaperOrderHistoryTable";

type Props = {
  data: PaperPortfolioResponse;
  onViewTrace?: (intentId?: string, orderId?: string) => void;
  /**
   * True only when the backend reports Paper execution authority for this
   * account. Cancel is a backend-authoritative mutation: the UI offers it only
   * when the operator is actually permitted to attempt it.
   */
  canCancelOrders?: boolean;
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

export function PaperOrderHistory({ data, onViewTrace, canCancelOrders = false }: Props) {
  const [filters, setFilters] = useState<PaperOrderHistoryFilters>(DEFAULT_PAPER_ORDER_HISTORY_FILTERS);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const portfolioModel = useMemo(() => buildPaperOrderHistoryFromPortfolio(data), [data]);
  const historyQuery = usePaperOrderHistoryInfiniteQuery();
  const cancelOrder = useCancelPaperOrderMutation();

  function cancelWorkingOrder(order: PaperOrderHistoryRow) {
    if (!order.orderId) return;
    setCancelError(null);
    void cancelOrder
      .mutateAsync(order.orderId)
      .catch((error: unknown) => {
        setCancelError(
          error instanceof Error && error.message
            ? `Cancel rejected: ${error.message}`
            : "Cancel rejected by the Paper ledger. The order is unchanged.",
        );
      });
  }

  const cancelHandlers = {
    onCancel: canCancelOrders ? cancelWorkingOrder : undefined,
    canCancel: canCancelOrders,
    cancelPending: cancelOrder.isPending,
    cancelError,
  };

  const paginatedHistoryRows = useMemo(() => {
    if (!historyQuery.data?.pages.length) return [];
    const orders = historyQuery.data.pages.flatMap((page) => page.orders);
    const fills = historyQuery.data.pages.flatMap((page) => page.fills);
    return dedupeHistoryRows(buildPaperOrderHistoryRows(orders, fills).filter((row) => !row.isOpen));
  }, [historyQuery.data?.pages]);

  const totalTerminalCount = historyQuery.data?.pages[0]?.total_count ?? paginatedHistoryRows.length;
  const historyEmptyMessage =
    totalTerminalCount === 0 && !historyQuery.isLoading
      ? "No simulated orders yet. Decisions submitted from Paper Workspace or Paper Command will appear here."
      : "No completed simulated orders match the current filters.";

  return (
    <div className="paper-order-history-stack">
      {portfolioModel.openOrders.length > 0 ? (
        <PaperOrderHistoryTable
          title="Working orders"
          sectionId={PORTFOLIO_SECTIONS.openOrders}
          rows={portfolioModel.openOrders}
          emptyMessage="No working simulated orders."
          onViewTrace={onViewTrace}
          {...cancelHandlers}
        />
      ) : null}

      {historyQuery.isLoading ? (
        <section
          className="panel paper-order-history-panel"
          id={PORTFOLIO_SECTIONS.orderHistory}
        >
          <h2>Order history</h2>
          <LoadingState label="Loading order history…" />
        </section>
      ) : null}

      {historyQuery.isError ? (
        <section
          className="panel paper-order-history-panel unavailable"
          id={PORTFOLIO_SECTIONS.orderHistory}
        >
          <h2>Order history</h2>
          <p>Order history is temporarily unavailable. Open orders and account summary remain current.</p>
        </section>
      ) : null}

      {!historyQuery.isLoading && !historyQuery.isError ? (
        <PaperOrderHistoryTable
          title="Order history"
          sectionId={PORTFOLIO_SECTIONS.orderHistory}
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
