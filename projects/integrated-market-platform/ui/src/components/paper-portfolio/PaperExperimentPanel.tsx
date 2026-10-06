import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useClosePaperExperimentMutation,
  useCreatePaperExperimentMutation,
  usePaperEquityHistoryQuery,
  usePaperTradesInfiniteQuery,
} from "../../api/hooks";
import type { PaperPortfolioResponse, PaperTrade } from "../../api/schemas";
import { CopyableIdentifier } from "../imp-ui/CopyableIdentifier";
import {
  UNAVAILABLE,
  boundaryModel,
  decisionSourceLabel,
  formatMoney,
  formatNs,
  formatReturn,
  formatSignedMoney,
  markAge,
  perShareCost,
  valuationQuality,
  type SignedMoney,
} from "./paperExperimentPresentation";

type Props = {
  data: PaperPortfolioResponse;
  canAct: boolean;
  onViewTrace: (intentId?: string, orderId?: string) => void;
};

function Signed({ amount }: { amount: SignedMoney }) {
  return (
    <span className={`experiment-signed experiment-signed-${amount.direction}`} aria-label={amount.label}>
      {amount.text}
    </span>
  );
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : "The request failed.";
}

/** Shown when no experiment is active: the $100,000 account is created only on an explicit action. */
export function PaperExperimentCreate() {
  const create = useCreatePaperExperimentMutation();
  return (
    <section className="panel experiment-panel" aria-labelledby="experiment-none-heading" data-testid="experiment-none">
      <h2 id="experiment-none-heading">No active Paper experiment</h2>
      <p>
        The OCT1-09 Paper experiment is one simulated account that starts with exactly $100,000.00 and is shared by
        every instrument. It is created only when you ask for it, is never topped up or reset on restart, and never
        uses live capital.
      </p>
      <button type="button" onClick={() => create.mutate()} disabled={create.isPending}>
        Create $100,000 Paper experiment
      </button>
      <p className="muted">
        The backend decides whether internal Paper simulation is authorized; if it is not, nothing is created.
      </p>
      {create.isError ? <p role="alert">Experiment was not created: {errorText(create.error)}</p> : null}
    </section>
  );
}

function TradeRow({ trade, currency, onViewTrace }: { trade: PaperTrade; currency: string; onViewTrace: Props["onViewTrace"] }) {
  const [open, setOpen] = useState(false);
  const realized = trade.position_effect === "OPEN" || trade.position_effect === "ADD"
    ? null
    : formatSignedMoney(trade.realized_pnl_delta_minor, currency);
  return (
    <>
      <tr>
        <td>{formatNs(trade.fill_time_ns)}</td>
        <th scope="row">{trade.symbol}</th>
        <td>{trade.side}</td>
        <td className="num">{trade.filled_quantity}</td>
        <td className="num">{formatMoney(trade.fill_price_minor, currency)}</td>
        <td className="num">{formatMoney(trade.commission_minor + trade.fees_minor, currency)}</td>
        <td>{trade.position_effect}</td>
        <td className="num">{realized ? <Signed amount={realized} /> : "—"}</td>
        <td>{decisionSourceLabel(trade.decision_source)}</td>
        <td>
          <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? "Hide decision" : "View decision"}
          </button>
        </td>
      </tr>
      {open ? (
        <tr className="experiment-trade-lineage">
          <td colSpan={10}>
            <p>
              Simulated fill ({trade.fill_kind}) of {trade.filled_quantity}
              {trade.requested_quantity ? ` of ${trade.requested_quantity} requested` : ""}. Commission{" "}
              {formatMoney(trade.commission_minor, currency)}, fees {formatMoney(trade.fees_minor, currency)}. Position
              after fill: {trade.position_after} sh.
            </p>
            <dl className="experiment-lineage">
              <div><dt>Order</dt><dd><CopyableIdentifier value={trade.order_id} /></dd></div>
              <div><dt>Fill</dt><dd><CopyableIdentifier value={trade.fill_id} /></dd></div>
              {trade.risk_decision_id ? (
                <div><dt>Risk decision</dt><dd><CopyableIdentifier value={trade.risk_decision_id} /></dd></div>
              ) : null}
              {trade.lineage_refs.map((ref) => (
                <div key={`${ref.kind}:${ref.id}`}>
                  <dt>{ref.kind.replace(/_/g, " ").toLowerCase()}</dt>
                  <dd><CopyableIdentifier value={ref.id} /></dd>
                </div>
              ))}
            </dl>
            <button type="button" onClick={() => onViewTrace(trade.intent_id ?? undefined, trade.order_id)}>
              Open execution trace
            </button>
          </td>
        </tr>
      ) : null}
    </>
  );
}

export function PaperExperimentPanel({ data, canAct, onViewTrace }: Props) {
  const experiment = data.experiment;
  const valuation = data.valuation;
  const close = useClosePaperExperimentMutation();
  const tradesQuery = usePaperTradesInfiniteQuery(experiment?.experiment_id);
  const equityQuery = usePaperEquityHistoryQuery(experiment?.experiment_id);
  if (!experiment || !valuation || !data.boundary || !data.assumptions) return null;

  const currency = valuation.currency;
  const boundary = boundaryModel(data.boundary);
  const quality = valuationQuality(valuation);
  const assumptions = data.assumptions;
  const active = experiment.status === "ACTIVE";
  const nowMs = Math.floor(valuation.valuation_cutoff_ns / 1_000_000);
  const trades = tradesQuery.data?.pages.flatMap((page) => page.trades) ?? [];
  const tradeTotal = tradesQuery.data?.pages[0]?.total_count ?? 0;
  const snapshots = equityQuery.data?.snapshots ?? [];
  const summary: Array<{ label: string; value: string | SignedMoney; lead?: boolean }> = [
    { label: "Initial capital", value: formatMoney(valuation.initial_capital_minor, currency) },
    { label: "Cash", value: formatMoney(valuation.cash_minor, currency) },
    { label: "Reserved cash", value: formatMoney(valuation.reserved_cash_minor, currency) },
    { label: "Buying power", value: formatMoney(valuation.buying_power_minor, currency) },
    { label: "Position value", value: formatMoney(valuation.position_value_minor, currency) },
    { label: "Realized P&L", value: formatSignedMoney(valuation.realized_pnl_minor, currency) },
    { label: "Unrealized P&L", value: formatSignedMoney(valuation.unrealized_pnl_minor, currency) },
    { label: "Total equity", value: formatMoney(valuation.equity_minor, currency), lead: true },
    { label: "Total Paper P&L", value: formatSignedMoney(valuation.total_pnl_minor, currency), lead: true },
    { label: "Paper experiment return", value: formatReturn(valuation.return_bps) },
  ];

  return (
    <section className="panel experiment-panel" aria-labelledby="experiment-heading" data-testid="experiment-panel">
      <header className="experiment-header">
        <div>
          <p className="experiment-eyebrow">OCT1-09 PAPER EXPERIMENT · SIMULATED CAPITAL</p>
          <h2 id="experiment-heading">{experiment.name}</h2>
          <p className="experiment-identity">
            <span data-testid="experiment-status">{experiment.status}</span>
            <CopyableIdentifier value={experiment.experiment_id} />
            <span>Started {formatNs(experiment.created_at_ns)}</span>
            <span>Evidence class {experiment.evidence_class}</span>
          </p>
        </div>
        {active && canAct ? (
          <button type="button" onClick={() => close.mutate(experiment.experiment_id)} disabled={close.isPending}>
            Close experiment
          </button>
        ) : null}
      </header>
      {close.isError ? (
        <p role="alert" data-testid="experiment-close-error">
          Experiment was not closed: {errorText(close.error)} Closing never sells positions for you.
        </p>
      ) : null}

      <div className="experiment-boundary" role="note" aria-label="Market data and execution boundary" data-testid="experiment-boundary">
        <strong>{boundary.headline}</strong>
        <ul>
          <li>{boundary.dataLine}</li>
          <li>{boundary.executionLine}</li>
          <li>{boundary.capitalLine}</li>
        </ul>
      </div>

      <dl className="portfolio-glance experiment-summary" data-testid="experiment-summary">
        {summary.map((metric) => (
          <div key={metric.label} data-lead={metric.lead ? "true" : undefined}>
            <dt>{metric.label}</dt>
            <dd>{typeof metric.value === "string" ? metric.value : <Signed amount={metric.value} />}</dd>
          </div>
        ))}
      </dl>
      <p className="experiment-quality" data-testid="experiment-quality" data-quality={quality.label}>
        <strong>Valuation quality: {quality.label}</strong> — {quality.detail}
        {valuation.newest_mark_as_of_ns ? ` Marks as of ${formatNs(valuation.oldest_mark_as_of_ns)} to ${formatNs(valuation.newest_mark_as_of_ns)}.` : ""}
        {` Buying power is cash less working-order reservations; no leverage.`}
      </p>

      <h3 id="experiment-positions-heading">Positions in this account</h3>
      {data.positions.length === 0 ? (
        <p className="muted">No open positions. Equity is cash.</p>
      ) : (
        <div className="experiment-table-scroll">
          <table className="experiment-table" aria-labelledby="experiment-positions-heading" data-testid="experiment-positions">
            <thead>
              <tr>
                <th scope="col">Symbol</th>
                <th scope="col">Side</th>
                <th scope="col" className="num">Quantity</th>
                <th scope="col" className="num">Average entry</th>
                <th scope="col">First entry</th>
                <th scope="col" className="num">Current mark</th>
                <th scope="col">Mark source · quality · age</th>
                <th scope="col" className="num">Position value</th>
                <th scope="col" className="num">Unrealized P&amp;L</th>
                <th scope="col">Risk control</th>
              </tr>
            </thead>
            <tbody>
              {data.positions.map((row) => (
                <tr key={row.instrument_id} data-testid={`experiment-position-${row.symbol}`}>
                  <th scope="row">{row.symbol}</th>
                  <td>{row.side}</td>
                  <td className="num">{row.quantity}</td>
                  <td className="num">{formatMoney(row.average_fill_minor, currency)}</td>
                  <td>{formatNs(row.first_entry_time_ns)}</td>
                  <td className="num">{formatMoney(row.mark_minor, currency)}</td>
                  <td>
                    {row.mark_minor === null || row.mark_minor === undefined
                      ? "No mark — not valued"
                      : `${row.mark_provider ?? "provider unavailable"} · ${row.mark_quality ?? "UNKNOWN"} · ${markAge(row.mark_as_of_ns, nowMs)}`}
                  </td>
                  <td className="num">{formatMoney(row.market_value_minor, currency)}</td>
                  <td className="num"><Signed amount={formatSignedMoney(row.unrealized_pnl_minor, currency)} /></td>
                  <td><Link to={`/workspace/${encodeURIComponent(row.instrument_id)}`}>Stop monitor in Workspace</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 id="experiment-trades-heading">Trade history (simulated fills)</h3>
      {tradesQuery.isError ? (
        <p role="alert">Trade history is unavailable. Positions and cash above remain authoritative.</p>
      ) : trades.length === 0 ? (
        <p className="muted">{tradesQuery.isLoading ? "Loading trade history…" : "No trades yet. Rejected and cancelled orders are listed under order history, not here."}</p>
      ) : (
        <div className="experiment-table-scroll">
          <table className="experiment-table" aria-labelledby="experiment-trades-heading" data-testid="experiment-trades">
            <thead>
              <tr>
                <th scope="col">Fill time</th>
                <th scope="col">Symbol</th>
                <th scope="col">Side</th>
                <th scope="col" className="num">Quantity</th>
                <th scope="col" className="num">Simulated fill</th>
                <th scope="col" className="num">Commission + fees</th>
                <th scope="col">Effect</th>
                <th scope="col" className="num">Realized P&amp;L</th>
                <th scope="col">Decision source</th>
                <th scope="col"><span className="sr-only">Decision detail</span></th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <TradeRow key={trade.fill_id} trade={trade} currency={currency} onViewTrace={onViewTrace} />
              ))}
            </tbody>
          </table>
          <p className="muted">
            Showing {trades.length} of {tradeTotal} trades.{" "}
            {tradesQuery.hasNextPage ? (
              <button type="button" onClick={() => void tradesQuery.fetchNextPage()} disabled={tradesQuery.isFetchingNextPage}>
                Load older trades
              </button>
            ) : null}
          </p>
        </div>
      )}

      <details className="experiment-assumptions" data-testid="experiment-assumptions">
        <summary>Fill, cost and slippage assumptions</summary>
        <dl className="experiment-lineage">
          <div><dt>Fill model</dt><dd>{assumptions.fill_model_registry_id} · {assumptions.fill_model_version} · {assumptions.fill_source_capability}</dd></div>
          <div><dt>Participation cap</dt><dd>{assumptions.participation_cap} of the fill bar's volume</dd></div>
          <div><dt>Commission</dt><dd>{perShareCost(assumptions.commission_minor_per_share, currency, "per share")}</dd></div>
          <div><dt>Fees</dt><dd>{perShareCost(assumptions.fee_minor_per_order, currency, "per order")}</dd></div>
          <div><dt>Slippage</dt><dd>{assumptions.slippage_model}. {assumptions.slippage_statement}</dd></div>
          <div><dt>Costs charged so far</dt><dd>{formatMoney(valuation.total_commission_minor + valuation.total_fees_minor, currency)}</dd></div>
          <div><dt>Cost policy</dt><dd><CopyableIdentifier value={assumptions.cost_policy_id} /></dd></div>
        </dl>
        <p>{assumptions.pnl_statement}</p>
      </details>

      <details className="experiment-assumptions" data-testid="experiment-equity-history">
        <summary>Equity history ({equityQuery.data?.total_count ?? 0} recorded states)</summary>
        {snapshots.length === 0 ? (
          <p className="muted">No recorded states.</p>
        ) : (
          <table className="experiment-table">
            <thead>
              <tr>
                <th scope="col">Recorded</th>
                <th scope="col">Trigger</th>
                <th scope="col" className="num">Cash</th>
                <th scope="col" className="num">Equity</th>
                <th scope="col" className="num">Paper P&amp;L</th>
                <th scope="col">Quality</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((row) => (
                <tr key={row.snapshot_id}>
                  <td>{formatNs(row.captured_at_ns)}</td>
                  <td>{row.trigger.replace(/_/g, " ").toLowerCase()}</td>
                  <td className="num">{formatMoney(row.cash_minor, currency)}</td>
                  <td className="num">{formatMoney(row.equity_minor, currency)}</td>
                  <td className="num"><Signed amount={formatSignedMoney(row.total_pnl_minor, currency)} /></td>
                  <td>{row.quality}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </details>
      {valuation.equity_minor === null ? (
        <p className="sr-only" role="status">Total equity is {UNAVAILABLE.toLowerCase()} because a position has no mark.</p>
      ) : null}
    </section>
  );
}
