import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import { EmptyState } from "../imp-ui/FeedbackStates";
import { FreshnessIndicator } from "../imp-ui/FreshnessIndicator";
import type {
  PortfolioPositionRow,
  SignedAmountPresentation,
} from "./paperPortfolioPresentation";
import { positionNeedsAttention } from "./paperPortfolioPresentation";

type Props = {
  positions: PortfolioPositionRow[];
  marksDecay: boolean;
  /** Handoff target used by the positions empty state. */
  workspaceHref: string;
};

function SignedAmount({ amount }: { amount: SignedAmountPresentation }) {
  return (
    <span className="portfolio-signed" data-direction={amount.direction}>
      {amount.text}
    </span>
  );
}

function PositionRowDetails({ row, marksDecay: decay }: { row: PortfolioPositionRow; marksDecay: boolean }) {
  return (
    <dl className="portfolio-row-detail-grid">
      <div>
        <dt>Instrument ID</dt>
        <dd>
          <CopyableIdentifier value={row.instrumentId} />
        </dd>
      </div>
      <div>
        <dt>Net quantity</dt>
        <dd>
          {row.side === "short" ? "−" : ""}
          {row.quantityLabel} sh
        </dd>
      </div>
      <div>
        <dt>Mark provider</dt>
        <dd>{row.markProvenance}</dd>
      </div>
      <div>
        <dt>Mark quality</dt>
        <dd>{row.markQuality ?? "Unavailable"}</dd>
      </div>
      <div>
        <dt>Mark as of</dt>
        <dd>
          <FreshnessIndicator backendLabel={row.markQuality} asOf={row.markAsOfNs} decays={decay} />
        </dd>
      </div>
      <div>
        <dt>Average fill</dt>
        <dd>{row.averageFill}</dd>
      </div>
    </dl>
  );
}

/**
 * Rapid exposure scanning. Instrument + direction lead; every market number is
 * right-aligned with tabular figures so magnitudes compare down the column.
 * Row selection surfaces the legitimate next actions for that position instead
 * of stamping a button set on every row.
 */
export function PortfolioPositionsTable({ positions, marksDecay: decay, workspaceHref }: Props) {
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const selected = useMemo(
    () => positions.find((row) => row.rowId === selectedRowId) ?? null,
    [positions, selectedRowId],
  );

  if (positions.length === 0) {
    return (
      <EmptyState
        title="No open positions"
        reason="This simulated account holds nothing right now."
        action={{ label: "Open Workspace", href: workspaceHref }}
      />
    );
  }

  return (
    <>
      <div className="portfolio-table-wrap">
        <table className="data-table portfolio-table portfolio-positions-table">
          <caption className="imp-visually-hidden">Open simulated positions</caption>
          <thead>
            <tr>
              <th scope="col" className="portfolio-col-instrument">
                Instrument
              </th>
              <th scope="col" className="portfolio-col-num">
                Qty
              </th>
              <th scope="col" className="portfolio-col-num">
                Avg fill
              </th>
              <th scope="col" className="portfolio-col-num">
                Mark
              </th>
              <th scope="col" className="portfolio-col-num portfolio-col-pnl">
                Unrealized P&amp;L
              </th>
              <th scope="col" className="portfolio-col-actions">
                <span className="imp-visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {positions.map((row) => {
              const isSelected = row.rowId === selectedRowId;
              return (
                <tr
                  key={row.rowId}
                  className="portfolio-row"
                  data-attention={positionNeedsAttention(row) ? "true" : "false"}
                  data-selected={isSelected ? "true" : "false"}
                  aria-selected={isSelected}
                  tabIndex={0}
                  onClick={() => setSelectedRowId(isSelected ? null : row.rowId)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedRowId(isSelected ? null : row.rowId);
                    }
                  }}
                >
                  <th scope="row" className="portfolio-col-instrument">
                    <Link
                      className="portfolio-instrument-link"
                      to={row.workspaceHref}
                      onClick={(event) => event.stopPropagation()}
                    >
                      {row.symbol}
                    </Link>
                    <span className="portfolio-side-chip" data-side={row.side}>
                      {row.sideLabel}
                    </span>
                  </th>
                  <td className="portfolio-col-num">{row.quantityLabel}</td>
                  <td className="portfolio-col-num">{row.averageFill}</td>
                  <td className="portfolio-col-num portfolio-mark-cell">
                    {row.mark}
                    {row.mark !== "Unavailable" ? (
                      <FreshnessIndicator
                        className="portfolio-mark-freshness"
                        backendLabel={row.markQuality}
                        asOf={row.markAsOfNs}
                        decays={decay}
                      />
                    ) : null}
                  </td>
                  <td className="portfolio-col-num portfolio-col-pnl">
                    <SignedAmount amount={row.unrealized} />
                  </td>
                  <td className="portfolio-col-actions">
                    <Link
                      className="portfolio-row-open"
                      to={row.workspaceHref}
                      aria-label={`Open ${row.symbol} Workspace`}
                      onClick={(event) => event.stopPropagation()}
                    >
                      Open
                      <span aria-hidden="true"> →</span>
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selected ? (
        <div className="portfolio-selection" data-testid="portfolio-position-selection">
          <div className="portfolio-selection-head">
            <p className="portfolio-selection-summary">
              <span className="portfolio-instrument-link">{selected.symbol}</span>
              <span className="portfolio-side-chip" data-side={selected.side}>
                {selected.sideLabel}
              </span>
              <span>
                {selected.quantityLabel} sh @ {selected.averageFill}
              </span>
              <SignedAmount amount={selected.unrealized} />
            </p>
            <div className="portfolio-selection-actions">
              <Link className="portfolio-action-primary" to={selected.workspaceHref}>
                Open Workspace
              </Link>
              <button
                type="button"
                className="portfolio-action-secondary"
                onClick={() => setSelectedRowId(null)}
              >
                Clear selection
              </button>
            </div>
          </div>
          <PositionRowDetails row={selected} marksDecay={decay} />
        </div>
      ) : null}
    </>
  );
}
