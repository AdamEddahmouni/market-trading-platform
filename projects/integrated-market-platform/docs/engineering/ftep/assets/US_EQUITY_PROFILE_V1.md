# FTEP US Equity Asset-Class Profile V1

**Classification:** `PREIMPLEMENTATION_PROFILE`  
**Inherits:** `FTEP_CORE_V1`  
**Scope:** US listed equity forward-test campaigns, including FTEP-V1-002 (US-equity-news-catalyst)

## Mandatory equity semantics

A US equity campaign must bind **canonical equity instrument keys** (ticker + venue), not continuous futures or index proxies unless explicitly preregistered as a benchmark-only arm.

The campaign manifest must record:

- venue (`US_EQUITY` default);
- eligible symbol universe and liquidity/capacity notes;
- corporate-action handling policy (splits, halts, delistings);
- session calendar (`US_EQUITY_RTH` unless extended hours are preregistered);
- market-data capability contract(s) actually entitled (L1 minimum for news-catalyst SIGNAL_ONLY);
- transaction-cost assumptions when execution claims are made;
- shortability/borrow assumptions when short arms are used.

## Market-data binding (FTEP-V1-002 pivot)

| Role | Provider | Capability | Incremental cost |
|------|----------|------------|------------------|
| Authority market context | Moomoo OpenD | `US_EQUITY_L1` | $0 incremental (existing owner access) |
| News/catalyst context | Finviz Elite | `NEWS_EXPORT` | $0 incremental (existing owner Elite) |
| Optional regulatory filings | SEC EDGAR | public HTTP | $0 incremental |

IBKR observational market data is **not** the immediate $0 path: live US equity L1 entitlements commonly require ~**$500** account funding for market-data subscriptions (documented constraint; not purchased in this increment).

## Non-goals

- Converting FTEP-V1-001 ES futures bindings to equity.
- Claiming entitled CME/ES streams without external Quote Store authorization.
- Live execution or empirical locks without owner authorization.
