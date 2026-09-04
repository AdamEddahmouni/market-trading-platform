# IMP-XA-02 implementation spec (2026-08-29)

## Purpose

Admit the first bounded FRED rates/macro reference vertical with point-in-time provenance and typed cross-asset reference relationships to XA-01 instruments. XA-02 does not implement rates analytics, yield-curve engines, or trading authority.

## FRED audit summary

| Existing component | Path | Reuse decision |
|---|---|---|
| `MacroObservation` / `MacroIndicatorValue` | `fred/contracts.py` | REUSE_DIRECTLY |
| `canonical_indicator_id` registry | `fred/registry.py` | REUSE_DIRECTLY |
| V1/V2 normalization | `fred/normalize.py` | REUSE_DIRECTLY |
| PIT selection / `macro_as_of` | `fred/pit.py` | REFERENCE |
| `FredQualityFlag` | `fred/quality.py` | REUSE_DIRECTLY |
| `FredStore` | `fred/store.py` | DO_NOT_TOUCH |
| Fixtures | `tests/fixtures/fred/**` | REUSE_DIRECTLY |
| `CrossAssetRegimeContext` | `fred/cross_asset.py` | DO_NOT_TOUCH (analytics-adjacent) |

## Identity planes (locked)

```text
FRED series_id ≠ canonical_indicator_id ≠ XA instrument ID ≠ XA-02 observation_id
```

Macro indicators remain non-tradable. XA-02 admits observations and reference metadata only.

## Admission model

- `AdmittedObservation` wraps normalized `MacroObservation` fields with explicit `event_time`, `available_time`, `retrieval_time`, and `revision_classification`.
- Observation identity: `XA02:OBS:{sha256_prefix}` from canonical indicator, observation date, vintage identity, and source provider.
- Relationship identity: `XA02:REL:{sha256_prefix}` from indicator, relationship type, XA target, and domain.

## Revision semantics

| Source evidence | Classification |
|---|---|
| FRED V1 realtime rows with knowledge interval | `ORIGINAL_OR_AS_REPORTED` or `VINTAGE_IDENTIFIED` |
| FRED V2 snapshot / `SNAPSHOT` precision | `LATEST_ONLY` |
| Missing vintage metadata | `REVISION_STATUS_UNKNOWN` |

## First admitted vertical

Bounded rates catalog (5 series):

| Canonical indicator | FRED series | XA target | Relationship | Domain |
|---|---|---|---|---|
| `US_10Y_TREASURY_YIELD` | DGS10 | ZN family | `MACRO_REFERENCE_FOR` | RATES |
| `US_2Y_TREASURY_YIELD` | DGS2 | ZT family | `MACRO_REFERENCE_FOR` | RATES |
| `US_5Y_TREASURY_YIELD` | DGS5 | ZF family | `MACRO_REFERENCE_FOR` | RATES |
| `US_30Y_TREASURY_YIELD` | DGS30 | ZB family | `MACRO_REFERENCE_FOR` | RATES |
| `US_EFFECTIVE_FED_FUNDS_RATE` | DFF | USD currency | `MACRO_REFERENCE_FOR` | MONETARY_RESERVE |

Relationships are reference metadata only — no causal claims.

## Query surfaces

Operator capabilities (`--json` via `xa02` CLI):

- `XA02.OP.STATUS`
- `XA02.OP.VALIDATE`
- `XA02.OP.SHOW_INDICATOR`
- `XA02.OP.LIST_RELATIONSHIPS`
- `XA02.OP.ADMIT_FIXTURE`

## Persistence

In-memory admission registry for acceptance. No Mongo requirement. Fixture-backed admission is authoritative for XA-02 v1.

## Protected boundaries

No changes to XA-01 identity semantics, OF-01/02/03 authority, RT-01 trace semantics, EVIDENCE semantics, risk, execution, or broker transport.

## Acceptance

Fixture classification: `FIXTURE`. Live FRED smoke: `NOT_EXECUTED` unless explicitly run.
