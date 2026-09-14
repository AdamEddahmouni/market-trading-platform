# Professor source and keyword catalog

**Status:** `RESEARCH_ONLY` — structured characterization for professor sequencing
(PD-05 / PD-06). Does **not** authorize procurement, credentials, or runtime
provider selection changes.

**Schema:** `1.1.0` (continues [PR #102](https://github.com/AdamEddahmouni/market-trading-platform/pull/102) `1.0.0` @ `73c7475`)

**Git baseline:** `origin/main` `5459619a` (#111)

**Machine-readable catalog:** [`PROFESSOR_SOURCE_KEYWORD_CATALOG.json`](./PROFESSOR_SOURCE_KEYWORD_CATALOG.json)

**JSON Schema (documentation):** [`PROFESSOR_SOURCE_KEYWORD_CATALOG.schema.json`](./PROFESSOR_SOURCE_KEYWORD_CATALOG.schema.json)

## What 1.1.0 adds (this increment)

| Gap left by #102 | 1.1.0 response |
|------------------|----------------|
| Equity-heavy 26-row list; futures/options/FI/FX/crypto only bundled | Per-market `market_source_maps` for US equity, options, futures, commodities, bonds/FI, FX, crypto, macro |
| No “why included / how validated” on rows | `inclusion_rationale` + `validation_method` on every source |
| `DEFAULT_CATALYST_REGISTRY` only partially mapped | All 24 registry ids mapped; professor **partnership** / **calls** explicit |
| Flat example terms | Versioned `keyword_packs` (`RESEARCH_ONLY_NOT_WIRED`) grouped by catalyst |
| No 8-K item taxonomy | `form_8k_item_map` research table |
| In-repo Cboe / FTD / NOAA packages unnamed as catalog rows | Split operational rows with existing provider docs |

**Not done (still PD-05/PD-06 open):** live professor-wire adapters; empirical false-positive/false-negative measurement; runtime registry expansion; assumed WRDS/I/B/E/S entitlements.

## Relationship to existing IMP docs

| Document | Role |
|----------|------|
| [PROVIDER_CANDIDATE_CATALOG_2026-09-11.md](./PROVIDER_CANDIDATE_CATALOG_2026-09-11.md) | Broad vendor universe (external research) |
| [PROVIDER_AND_DATA_RESEARCH_MATRIX.md](./PROVIDER_AND_DATA_RESEARCH_MATRIX.md) | Selection economics and sparse planning rows |
| [NEWS_EVENT_FOUNDATION.md](../architecture/NEWS_EVENT_FOUNDATION.md) | Runtime news/event contract and trust catalog semantics |
| [NEWS_SOURCES.md](../providers/NEWS_SOURCES.md) | NewsAPI/Finnhub/Finviz operator wiring |
| [CBOE_PUBLIC_OPTIONS_STATISTICS.md](../providers/CBOE_PUBLIC_OPTIONS_STATISTICS.md) | Options public aggregates |
| [SEC_FAILS_TO_DELIVER.md](../providers/SEC_FAILS_TO_DELIVER.md) | FTD settlement-fail evidence |
| [NOAA_NWS_CPC_WEATHER.md](../providers/NOAA_NWS_CPC_WEATHER.md) | Weather vintages for energy demand context |
| [PROVIDER_READINESS.md](../engineering/PROVIDER_READINESS.md) | Local gates and probes |
| `news/sources.py` / `news/catalysts.py` | In-code `CONFIGURED` vs `OPERATIONAL` and keyword registry |
| `artifacts/wave-a-findings/news-data-inventory.json` | Wave A configured_not_operational headline vendors |

## Frozen runtime policy

- G7, OpenD primary L1, Yahoo overlay-only honesty, Finviz hop gating, and Path A
  boundaries are unchanged.
- Seven professor-named headline sources remain **`CONFIGURED`** in
  `SourceTrustCatalog` until a separate activation increment wires adapters.
- Every catalog row sets `access_in_imp_claimed` explicitly; **false** means
  documentation or adapter existence does not assert operator access on this machine.
- Only `news_fixture` remains `access_in_imp_claimed: true`.
- Keyword packs are **not** loaded by `CatalystRegistry`.

## Market maps (operator summary)

Full id lists live in JSON `market_source_maps`.

| Market | Official / entitled primary (when gated) | Overlay | Research-only / not in repo |
|--------|------------------------------------------|---------|-----------------------------|
| US equity | EDGAR, FINRA SI, FTD, threshold lists, OpenD | Finviz, NewsAPI, Finnhub | Professor wires, IR, Sharadar, WRDS |
| US options | Entitled OPRA via OpenD, Cboe public stats | Finviz options export | Polygon OPRA, ORATS, Databento |
| Futures | OpenD/CME via broker, COT, EIA | Calendars, FRED | CME MDP 3.0, Databento, WASDE |
| Commodities | EIA, COT, NOAA weather, futures tape | Calendars | WASDE, MDP |
| Bonds / FI | FRED rates | Calendars | ICE CEP; Treasury official is KNOWN |
| FX | None as tape | Finnhub lite, calendars | Reuters/DJ CONFIGURED; official macro KNOWN |
| Crypto | None authorized | — | CEX public WS, Kaiko |
| Macro | FRED/ALFRED, EIA, COT | Finnhub calendar | BLS/BEA/Fed/Treasury KNOWN; wires CONFIGURED |

## Catalyst taxonomy

JSON `catalyst_taxonomy` (47 rows) maps **every** `DEFAULT_CATALYST_REGISTRY` id
plus research extensions.

Professor PD-06 examples:

| Term | Catalog id | In runtime registry? |
|------|------------|----------------------|
| partnership | `partnership` | Yes |
| earnings | `earnings` | Yes |
| calls | `earnings_call` | **No** (research pack only) |

**Gap rows remain research-only** (not added to `DEFAULT_CATALYST_REGISTRY`):
buybacks, dividends, litigation, geopolitical, unusual volume, short squeeze,
options activity headlines, earnings calls, 8-K item subtypes, WASDE, FOMC
minutes, Treasury auctions, weather HDD/CDD, crypto hack/listing/ETF, FX
intervention.

Empirical FP/FN measurement is **not claimed**. Fixture coverage ≠ live
precision.

## Access honesty

`access_in_imp_claimed` is **false** for all live paths. Adapter presence or a
provider markdown file does not mean this cloud/operator hop has keys, OpenD,
or entitlements.

## Project store mirror

User-facing narrative: Project Agent Store
`docs/professor-source-keyword-catalog.md`.
