# CFTC Commitments of Traders (COT)

**Status:** OBSERVED / CAPTURED (not ADMITTED)  
**Source:** Official CFTC Public Reporting Environment — https://publicreporting.cftc.gov/  
**ADR:** ADR-COT-001

## Purpose

COT provides **official aggregate regulatory participant-class positioning** for futures markets. It strengthens Futures (F4), Participant Intelligence (PI11 cross-asset), and Market Context lanes as slow-moving institutional positioning context.

COT is **not** a trading signal, smart-money score, or whale identity feed.

## Release Schedule & PIT Semantics

| Clock | Meaning |
|-------|---------|
| `position_date` | Tuesday close-of-business positions (holiday-adjusted) |
| `publication_time` | Official CFTC release (typically Friday 15:30 ET) |
| `available_time` | PIT knowledge cutoff — equals `publication_time` when known |
| `observed_time` | First platform observation / capture time |

**Critical:** `position_date ≠ publication_time`. A query on Thursday MUST NOT see Tuesday's unreleased positions.

Federal holidays can delay publication. The platform uses the **official 2026 CFTC release schedule** — not `Tuesday + 3 days`.

For historical rows beyond the published schedule window: `HISTORICAL_PUBLICATION_TIME_INFERRED`.

## Official Datasets (Observed IDs)

| Dataset | Socrata ID | Report Family | Scope |
|---------|-----------|---------------|-------|
| TFF Futures Only | `gpe5-46if` | TFF | FUTURES_ONLY |
| TFF Combined | `yw9f-hn96` | TFF | FUTURES_AND_OPTIONS_COMBINED |
| Disaggregated Futures Only | `72hh-3qpy` | DISAGGREGATED | FUTURES_ONLY |
| Disaggregated Combined | `kh3c-gbw2` | DISAGGREGATED | FUTURES_AND_OPTIONS_COMBINED |
| Legacy Futures Only | `6dca-aqww` | LEGACY | FUTURES_ONLY |
| Legacy Combined | `jun7-fc8e` | LEGACY | FUTURES_AND_OPTIONS_COMBINED |
| Supplemental CIT | `4zgm-a668` | SUPPLEMENTAL_CIT | FUTURES_ONLY |
| ProductHierarchy | `rj6x-va3z` | — | mapping |

**Double-count hazard:** All-dataset exports may contain both Futures Only and Combined rows. The pipeline requires explicit `position_scope` — never aggregate both.

## Report Families & Categories

### TFF (financial futures — ES, NQ, rates, FX)

- Dealer / Intermediary
- Asset Manager / Institutional
- Leveraged Funds
- Other Reportables
- Non-Reportables

### Disaggregated (commodities — CL, NG, GC, agriculture)

- Producer / Merchant
- Swap Dealer
- Managed Money
- Other Reportable
- Non-Reportable

### Legacy (longer history, cross-check)

- Commercial
- Non-Commercial
- Non-Reportable

**Do not** map Managed Money ≡ Leveraged Funds. They are different taxonomies.

## Contract-Family Identity

COT reports at **market/contract-family** level (e.g., E-MINI S&P 500), not specific expirations (ESU26). Mapping uses ProductHierarchy + seed mappings. Downstream strategies must explicitly map family-level positioning to active contracts.

## Derived Features (UNVALIDATED)

| Feature | Layer | Predictive |
|---------|-------|------------|
| long, short, spreading | RAW | false |
| net_position | DERIVED | false |
| net_pct_open_interest | DERIVED | false |
| weekly_net_change | DERIVED | false |
| net_percentile_52w/104w | DERIVED | false |
| net_zscore | DERIVED | false |

Position deltas are **weekly reported position changes**, not buy/sell volume. Classification changes can affect week-over-week deltas.

## Quality Flags

- `SOURCE_UNAVAILABLE`
- `REPORT_NOT_YET_RELEASED`
- `EXPECTED_NOT_YET_AVAILABLE`
- `PUBLICATION_TIME_INFERRED`
- `HISTORICAL_PUBLICATION_TIME_INFERRED`
- `PRODUCT_MAPPING_UNRESOLVED`
- `REPORT_SCOPE_AMBIGUOUS`

## Sync

```python
from market_platform_foundation.cftc import sync_cot
sync_cot()  # idempotent incremental sync
```

Scheduler-friendly: run Friday after 15:30 ET with holiday-aware retry.

## Limitations

- Weekly lag (Tuesday positions, Friday release)
- Aggregate categories only — no individual trader identity
- No transaction timing
- Reporting-threshold coverage — absence from COT ≠ no institutional positions
- Dealer/producer positions often reflect hedging, not directional views
- Contract-family aggregation, not expiration-specific

## Classification Legend

| Label | Meaning |
|-------|---------|
| DOCUMENTED | From official CFTC documentation |
| OBSERVED | Confirmed via live API probe |
| INFERRED | Conservative policy when exact data unavailable |
| UNTESTED | Derived features not validated for prediction |
