# Provider candidate catalog (research-only)

**Status:** `RESEARCH-ONLY` — characterization and documentation pointers only.

**Observed:** 2026-09-11 (Wave A provider-universe research).

**Authority:** No vendor selection, procurement, credential storage, or network access authorized.
This catalog does **not** recommend integrating every listed vendor. For IMP selection
principles and sparse planning rows, see
[PROVIDER_AND_DATA_RESEARCH_MATRIX.md](./PROVIDER_AND_DATA_RESEARCH_MATRIX.md).
For **verified in-repo** wiring and readiness, see `docs/providers/*` and
[PROVIDER_READINESS.md](../engineering/PROVIDER_READINESS.md).

**Confidence:** **High** = primary vendor docs checked in the research pass; **Med** =
product clear, pricing/entitlements need confirmation; **Low** = partial public detail.

---

## IMP adapter role legend

| Code | Meaning |
|------|---------|
| **MD** | Normalized market data (live / delayed / historical) |
| **EXEC** | Order routing; paper or live broker |
| **REF** | Reference, symbology, corporate actions |
| **EVT** | News, calendars, corporate events |
| **FUND** | Fundamentals / estimates (PIT where noted) |
| **MACRO** | Economic series, rates curves (non-tradeable) |
| **FIL** | Regulatory filings / XBRL |
| **RISK** | Borrow, financing, crowding |
| **ANLY** | Derived analytics (IV surfaces, TCA, etc.) |

---

## Rights and redistribution (cross-cutting)

| Concern | Typical pattern | IMP implication |
|--------|------------------|-----------------|
| Exchange display / OPRA / CME MDP | Per-user or per-device fees; redistribution often restricted without business tier | Model **entitlements** separately from API keys; audit display use |
| Delayed vs real-time | 15-min SIP, CME delayed Pub/Sub, etc. | Tag observations with `latency_tier` |
| Historical depth | EOD free tiers vs tick/MBO purchased | Storage cost drives feasibility |
| PIT fundamentals | “As-reported” ≠ vintage without `datekey` / snapshot tables | Backtests use PIT store, not latest restated |
| SEC EDGAR | Free read APIs; ~10 req/s; **User-Agent** required | Strong **FIL** source; not exchange MD |
| Paper trading | Often same API as live (different host/port) | Environment guardrails mandatory |

---

## 1. Futures — market data

| Candidate | Capabilities (summary) | Live / delayed / hist | IMP roles | Primary docs | Conf. |
|-----------|------------------------|------------------------|-----------|--------------|-------|
| **CME Group MDP 3.0 + DataMine** | MDP 3.0 SBE multicast; MBO, MBP-10, trades; Pub/Sub + WebSocket; DataMine v2 historical | Live (licensed), delayed tier, historical entitlements | MD, REF | [MDP 3.0](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457219613/CME+MDP+3.0+Market+Data), [DataMine API](https://www.cmegroup.com/datamine/datamine-api.html), [DataMine migration](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457413432/CME%2BDataMine%2BDataset%2BDelivery%2BMigration) | High (fees Med) |
| **Databento** | Unified historical + live; `GLBX.MDP3`; MBO/MBP/OHLCV | Live + historical replay | MD | [Futures](https://databento.com/futures), [GLBX.MDP3](https://databento.com/datasets/GLBX.MDP3), [Historical API](https://databento.com/docs/api-reference-historical) | High |
| **dxFeed** | Quotes, T&S, options analytics; multi-asset | Package-dependent | MD, ANLY | [Market Data API](https://kb.dxfeed.com/en/market-data-api.html), [Symbology](https://kb.dxfeed.com/en/data-model/symbology-guide/general-provisions.html) | Med |
| **Polygon.io / Massive (futures tier)** | REST/WS, flat files; tiered depth | Tiered EOD → real-time | MD (prototype) | [Docs hub](https://polygon.io/docs) | Med (rebrand/pricing) |

**Rights:** CME and vendor pass-through licensing; redistribution restricted.

---

## 2. Futures — paper / sandbox brokers (EXEC)

| Candidate | Paper / sim | Assets (summary) | Notable gates | IMP role | Primary docs | Conf. |
|-----------|-------------|------------------|---------------|----------|--------------|-------|
| **Interactive Brokers** | Paper account; API ports differ paper vs live | Futures, FOP, equities, FX, bonds | Market data uses live entitlements or delayed | EXEC (MD optional via IB) | [Paper trading glossary](https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/) | High |
| **Tradovate** | `demo.tradovateapi.com` vs live host | Futures ecosystem | `isAutomated: true` for CME algo; tokens not portable demo/live | EXEC | [NinjaTrader API getting started](https://docs.ninjatrader.com/api/getting-started) | High |
| **Rithmic** | Exchange Simulator + R\|API+ | CME/Nasdaq ticks + sim matching | Conformance before production; trial advertised | EXEC, MD (bundled) | [Exchange Simulator](https://www.rithmic.com/products/exchange-simulator), [APIs](https://www.rithmic.com/apis) | High |
| **CQG WebAPI** | `wss://demoapi.cqg.com:443` sim | MD + orders in sim | Demo credentials IP allowlist; conformance | EXEC | [Web API testing](https://partners.cqg.com/api-resources/web-api/testing), [WebAPI help](https://help.cqg.com/apihelp/Documents/cqgwebapi.htm) | High |

---

## 3. News and events (EVT)

| Candidate | Capabilities (summary) | Cost / rights (summary) | IMP role | Primary docs | Conf. |
|-----------|------------------------|-------------------------|----------|--------------|-------|
| **Benzinga** | News API v2; Calendar v2.1 (earnings, economics, splits, etc.) | Commercial; text redistribution usually restricted | EVT | [Welcome](https://docs.benzinga.com/introduction/welcome), [News](https://docs.benzinga.com/api-reference/news-api/get-news-items), [Economics calendar](https://docs.benzinga.com/api-reference/calendar-api/get-economics) | High |
| **Tiingo** | `/tiingo/news`; ticker tags | Tiered | EVT (also MD/FUND same vendor) | [News](https://www.tiingo.com/documentation/news) | High |
| **Finnhub** | News + earnings/IPO/economic calendars; forex/crypto candles | Free tier + paid limits | EVT, MACRO (lite) | [Economic calendar](https://finnhub.io/docs/api/economic-calendar) | Med |

---

## 4. Equities (MD / REF / FUND)

| Candidate | Capabilities (summary) | IMP roles | Primary docs | Conf. |
|-----------|------------------------|-----------|--------------|-------|
| **Databento US equities** | Top-of-book blend, delayed summary, tick history (product-dependent) | MD | [Stocks](https://databento.com/stocks) | High |
| **Tiingo** | Cleansed EOD; IEX real-time (not full SIP) | MD, REF, FUND add-on | [Stock API](https://www.tiingo.com/products/stock-api) | High |
| **LSEG Refinitiv Data Platform** | `get_history`, tick/T&S, FX RICs, fundamentals fields | MD, FUND | [Historical pricing tutorial](https://developers.lseg.com/en/api-catalog/refinitiv-data-platform/refinitiv-data-library-for-python/tutorials/content-tutorials/historical-pricing) | High (pricing Med) |
| **IEX DEEP / DEEP+** | Aggregated price-level depth on IEX only (not MBO) | MD (niche) | [Market data resources](https://www.iex.io/resources/trading/market-data) | High |

---

## 5. Options (MD / ANLY)

| Candidate | Capabilities (summary) | Rights | IMP roles | Primary docs | Conf. |
|-----------|------------------------|--------|-----------|--------------|-------|
| **Polygon/Massive OPRA** | Chains, trades, quotes, WS; Greeks on paid tiers | OPRA license | MD | [Options docs](https://polygon.io/docs/options) | Med (pricing) |
| **ORATS Data API v2** | EOD + intraday; IV surfaces; history to ~2007 | Not full OPRA tick substitute | ANLY, MD (smoothed IV) | [Data API](https://docs.orats.io/datav2-api-guide/data.html), [Product](https://orats.com/data-api) | High |
| **dxFeed** | Options analytics (Greeks, TheoPrice) | Exchange bundles | MD, ANLY | [Market Data API](https://kb.dxfeed.com/en/market-data-api.html) | Med |

---

## 6. Fixed income / rates (MD / MACRO / EXEC)

| Candidate | Capabilities (summary) | IMP roles | Primary docs | Conf. |
|-----------|------------------------|-----------|--------------|-------|
| **ICE Data API + CEP** | Evaluated pricing ~2.5M bonds; liquidity/TCA | MD | [ICE Data API](https://www.ice.com/fixed-income-data-services/access-and-delivery/connectivity-and-feeds/ice-data-api), [CEP catalog](https://developer.ice.com/fixed-income-data-services/catalog/ice-continuous-evaluated-pricingtm-ceptm) | High |
| **ICE Bonds / BondPoint** | Dealer RFQ / click-to-trade (separate from CEP) | EXEC (FI workflow) | [ICE FI Select](https://www.ice.com/fixed-income-data-services/fixed-income/ice-bonds/ice-fi-select) | High |
| **FRED / ALFRED** | Macro series; `realtime_start/end`, vintage dates | MACRO (PIT macro) | [FRED overview](https://fred.stlouisfed.org/docs/api/fred/overview.html), [Observations](https://fred.stlouisfed.org/docs/api/fred/series_observations.html) | High |
| **LSEG Refinitiv** | Curves, bond fields (entitlement-driven) | MD, MACRO | [Historical pricing](https://developers.lseg.com/en/api-catalog/refinitiv-data-platform/refinitiv-data-library-for-python/tutorials/content-tutorials/historical-pricing) | Med |

---

## 7. FX (MD)

| Candidate | Notes | Primary docs | Conf. |
|-----------|-------|--------------|-------|
| Refinitiv RDP | Spot/ref via RICs, intraday intervals | [Historical pricing](https://developers.lseg.com/en/api-catalog/refinitiv-data-platform/refinitiv-data-library-for-python/tutorials/content-tutorials/historical-pricing) | High |
| Polygon/Massive | Forex REST/WS tiers | [polygon.io/docs](https://polygon.io/docs) | Med |
| dxFeed | FX in symbology model | [Symbology](https://kb.dxfeed.com/en/data-model/symbology-guide/general-provisions.html) | Med |
| Finnhub | `forex_candles`, `forex_rates` | [Forex candles](https://finnhub.io/docs/api/forex-candles) | Med |

---

## 8. Crypto (MD / EXEC)

| Candidate | Capabilities (summary) | Paper / sim | IMP roles | Primary docs | Conf. |
|-----------|------------------------|-------------|-----------|--------------|-------|
| **Kaiko** | L1 trades; L2 snapshots + tick CSV; ~72h stream replay | N/A (vendor replay) | MD | [Raw order book snapshot](https://docs.kaiko.com/rest-api/cefi-spot-market-data/order-book-aggregations/raw-order-book-snapshot), [L1/L2](https://www.kaiko.com/products/l1-l2-data) | High |
| **Coinbase Advanced Trade** | Public WS ticker, level2, market_trades | No exchange sim | MD, EXEC (if brokerage) | [WebSocket overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-overview) | High |
| **Alpaca / Tiingo / Finnhub / Polygon** | Prices, candles, trading (Alpaca); not full global L2 | Alpaca paper API | MD, EXEC (Alpaca) | [Alpaca paper trading](https://alpaca.markets/learn/start-paper-trading) | Med |

---

## 9. Short / borrow (RISK)

| Candidate | Capabilities (summary) | Delivery | IMP role | Primary docs | Conf. |
|-----------|------------------------|----------|----------|--------------|-------|
| **S3 Partners** | Daily SI + securities finance rates, crowding | API/SFTP, Snowflake, AWS Marketplace, Bloomberg DL | RISK | [Data & predictive](https://www.s3partners.com/data-predictive), [AWS listing](https://aws.amazon.com/marketplace/pp/prodview-l3a2kf5yecuy6) | High (API schema Med) |
| **IBKR / Alpaca** | Locate/borrow workflow | Broker-only | EXEC adjunct, not market-wide borrow feed | — | High (scope) |

**Rights:** Highly restricted redistribution for institutional borrow analytics.

---

## 10. Macro (MACRO / EVT)

| Candidate | Notes | IMP role | Primary docs | Conf. |
|-----------|-------|----------|--------------|-------|
| FRED/ALFRED | US macro + vintages | MACRO | [FRED API](https://fred.stlouisfed.org/docs/api/fred/overview.html) | High |
| Benzinga Calendar | Economics events, importance filters | EVT, MACRO | [Economics](https://docs.benzinga.com/api-reference/calendar-api/get-economics) | High |
| Finnhub | `calendar_economic` | MACRO lite | [Economic calendar](https://finnhub.io/docs/api/economic-calendar) | Med |

---

## 11. Filings (FIL)

| Candidate | Capabilities (summary) | Auth / limits | IMP role | Primary docs | Conf. |
|-----------|------------------------|---------------|----------|--------------|-------|
| **SEC EDGAR (`data.sec.gov`)** | Submissions JSON, XBRL company facts, bulk ZIPs | No API key; User-Agent; ~10 req/s | FIL | [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | High |

**Note:** EDGAR Next **submission** APIs require filer tokens — distinct from read-only research ingest.

**In-repo pointer:** [SEC_EDGAR.md](../providers/SEC_EDGAR.md).

---

## 12. Point-in-time historical (FUND / MACRO)

| Candidate | PIT / vintage behavior (summary) | IMP role | Primary docs | Conf. |
|-----------|----------------------------------|----------|--------------|-------|
| **Sharadar SF1 (Nasdaq Data Link)** | `datekey` vs report period; ARQ/ARY dimensions | FUND | [SF1](https://data.nasdaq.com/databases/SF1), [Data organization](https://docs.data.nasdaq.com/docs/data-organization) | High |
| **S&P Compustat Snapshot / Xpressfeed / Cap IQ PIT** | Observation dates to 1984+; filing/delivery history | FUND | [Xpressfeed](https://www.marketplace.spglobal.com/en/solutions/xpressfeed-(b73250d6-a15c-4243-9016-3e5bf6300e43)), [Compustat brochure](https://www.spglobal.com/marketintelligence/en/documents/compustat-brochure_digital.pdf) | High (delivery Med) |
| **Tiingo fundamentals** | `asReported=True` — partial PIT, not full vintage graph | FUND | [Fundamentals](https://www.tiingo.com/documentation/fundamentals) | High |
| **FRED vintages** | Macro release revisions | MACRO PIT | [FRED overview](https://fred.stlouisfed.org/docs/api/fred/overview.html) | High |

---

## 13. L2 / MBO (MD)

| Candidate | Depth type | Assets | Notes | Conf. |
|-----------|------------|--------|-------|-------|
| CME MDP 3.0 | MBO + MBP-10 | Futures | Primary exchange source; SBE multicast | High |
| Databento `mbo` | MBO | CME + others | Normalized replay | High |
| Kaiko | L2 snap + tick updates | Crypto CEX | Reconstruct book from snap + updates | High |
| dxFeed | Venue-dependent | Multi | Confirm per package | Med |
| Polygon/Massive | Trades/quotes; not full US equity MBO | US | SIP limitations | Med |
| IEX DEEP+ | Aggregated depth (not MBO) | IEX only | Subscriber agreement | High |
| Nasdaq TotalView / NYSE OpenBook / OPRA direct | Exchange-native | US | Requires direct exchange agreements (not expanded here) | Med |

---

## 14. Equities / options paper brokers (EXEC, non-futures)

| Candidate | Paper? | Assets | Primary docs |
|-----------|--------|--------|--------------|
| Alpaca | Yes (`paper-api`) | US stocks, ETFs, options, crypto | [Paper trading guide](https://alpaca.markets/learn/start-paper-trading) |
| IBKR | Yes | Broad | See §2 |

**In-repo pointers (verified wiring, not this catalog):** [TRADIER_PAPER.md](../providers/TRADIER_PAPER.md), [MOOMOO_OBSERVATIONAL.md](../providers/MOOMOO_OBSERVATIONAL.md), [IBKR_OBSERVATIONAL.md](../providers/IBKR_OBSERVATIONAL.md).

---

## 15. Enterprise bundles (catalog only)

| Candidate | Typical roles | Public API detail | Conf. |
|-----------|---------------|-------------------|-------|
| Bloomberg Data License / B-PIPE | MD, REF, FUND, MACRO, RISK (via partners) | Contract-only | Low–Med |
| FactSet | FUND, EST, EVT | Contract-only | Low |
| ICE Consolidated Feed | MD FI + cross-asset | [Developer portal](https://developer.ice.com/) | Med |

Listed for entitlement/compliance context only — not a build directive.

---

## Open unknowns (workshop inputs)

1. **Production venues:** CME-only vs multi-asset US vs global.
2. **Display vs internal** use (exchange fee magnitude).
3. **PIT bar** for fundamentals (research-tier vs institutional Compustat-class).
4. **Book fidelity:** MBO vs MBP vs top-of-book.
5. **Paper EXEC parity:** which live broker paper must mirror (IBKR, Rithmic, Tradovate, CQG, etc.).
6. **News redistribution:** UI display vs NLP-only features.
7. **L2/MBO design:** native ITCH/OUCH vs vendor normalization; MBO retention; cross-venue spread symbology.

---

## Freshness disclaimer

Pricing, rebrands (e.g. Polygon → Massive), and CME DataMine v2 migration deadlines change frequently. Dollar figures from third-party plan mirrors are **indicative** until confirmed on vendor checkout or order form.

---

## Related IMP documents (not superseded by this catalog)

| Document | Relationship |
|----------|----------------|
| [PROVIDER_AND_DATA_RESEARCH_MATRIX.md](./PROVIDER_AND_DATA_RESEARCH_MATRIX.md) | Selection principles + sparse planning rows |
| [docs/providers/](../providers/) | Integrated / admitted provider operator docs |
| [PROVIDER_READINESS.md](../engineering/PROVIDER_READINESS.md) | Local credential presence and probes |
| [docs/audits/imp-reconciliation/05-capability-matrix.md](../audits/imp-reconciliation/05-capability-matrix.md) | Repo requirement vs implementation matrix |
