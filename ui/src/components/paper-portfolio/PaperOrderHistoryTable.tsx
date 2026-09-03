import { useMemo, useState } from "react";
import {
  DEFAULT_PAPER_ORDER_HISTORY_FILTERS,
  filterPaperOrderHistoryRows,
  type PaperOrderHistoryFilters,
  type PaperOrderHistoryRow,
} from "./paperOrderHistoryModel";
import { PaperOrderHistoryRowView } from "./PaperOrderHistoryRow";

type Props = {
  title: string;
  rows: PaperOrderHistoryRow[];
  emptyMessage: string;
  onViewTrace?: (intentId?: string, orderId?: string) => void;
  showFilters?: boolean;
  filters?: PaperOrderHistoryFilters;
  onFiltersChange?: (filters: PaperOrderHistoryFilters) => void;
  pagination?: {
    loadedCount: number;
    totalCount: number;
    hasMore: boolean;
    loadingMore: boolean;
    onLoadMore: () => void;
  };
};

export function PaperOrderHistoryTable({
  title,
  rows,
  emptyMessage,
  onViewTrace,
  showFilters = false,
  filters = DEFAULT_PAPER_ORDER_HISTORY_FILTERS,
  onFiltersChange,
  pagination,
}: Props) {
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const visibleRows = useMemo(
    () => (showFilters ? filterPaperOrderHistoryRows(rows, filters) : rows),
    [filters, rows, showFilters],
  );

  return (
    <section className="panel paper-order-history-panel">
      <div className="paper-order-history-header">
        <h2>{title}</h2>
        {showFilters && onFiltersChange ? (
          <div className="paper-order-history-filters" aria-label="Order history filters">
            <label>
              Status
              <select
                value={filters.status}
                onChange={(event) =>
                  onFiltersChange({
                    ...filters,
                    status: event.target.value as PaperOrderHistoryFilters["status"],
                  })
                }
              >
                <option value="ALL">All statuses</option>
                <option value="OPEN">Open</option>
                <option value="FILLED">Filled</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </label>
            <label>
              Source
              <select
                value={filters.source}
                onChange={(event) =>
                  onFiltersChange({
                    ...filters,
                    source: event.target.value as PaperOrderHistoryFilters["source"],
                  })
                }
              >
                <option value="ALL">All sources</option>
                <option value="PAPER_COMMAND">Paper Command</option>
                <option value="WORKSPACE_LANE">Workspace lane</option>
                <option value="MANUAL">Manual</option>
                <option value="UNKNOWN">Unknown</option>
              </select>
            </label>
            <label>
              Symbol
              <input
                type="search"
                value={filters.symbolQuery}
                placeholder="Search symbol"
                onChange={(event) => onFiltersChange({ ...filters, symbolQuery: event.target.value })}
              />
            </label>
          </div>
        ) : null}
      </div>

      {visibleRows.length === 0 ? (
        <p className="muted">{emptyMessage}</p>
      ) : (
        <div className="paper-order-table-wrap">
          <table className="data-table paper-order-history-table">
            <thead>
              <tr>
                <th scope="col">Time</th>
                <th scope="col">Symbol</th>
                <th scope="col">Side</th>
                <th scope="col">Qty</th>
                <th scope="col" className="paper-order-col-type">
                  Type
                </th>
                <th scope="col">Status</th>
                <th scope="col" className="paper-order-col-fill">
                  Fill
                </th>
                <th scope="col">Decision source</th>
                <th scope="col" className="paper-order-col-detail">
                  Source detail
                </th>
                <th scope="col">Trace</th>
                <th scope="col">
                  <span className="sr-only">Details</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <PaperOrderHistoryRowView
                  key={row.rowId}
                  row={row}
                  expanded={expandedRowId === row.rowId}
                  onToggle={() => setExpandedRowId((current) => (current === row.rowId ? null : row.rowId))}
                  onViewTrace={onViewTrace}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {pagination ? (
        <div className="paper-order-history-pagination">
          <p className="muted" role="status">
            Showing {visibleRows.length} of {pagination.totalCount} completed order
            {pagination.totalCount === 1 ? "" : "s"}
          </p>
          {pagination.hasMore ? (
            <button type="button" onClick={pagination.onLoadMore} disabled={pagination.loadingMore}>
              {pagination.loadingMore ? "Loading more…" : "Load more history"}
            </button>
          ) : pagination.totalCount > 0 ? (
            <p className="muted">End of history</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
