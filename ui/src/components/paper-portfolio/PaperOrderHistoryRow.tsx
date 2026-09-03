import { PaperDecisionProvenanceBadge } from "./PaperDecisionProvenanceBadge";
import { PaperPersistedSourceContextPanel } from "./PaperPersistedSourceContextPanel";
import type { PaperOrderHistoryRow } from "./paperOrderHistoryModel";
import { paperOrderStatusLabel, paperOrderStatusTone } from "./paperOrderStatusPresentation";

type Props = {
  row: PaperOrderHistoryRow;
  expanded: boolean;
  onToggle: () => void;
  onViewTrace?: (intentId?: string, orderId?: string) => void;
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
          <dd>{row.provenance.provenanceLabel}</dd>
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

export function PaperOrderHistoryRowView({ row, expanded, onToggle, onViewTrace }: Props) {
  const statusTone = paperOrderStatusTone(row.status);
  const traceLabel = row.symbol && row.symbol !== "—" ? `View trace for ${row.symbol}` : "View trace";

  return (
    <>
      <tr className={expanded ? "paper-order-row expanded" : "paper-order-row"}>
        <td className="paper-order-time">{row.submittedAtLabel ?? "—"}</td>
        <td>{row.symbol}</td>
        <td>{row.side}</td>
        <td>{row.quantity ?? "—"}</td>
        <td className="paper-order-type">{row.orderType}</td>
        <td>
          <span className={`paper-order-status paper-order-status--${statusTone}`}>{paperOrderStatusLabel(row.status)}</span>
        </td>
        <td className="paper-order-fill">{row.fillSummary}</td>
        <td>
          <PaperDecisionProvenanceBadge provenance={row.provenance} />
        </td>
        <td className="paper-order-source-detail">{row.provenance.tableSourceSummary}</td>
        <td>
          {onViewTrace ? (
            <button
              type="button"
              className="paper-order-trace-action"
              aria-label={traceLabel}
              onClick={() => onViewTrace(row.intentId ?? undefined, row.orderId ?? undefined)}
            >
              View trace
            </button>
          ) : null}
        </td>
        <td className="paper-order-expand-cell">
          <button
            type="button"
            className="paper-order-expand-action"
            aria-expanded={expanded}
            aria-controls={`paper-order-details-${row.rowId}`}
            onClick={onToggle}
          >
            {expanded ? "Hide details" : "Details"}
          </button>
        </td>
      </tr>
      {expanded ? (
        <tr className="paper-order-details-row">
          <td colSpan={11} id={`paper-order-details-${row.rowId}`}>
            <PaperOrderHistoryRowDetails row={row} />
          </td>
        </tr>
      ) : null}
    </>
  );
}
