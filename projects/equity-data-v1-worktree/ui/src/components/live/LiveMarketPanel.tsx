import { useMarketStateQuery, useWorkspaceOrderFlowQuery } from "../../api/hooks";

type Props = {
  instrumentId: string;
};

function formatMaybe(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return Number.isFinite(value) ? value.toString() : "—";
  return String(value);
}

export function LiveMarketPanel({ instrumentId }: Props) {
  const marketQuery = useMarketStateQuery(instrumentId);
  const flowQuery = useWorkspaceOrderFlowQuery(instrumentId);
  const market = marketQuery.data;
  if (!marketQuery.isFetched && !market) {
    return null;
  }
  if (!market?.available && marketQuery.isFetched && !marketQuery.isFetching) {
    return (
      <section className="live-market-panel capability-panel unavailable">
        <h2>Live market</h2>
        <p>No live quote, trades, or book yet for {instrumentId}. Subscribe from Explore.</p>
      </section>
    );
  }
  const quote = market?.quote ?? {};
  const book = market?.book ?? {};
  const bids = Array.isArray(book.bids) ? book.bids.slice(0, 5) : [];
  const asks = Array.isArray(book.asks) ? book.asks.slice(0, 5) : [];
  const trades = market?.trades_tail ?? [];
  const lastTrade = trades[trades.length - 1];
  const flow = flowQuery.data;
  const lastCvd = flow?.bars?.[flow.bars.length - 1];

  return (
    <section className="live-market-panel">
      <h2>Live observational · {instrumentId}</h2>
      <p className="muted">
        freshness {formatMaybe(market?.freshness_ms)} ms · trades {formatMaybe(market?.trade_count)} ·
        quality {formatMaybe(quote.quality)}
      </p>
      <dl className="metric-list">
        <div>
          <dt>Last</dt>
          <dd>{formatMaybe(quote.last_price ?? lastTrade?.price)}</dd>
        </div>
        <div>
          <dt>Bid / Ask</dt>
          <dd>
            {formatMaybe(quote.bid_price)} / {formatMaybe(quote.ask_price)}
          </dd>
        </div>
        <div>
          <dt>Last trade</dt>
          <dd>
            {formatMaybe(lastTrade?.quantity)} @ {formatMaybe(lastTrade?.price)}{" "}
            {formatMaybe(lastTrade?.aggressor_side)}
          </dd>
        </div>
        <div>
          <dt>CVD</dt>
          <dd>{formatMaybe(lastCvd?.cumulative_delta ?? flow?.cvd)}</dd>
        </div>
      </dl>
      <div className="live-dom-grid">
        <div>
          <h3>Bids</h3>
          <ul>
            {bids.length ? bids.map((row: { price?: number; size?: number }, idx: number) => (
              <li key={`bid-${idx}`}>
                {formatMaybe(row.price)} × {formatMaybe(row.size)}
              </li>
            )) : <li>—</li>}
          </ul>
        </div>
        <div>
          <h3>Asks</h3>
          <ul>
            {asks.length ? asks.map((row: { price?: number; size?: number }, idx: number) => (
              <li key={`ask-${idx}`}>
                {formatMaybe(row.price)} × {formatMaybe(row.size)}
              </li>
            )) : <li>—</li>}
          </ul>
        </div>
      </div>
    </section>
  );
}
