import { Link } from "react-router-dom";
import { usePaperStrategyProfitabilityQuery } from "../../api/hooks";
import { LoadingState } from "../shared/LoadingState";
import { buildPaperStrategyProfitabilityModel } from "./paperStrategyProfitabilityModel";

export function PaperStrategyProfitabilityObservability() {
  const query = usePaperStrategyProfitabilityQuery();

  if (query.isLoading) {
    return (
      <section className="panel paper-strategy-profitability" aria-labelledby="paper-strategy-profitability-title">
        <LoadingState label="Loading strategy profitability lineage…" />
      </section>
    );
  }

  if (query.isError || !query.data) {
    return (
      <section
        className="panel paper-strategy-profitability unavailable"
        aria-labelledby="paper-strategy-profitability-title"
      >
        <p className="paper-eyebrow">Strategy observability</p>
        <h2 id="paper-strategy-profitability-title">Profitability lineage</h2>
        <p>Strategy runtime observability is unavailable for this Paper session.</p>
        <p className="muted">The portfolio ledger and order history remain authoritative.</p>
      </section>
    );
  }

  const model = buildPaperStrategyProfitabilityModel(query.data);
  const currency = query.data.account_ledger_pnl.currency;

  return (
    <section className="panel paper-strategy-profitability" aria-labelledby="paper-strategy-profitability-title">
      <div className="paper-strategy-profitability__header">
        <div>
          <p className="paper-eyebrow">Strategy observability</p>
          <h2 id="paper-strategy-profitability-title">Profitability lineage</h2>
          <p className="muted">
            Read-only reconstruction from allocation through fill, attribution, and settlement.
          </p>
        </div>
        <span className="paper-provenance-badge">PAPER · READ ONLY</span>
      </div>

      <dl className="metric-list paper-strategy-profitability__metrics">
        <div>
          <dt>Linked allocations</dt>
          <dd>{model.allocationCount}</dd>
        </div>
        <div>
          <dt>Settled predictions</dt>
          <dd>{model.settledCount}</dd>
        </div>
        <div>
          <dt>Ledger realized P&amp;L</dt>
          <dd>{formatMinorCurrency(model.ledgerRealizedPnlMinor, currency) ?? "Unavailable"}</dd>
        </div>
        <div>
          <dt>Ledger unrealized P&amp;L</dt>
          <dd>{formatMinorCurrency(model.ledgerUnrealizedPnlMinor, currency) ?? "Unavailable"}</dd>
        </div>
        <div>
          <dt>Strategy P&amp;L</dt>
          <dd>Per allocation</dd>
        </div>
      </dl>

      <p className="paper-strategy-profitability__disclaimer">{query.data.disclaimer}</p>

      {model.rows.length === 0 ? (
        <div className="paper-strategy-profitability__empty">
          <strong>No strategy-linked Paper allocations yet.</strong>
          <p>Strategy attribution appears here when a Paper runtime allocation has a proven account lineage.</p>
        </div>
      ) : (
        <div className="paper-strategy-profitability__table-wrap">
          <table className="paper-strategy-profitability__table">
            <caption className="sr-only">Strategy profitability and lineage by Paper allocation</caption>
            <thead>
              <tr>
                <th scope="col">Strategy / instrument</th>
                <th scope="col">Allocation</th>
                <th scope="col">Fills</th>
                <th scope="col">Attributed realized P&amp;L</th>
                <th scope="col">Settlement</th>
                <th scope="col">Workspace</th>
              </tr>
            </thead>
            <tbody>
              {model.rows.map((row) => (
                <tr key={row.allocationId}>
                  <td>
                    <strong>{row.strategyId}</strong>
                    <span className="paper-strategy-profitability__subline">{row.instrumentId}</span>
                    <span className="paper-strategy-profitability__subline">
                      Lineage: {row.lineageIds.map(shortId).join(" · ")}
                    </span>
                  </td>
                  <td>
                    {row.quantity} sh
                    <span className="paper-strategy-profitability__subline">
                      {shortId(row.allocationId)}
                    </span>
                  </td>
                  <td>
                    {row.fillCount}
                    {row.fillIds.length > 0 ? (
                      <span className="paper-strategy-profitability__subline">
                        {row.fillIds.map(shortId).join(" · ")}
                      </span>
                    ) : null}
                  </td>
                  <td>
                    {row.attributedPnlMinor === null
                      ? "Unavailable"
                      : formatMinorCurrency(row.attributedPnlMinor, currency) ?? "Unavailable"}
                    <span className="paper-strategy-profitability__subline">Sidecar snapshot</span>
                  </td>
                  <td>
                    <span className={`paper-order-status paper-order-status--${settlementClass(row.settlementState)}`}>
                      {row.settlementState}
                    </span>
                  </td>
                  <td>
                    {isValidInstrument(row.instrumentId) ? (
                      <Link to={`/workspace/${encodeURIComponent(row.instrumentId)}`}>Review in Workspace</Link>
                    ) : (
                      <span className="muted">Instrument unavailable</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="paper-strategy-profitability__footer">
        {model.strategyAttribution.label}. As of {new Date(query.data.as_of_context.as_of_ns / 1_000_000).toISOString()}.
      </p>
    </section>
  );
}

function shortId(value: string): string {
  return value.length > 16 ? `${value.slice(0, 12)}…` : value;
}

function formatMinorCurrency(minor: number, currency: string): string | null {
  if (!Number.isFinite(minor) || !currency) return null;
  try {
    return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(minor / 100);
  } catch {
    return null;
  }
}

function isValidInstrument(value: string): boolean {
  return value !== "Instrument unavailable" && /^[A-Za-z0-9._:-]+$/.test(value);
}

function settlementClass(value: string): "success" | "open" | "neutral" {
  if (value === "SETTLED") return "success";
  if (value === "PENDING") return "open";
  return "neutral";
}
