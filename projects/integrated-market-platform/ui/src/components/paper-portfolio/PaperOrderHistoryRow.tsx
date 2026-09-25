import { Link } from "react-router-dom";
import { PaperDecisionProvenanceBadge } from "./PaperDecisionProvenanceBadge";
import { PaperPersistedSourceContextPanel } from "./PaperPersistedSourceContextPanel";
import { formatOrderAge, type PaperOrderHistoryRow } from "./paperOrderHistoryModel";
import { paperOrderStatusLabel, paperOrderStatusTone } from "./paperOrderStatusPresentation";

type Props = {
  row: PaperOrderHistoryRow;
  nowMs: number;
  selected: boolean;
  onSelect: () => void;
  expanded: boolean;
  onToggleDetails: () => void;
};

export function PaperOrderHistoryRowDetails({ row }: { row: PaperOrderHistoryRow }) {
  return (
    <div className="paper-order-details">
      <dl className="metric-list paper-order-details-grid">
        <div>
          <dt>Symbol</dt>
          <dd>{row.symbol}</dd>
        </div>
        <div>
          <dt>Side</dt>
          <dd>{row.side}</dd>
        </div>
        <div>
          <dt>Requested quantity</dt>
          <dd>{row.quantity ?? "—"}</dd>
        </div>
        <div>
          <dt>Filled quantity</dt>
          <dd>{row.filledQuantity ?? "—"}</dd>
        </div>
        <div>
          <dt>Order type</dt>
          <dd>{row.orderType}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{row.statusLabel}</dd>
        </div>
        {row.submittedAtLabel ? (
          <div>
            <dt>Submitted</dt>
            <dd>{row.submittedAtLabel}</dd>
          </div>
        ) : null}
        <div>
          <dt>Decision source</dt>
          <dd>
            <PaperDecisionProvenanceBadge provenance={row.provenance} />
          </dd>
        </div>
        <div>
          <dt>Source detail</dt>
          <dd>{row.provenance.sourceDetail}</dd>
        </div>
        {row.clientOrderId ? (
          <div>
            <dt>Client order ID</dt>
            <dd>{row.clientOrderId}</dd>
          </div>
        ) : null}
        {row.orderId ? (
          <div>
            <dt>Paper order ID</dt>
            <dd>{row.orderId}</dd>
          </div>
        ) : null}
        {row.intentId ? (
          <div>
            <dt>Intent ID</dt>
            <dd>{row.intentId}</dd>
          </div>
        ) : null}
        {row.correlationId ? (
          <div>
            <dt>Decision correlation</dt>
            <dd>{row.correlationId}</dd>
          </div>
        ) : null}
        {row.rejectionReason ? (
          <div>
            <dt>Rejection reason</dt>
            <dd>{row.rejectionReason}</dd>
          </div>
        ) : null}
      </dl>
      <PaperPersistedSourceContextPanel persisted={row.provenance.persistedSourceContext} />
      {row.fills.length > 0 ? (
        <div className="paper-order-fill-list">
          <h4>Fills</h4>
          <ul>
            {row.fills.map((fill) => (
              <li key={fill.fillId}>
                {fill.direction} · {fill.quantity} @ {fill.priceMinor} minor
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Rapid order-state comprehension. Instrument and status lead; size, fill, and
 * age are aligned numerals. Provenance and technical identifiers stay in row
 * detail — they answer "why", not "what is working right now".
 */
export function PaperOrderHistoryRowView({
  row,
  nowMs,
  selected,
  onSelect,
  expanded,
  onToggleDetails,
  onCancel,
  canCancel,
  cancelPending,
}: Props & {
  onCancel?: (order: PaperOrderHistoryRow) => void;
  canCancel: boolean;
  cancelPending: boolean;
}) {
  const statusTone = paperOrderStatusTone(row.status);
  const age = formatOrderAge(row, nowMs);
  const cancelLabel = row.symbol !== "—" ? `Cancel working ${row.symbol} order` : "Cancel order";
  const canOfferCancel = Boolean(onCancel) && canCancel && row.cancelEligible && Boolean(row.orderId);

  return (
    <>
      <tr
        className="paper-order-row"
        data-selected={selected ? "true" : "false"}
        aria-selected={selected}
        tabIndex={0}
        onClick={onSelect}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onSelect();
          }
        }}
      >
        <th scope="row" className="portfolio-col-instrument">
          {row.workspaceHref ? (
            <Link
              className="portfolio-instrument-link"
              to={row.workspaceHref}
              onClick={(event) => event.stopPropagation()}
            >
              {row.symbol}
            </Link>
          ) : (
            <span className="portfolio-instrument-link">{row.symbol}</span>
          )}
          <span className="portfolio-side-chip" data-side={classifyOrderSide(row.side)}>
            {row.side}
          </span>
        </th>
        <td className="portfolio-col-num">{row.quantity ?? "—"}</td>
        <td className="portfolio-col-num">{row.filledLabel}</td>
        <td className="portfolio-col-num portfolio-order-price">{row.fillPriceLabel ?? "—"}</td>
        <td className="portfolio-col-type">{row.orderType}</td>
        <td>
          <span className={`paper-order-status paper-order-status--${statusTone}`}>
            {paperOrderStatusLabel(row.status)}
          </span>
        </td>
        <td className="portfolio-col-num portfolio-order-age" title={age?.title}>
          {age?.label ?? "—"}
        </td>
        <td className="portfolio-col-actions">
          <div className="portfolio-row-actions">
            {row.workspaceHref ? (
              <Link
                className="portfolio-row-open"
                to={row.workspaceHref}
                aria-label={`Open ${row.symbol} Workspace`}
                onClick={(event) => event.stopPropagation()}
              >
                Open<span aria-hidden="true"> →</span>
              </Link>
            ) : null}
            {canOfferCancel ? (
              <button
                type="button"
                className="portfolio-row-action-danger"
                aria-label={cancelLabel}
                disabled={cancelPending}
                onClick={(event) => {
                  event.stopPropagation();
                  onCancel?.(row);
                }}
              >
                Cancel
              </button>
            ) : null}
          </div>
        </td>
        <td className="portfolio-col-actions">
          <button
            type="button"
            className="portfolio-row-open"
            aria-expanded={expanded}
            aria-controls={`paper-order-details-${row.rowId}`}
            onClick={(event) => {
              event.stopPropagation();
              onToggleDetails();
            }}
          >
            Details
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr className="paper-order-details-row">
          <td colSpan={9} id={`paper-order-details-${row.rowId}`}>
            <PaperOrderHistoryRowDetails row={row} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

function classifyOrderSide(side: string): "long" | "short" | "flat" {
  const normalized = side.trim().toUpperCase();
  if (normalized === "BUY" || normalized === "LONG") return "long";
  if (normalized === "SELL" || normalized === "SHORT") return "short";
  return "flat";
}
