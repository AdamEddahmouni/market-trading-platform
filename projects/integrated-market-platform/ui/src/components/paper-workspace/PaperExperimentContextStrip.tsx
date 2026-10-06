import type { PaperPortfolioResponse } from "../../api/client";
import { boundaryModel, formatMoney } from "../paper-portfolio/paperExperimentPresentation";

type Props = { portfolio: PaperPortfolioResponse | undefined; instrumentId: string };

/** Which fake-money account an order from this ticket would touch, shown before preview and submit. */
export function PaperExperimentContextStrip({ portfolio, instrumentId }: Props) {
  if (!portfolio) return null;
  const { experiment, valuation, boundary } = portfolio;
  if (!experiment || !valuation || !boundary) {
    return (
      <div className="panel paper-cockpit-panel experiment-context" data-testid="experiment-context-none">
        <strong>No active Paper experiment.</strong> Orders from this ticket use the default Paper session, not the
        $100,000 experiment account. Create the experiment from Paper Portfolio first.
      </div>
    );
  }
  const currency = valuation.currency;
  const held = portfolio.positions.find((row) => row.instrument_id === instrumentId);
  const model = boundaryModel(boundary);
  return (
    <section className="panel paper-cockpit-panel experiment-context" aria-labelledby="experiment-context-heading" data-testid="experiment-context">
      <h2 id="experiment-context-heading">Experiment: OCT1-09 Paper experiment · simulated capital</h2>
      <dl className="paper-cockpit-meta">
        <div><dt>Status</dt><dd>{experiment.status}</dd></div>
        <div><dt>Initial</dt><dd>{formatMoney(valuation.initial_capital_minor, currency)}</dd></div>
        <div><dt>Cash</dt><dd>{formatMoney(valuation.cash_minor, currency)}</dd></div>
        <div><dt>Buying power</dt><dd>{formatMoney(valuation.buying_power_minor, currency)}</dd></div>
        <div>
          <dt>Current position</dt>
          <dd>{held ? `${held.side} ${held.quantity} sh of ${held.symbol}` : `Flat in ${instrumentId}`}</dd>
        </div>
      </dl>
      <p className="muted">
        {model.headline}. {model.capitalLine} Account {experiment.paper_account_id.slice(0, 12)}…
      </p>
      {experiment.status !== "ACTIVE" ? (
        <p className="paper-cockpit-warning" role="status">This experiment is closed. New orders are refused.</p>
      ) : null}
    </section>
  );
}
