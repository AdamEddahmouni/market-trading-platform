import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  DEFAULT_PAPER_ORDER_HISTORY_FILTERS,
  filterPaperOrderHistoryRows,
  type PaperOrderHistoryFilters,
  type PaperOrderHistoryRow,
} from "./paperOrderHistoryModel";
import { PaperDecisionProvenanceBadge } from "./PaperDecisionProvenanceBadge";
import { PaperOrderHistoryRowView } from "./PaperOrderHistoryRow";
import { paperOrderStatusLabel, paperOrderStatusTone } from "./paperOrderStatusPresentation";

type Props = {
  title: string;
  rows: PaperOrderHistoryRow[];
  emptyMessage: string;
  /** Stable section id for in-page handoffs (e.g. Fills → Order history). */
  sectionId?: string;
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
  /** Present only when the backend cancel contract is available to the operator. */
  onCancel?: (order: PaperOrderHistoryRow) => void;
  canCancel?: boolean;
  cancelPending?: boolean;
  cancelError?: string | null;
};

export function PaperOrderHistoryTable({
  title,
  rows,
  emptyMessage,
  sectionId,
  onViewTrace,
  showFilters = false,
  filters = DEFAULT_PAPER_ORDER_HISTORY_FILTERS,
  onFiltersChange,
  pagination,
  onCancel,
  canCancel = false,
  cancelPending = false,
  cancelError = null,
}: Props) {
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const nowMs = Date.now();
  const visibleRows = useMemo(
    () => (showFilters ? filterPaperOrderHistoryRows(rows, filters) : rows),
    [filters, rows, showFilters],
  );
  const selected = useMemo(
    () => visibleRows.find((row) => row.rowId === selectedRowId) ?? null,
    [selectedRowId, visibleRows],
  );

  return (
    <section className="panel paper-order-history-panel" id={sectionId}>
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
                <option value="WATCHED_OPPORTUNITY">Radar watched opportunity</option>
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

      {cancelError ? (
        <p className="portfolio-inline-error" role="alert">
          {cancelError}
        </p>
      ) : null}

      {visibleRows.length === 0 ? (
        <p className="muted">{emptyMessage}</p>
      ) : (
        <>
          <div className="paper-order-table-wrap">
            <table className="data-table paper-order-history-table portfolio-table">
              <caption className="imp-visually-hidden">{title}</caption>
              <thead>
                <tr>
                  <th scope="col" className="portfolio-col-instrument">
                    Instrument
                  </th>
                  <th scope="col" className="portfolio-col-num">
                    Qty
                  </th>
                  <th scope="col" className="portfolio-col-num">
                    Filled
                  </th>
                  <th scope="col" className="portfolio-col-num">
                    Price
                  </th>
                  <th scope="col" className="portfolio-col-type">
                    Type
                  </th>
                  <th scope="col">Status</th>
                  <th scope="col" className="portfolio-col-num">
                    Age
                  </th>
                  <th scope="col" className="portfolio-col-actions">
                    <span className="imp-visually-hidden">Actions</span>
                  </th>
                  <th scope="col" className="portfolio-col-actions">
                    <span className="imp-visually-hidden">Details</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => (
                  <PaperOrderHistoryRowView
                    key={row.rowId}
                    row={row}
                    nowMs={nowMs}
                    selected={row.rowId === selectedRowId}
                    onSelect={() =>
                      setSelectedRowId((current) => (current === row.rowId ? null : row.rowId))
                    }
                    expanded={expandedRowId === row.rowId}
                    onToggleDetails={() =>
                      setExpandedRowId((current) => (current === row.rowId ? null : row.rowId))
                    }
                    onCancel={onCancel}
                    canCancel={canCancel}
                    cancelPending={cancelPending}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {selected ? (
            <div
              className="portfolio-selection"
              data-testid={`paper-order-selection-${selected.rowId}`}
              aria-label={`${selected.symbol} order context`}
            >
              <div className="portfolio-selection-head">
                <p className="portfolio-selection-summary">
                  <span className="portfolio-instrument-link">{selected.symbol}</span>
                  <span className="portfolio-side-chip" data-side={selected.side.toUpperCase() === "SELL" ? "short" : "long"}>
                    {selected.side}
                  </span>
                  <span className={`paper-order-status paper-order-status--${paperOrderStatusTone(selected.status)}`}>
                    {paperOrderStatusLabel(selected.status)}
                  </span>
                  <span>
                    {selected.quantity ?? "—"} @ {selected.orderType}
                  </span>
                  <span>{selected.fillSummary}</span>
                </p>
                <div className="portfolio-selection-actions">
                  {selected.workspaceHref ? (
                    <Link className="portfolio-action-primary" to={selected.workspaceHref}>
                      Open Workspace
                    </Link>
                  ) : null}
                  {onViewTrace ? (
                    <button
                      type="button"
                      className="portfolio-action-secondary"
                      onClick={() =>
                        onViewTrace(selected.intentId ?? undefined, selected.orderId ?? undefined)
                      }
                    >
                      View trace
                    </button>
                  ) : null}
                  {onCancel && canCancel && selected.cancelEligible && selected.orderId ? (
                    <button
                      type="button"
                      className="portfolio-action-danger"
                      disabled={cancelPending}
                      onClick={() => onCancel(selected)}
                    >
                      Cancel working order
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="portfolio-action-secondary"
                    onClick={() => setSelectedRowId(null)}
                  >
                    Clear selection
                  </button>
                </div>
              </div>
              <dl className="portfolio-row-detail-grid">
                <div>
                  <dt>Decision source</dt>
                  <dd>
                    <PaperDecisionProvenanceBadge provenance={selected.provenance} />
                  </dd>
                </div>
                <div>
                  <dt>Source detail</dt>
                  <dd>{selected.provenance.tableSourceSummary}</dd>
                </div>
                {selected.workingQuantity !== null ? (
                  <div>
                    <dt>Working remainder</dt>
                    <dd>{selected.workingQuantity} sh</dd>
                  </div>
                ) : null}
                {selected.rejectionReason ? (
                  <div>
                    <dt>Rejection reason</dt>
                    <dd>{selected.rejectionReason}</dd>
                  </div>
                ) : null}
              </dl>
            </div>
          ) : null}
        </>
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
