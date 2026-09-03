# Professor brief, platform goal, and research roadmap

Updated: 2026-08-13. This document records the professor-supplied project brief,
the accompanying screenshot, the meeting transcript in
[`PROFESSOR_MEETING_TRANSCRIPT_20260813.md`](PROFESSOR_MEETING_TRANSCRIPT_20260813.md),
and implementation guidance. It is a project record, not financial advice.

## Stated overall goal

Build an integrated research/paper-trading platform in which short-squeeze,
CVD/Level-2/order-flow, news/options, futures, and a new whale/copy-trading
research lane can be compared through shared data and risk controls. IBKR is the
ultimate target because it can consolidate instruments and professional data, but
the current constraint is that a $500 account-equity hold is not available.

The screenshot says CVD/Level-2 requires IBKR Level 1 and Level 2 data; options
may also use IBKR; Eric’s futures work uses IB data; and the intended end state
is a unified platform. The professor offered to reimburse one month of data cost,
not to guarantee the $500 equity requirement.

## Data/broker decision: work now, design for IBKR later

| Candidate | Useful now | Important limitation | Recommendation |
|---|---|---|---|
| **Moomoo OpenAPI** | REST/WebSocket quotes, order-book, ticks, options and paper/live workflows; current docs advertise $0 API cost and paper trading | Requires account/API agreements; specific real-time/Level-2 rights, quotas and quotation cards vary by market and account. Validate US access before architectural commitment. | Best first experiment for the CVD adapter and paper-only event stream. |
| **Tradier** | Free account gives an API token and paper sandbox; supports US equities/options, orders, chains, and delayed quote testing. | Sandbox is 15-minute delayed, has no delayed streaming, and Tradier documents Level 1 only; it is not a CVD/Level-2 replacement or futures source. Real-time data requires a brokerage account. | Best free option-chain/paper execution adapter and API-contract test bed. |
| **Alpaca** | Paper trading and Basic market-data plan cost $0; equities IEX real-time and indicative options data are useful for non-microstructure integration/testing. | Not consolidated Level-2 / full options feed on Basic. | Keep as the existing internship-agent paper adapter; do not use for L2 truth. |
| **SEC EDGAR** | Free, authoritative filing history: Form 4 insider transactions; Schedule 13D/G large-beneficial-owner disclosures; quarterly Form 13F institutional holdings. | Disclosure is delayed and reports positions/ownership, not a real-time whale tape. | Core of a free, auditable whale-monitoring lane. |
| **IBKR** | Target adapter for real-time multi-asset data, Level 1/2, options, futures, and eventual controlled execution. | Account/data entitlement and exchange subscriptions must be confirmed before use. | Define an interface now; add only after account and subscriptions exist. |

Source checks: [Moomoo OpenAPI introduction](https://openapi.moomoo.com/futu-api-doc/en/), [Moomoo current developer overview](https://open.moomoo.com/), [Tradier endpoints](https://docs.tradier.com/docs/endpoints), [Tradier market-data limits](https://docs.tradier.com/docs/market-data), [Tradier FAQ](https://docs.tradier.com/docs/faq), [Alpaca market-data plans](https://docs.alpaca.markets/us/docs/about-market-data-api), and [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

## Whale-monitoring: feasible definition

Do not implement “follow Elon/Cathie/Buffett/Icahn” as automatic trading. Those
names are hypotheses/sources to monitor, not proof of causality, quality, timing,
or tradeability. Build an evidence ledger with these independent source classes:

1. **SEC ownership filings:** Form 4 (insider transactions), Schedule 13D/G
   (beneficial ownership), Form 13F (institutional holdings). Retain filer,
   issuer, filing/accepted time, transaction/position fields, source URL, and
   amendment flag. SEC’s free `data.sec.gov` submissions service is rate-limited
   to 10 requests/sec and requires an identifying User-Agent.
2. **Published-manager disclosures:** Berkshire 13Fs and ARK’s public daily-trade
   publications, where they exist. Treat each as a named source with publication
   time and disclosure latency—not as a broker feed.
3. **Public statement/catalyst events:** a cited primary post/interview/filing,
   timestamped and separated from price reaction. Never infer a trade merely from
   a social mention.
4. **Copy-trading platforms:** research dashboards only until terms, jurisdiction,
   performance history, fees, leverage, drawdown and slippage have been reviewed.

## LiteFinance assessment

LiteFinance has a social/copy-trading product: traders set a profit share and
investors can select full-volume, fixed-volume, percentage-volume, or
equity-proportional copying. Equity-proportional copying is documented as:

```text
copied volume = trader trade volume × investor allocated assets / trader equity
```

It is not a public US stock-whale data API. Its own US-facing FAQ says LiteFinance
Global LLC does not provide brokerage services in the United States; copied orders
can execute at different prices, and the platform disclaims endorsements. Use it
only for conceptual research/demo comparison unless legal eligibility and platform
terms are confirmed. Sources: [how it works](https://www.litefinance.org/social-trading/how-it-works/), [FAQ/US availability notice](https://www.litefinance.org/social-trading/faq/), and [client agreement](https://www.litefinance.org/uploads/documents/pdf-litefinance/litefinance-client-agreement-en.pdf?v=4142a5da).

## Recommended implementation sequence

1. Create broker-neutral interfaces: `MarketDataProvider`, `OrderBookProvider`,
   `OptionsProvider`, `PaperExecutionProvider`, and `DisclosureProvider`. Every
   event gets provider, entitlement, event-time, receive-time, symbol mapping,
   latency/quality, and raw-source reference.
2. Implement Tradier sandbox + Alpaca/Moomoo paper adapters behind those contracts;
   ensure no live order method is callable without a separate explicit enablement.
3. Build an EDGAR ingestion job and whale ledger. Normalize filings to event types
   such as `insider_buy`, `insider_sell`, `beneficial_owner_change`, and
   `institutional_holding_snapshot`; show disclosure lag prominently.
4. Add a dashboard tab that juxtaposes whale/disclosure events, CVD/Level-2
   measurements, short-squeeze evidence, news, option liquidity, and a
   “not actionable / research only” status. Do not create a composite buy score
   before data coverage and validation exist.
5. Run the system in replay/paper mode. Log signals, source freshness, simulated
   fills, spread/slippage, and outcomes; perform preregistered out-of-sample
   evaluation.
6. When funded, implement IBKR as another adapter and migrate only after comparing
   timestamps, symbols, depth semantics, and data entitlements against the paper
   feeds.

## Non-negotiable controls

- Separate public-disclosure observation from copying, recommendation, and order
  placement. Make all new whale signals research-only by default.
- Never describe 13F as live, or a public figure’s statement as a guaranteed price
  catalyst. Store facts with citations and mark interpretations as hypotheses.
- Cap data collection to provider terms/rate limits; do not scrape login-only
  LiteFinance profiles or bypass account access controls.
- Preserve the existing projects’ warnings: CVD is a measurement layer, the
  short-squeeze screener is read-only research, and the internship agent’s paper
  results do not establish profitability.
