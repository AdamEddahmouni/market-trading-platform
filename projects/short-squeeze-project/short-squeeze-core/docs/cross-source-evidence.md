# Cross-Source Point-in-Time Evidence

## Phase 1I trade and quote independence

`TRADES` and `QUOTES` are independent coverage domains. Direct conflicts require compatible symbol, asset class, venue/market scope, event time, sequence scope, unit, and lifecycle stage. Same events from multiple providers remain separate; values are not merged, averaged, or winner-selected. A venue quote is never promoted to synthetic NBBO. Sequence scope incompatibility prevents comparison.

## Phase 1H market-bar independence

`MARKET_BARS` is an independent coverage domain. Records compete only when symbol, boundary, interval, session/date, and volume unit describe the same semantic fact. Explicit lifecycle chains are relationships rather than conflicts; unlinked disagreements remain visible. Providers are never averaged, ranked, or selected as authoritative. Objective bar-series output preserves all eligible observations in deterministic order.

## Phase 1G news independence

`NEWS` coverage is independent and includes only observations explicitly associated with the bundle symbol. News is not averaged, substituted, or compared as a competing value with other domains. Same-identity disagreements create news-specific conflicts; explicit lifecycle links and equal canonical URLs create revision or syndication relationships without merging provider observations.

## Purpose

`squeeze_core.evidence` answers: what evidence from each implemented source was available for this symbol at this exact time? It does not answer whether a symbol should be bought, sold, ranked, classified, or scored.

## Bundle contents

`PointInTimeEvidenceBundle` contains a deterministic ID and hash, symbol, as-of time, unchanged canonical observations, structured diagnostics, source-domain coverage, structured conflicts, and freshness/completeness summaries.

Phase 1C domains are `CANDIDATE_SNAPSHOT`, `BORROW_FEE`, and `BORROW_AVAILABILITY`. Phase 1D activates the independent `PUBLISHED_SHORT_INTEREST` domain when the input or policy requests it. Missing coverage remains `MISSING`; it never becomes a numeric zero or negative evidence.

## Selection rules

The immutable policy and builder:

1. keep only the requested symbol;
2. exclude observations first received after `as_of`;
3. exclude effective timestamps after `as_of + maximum_future_skew`;
4. apply event-specific maximum ages and stale policy;
5. apply delayed and unknown-freshness policy;
6. order observations with the canonical replay key;
7. preserve included observations byte-for-byte;
8. record exclusions and missing domains deterministically.

Future effective-time skew never relaxes the received-time rule. Evidence first received after `as_of` was unavailable at that point in time. Later observations never backfill earlier missing Finviz or IBKR fields.

Published short interest adds a strict source/publication gate before the existing receipt/effective gates. Settlement date never grants eligibility. Included short-interest observations carry separate availability and reporting-period ages. Eligible corrections create deterministic revision relationships while original and correction observations remain unchanged.

## Complementary semantics

Finviz `short_float_percent`, IBKR `annualized_fee_percent`, and IBKR `available_shares` are distinct evidence dimensions. They are not competing measurements and are never compared, averaged, substituted, or merged.

Published `short_shares`, Finviz short float, borrow fee, and borrow availability are likewise distinct. Published values compare only with the same semantic field and compatible settlement period. Different settlement periods are temporal differences. Phase 1D does not declare Finviz and published short-float methodology compatible.

## Conflict preservation

Compatible semantic values can produce:

- `VALUE_CONFLICT`: different-source, same-field, same-time values disagree beyond configured tolerance.
- `DUPLICATE_CONFLICT`: same-source, same-field, same-time records are duplicate or inconsistent.
- `TEMPORAL_DIFFERENCE`: compatible values have different effective times and may legitimately differ.
- `INCOMPATIBLE_SEMANTICS`: available as an explicit model classification, but automatic extraction refuses to create a comparison for semantically disjoint fields.

Conflicts retain observation IDs, values, units, sources, timestamps, and numeric differences. Original observations remain unchanged. There is no winner field and no averaging.

## Determinism

Ordering, diagnostics, coverage, conflicts, bundle IDs, serialization, and hashes use explicit fixture/context/policy data only. They do not use wall time, random UUIDs, paths, environment state, or unordered iteration.

## Offline command

```powershell
.\.venv\Scripts\python.exe -m squeeze_core build-evidence --input tests\fixtures\evidence\normalized_point_in_time.jsonl --symbol TESTA --as-of 2026-01-15T15:30:00Z
```

## SEC filing domain

Phase 1E activates independent `SEC_FILINGS` coverage when input or policy requests it. Filing metadata is not compared, averaged, substituted, or merged with market snapshots, borrow fee, borrow availability, or published short interest.

SEC filings add a strict public-availability gate before receipt/effective gates. Period of report and filed date never grant eligibility. Included filings carry separate availability, filing, and reporting-period ages. Eligible amendments create deterministic relationships while originals remain unchanged.

## Trading-halt domain

Phase 1F activates independent `TRADING_HALTS` coverage when observations or policy request it. Halt lifecycle facts are not averaged, substituted, or merged with market snapshots, borrow data, published short interest, or SEC filings.

Eligible halt rows pass strict publication, receipt, and effective-time gates. The bundle preserves announcement/halt/resumption ages, immutable revisions, compatible temporal differences, and contradictory same-event conflicts. Its `halt_state` is an objective summary of eligible lifecycle facts, not a strategy or prediction.
