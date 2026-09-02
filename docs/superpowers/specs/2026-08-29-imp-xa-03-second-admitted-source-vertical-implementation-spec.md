# IMP-XA-03 implementation spec (2026-08-29)

## Purpose

Prove the XA-02 admission architecture generalizes to a materially different second source vertical (CFTC institutional positioning) without creating a disconnected provenance system or untyped payload blobs.

## Source selection audit

| Candidate | Code | Fixtures | PIT | Distinct shape | XA target | Cost | Class |
|---|---:|---:|---:|---:|---:|---:|---|
| CFTC COT | `src/market_platform_foundation/cftc/**` | `tests/fixtures/cftc/**` | `release_schedule.py` | Structured category positions | Futures families | Low | **PREFERRED** |
| EIA | `eia/**` | partial | moderate | energy inventory scalars | commodities | medium | VIABLE |
| SEC/FINRA | minimal | none | unknown | filings | equities | high | DO_NOT_USE |
| Second FRED vertical | `fred/**` | yes | yes | scalar macro | rates | low | WEAK_FALLBACK |

**Selected source:** CFTC Commitments of Traders (TFF / Disaggregated futures-only reports).

**Selection rationale:** Full parser, normalize, mapping, release schedule, and deterministic fixtures already exist. Data shape is materially different from FRED scalar macro (multi-category contract counts, report-family taxonomy, official publication schedule).

**second provider/source proven: YES**

## Identity planes (locked)

```text
cftc_contract_market_code ≠ CFTC_MARKET report identity ≠ observation identity ≠ trader category ≠ XA futures family
```

Regulatory market reports are not instruments. Observations are reported quantities per category, not analytical signals.

## Common admission envelope (XA-02 hardening)

- `AdmissionEnvelope` — source-neutral temporal/provenance shell
- `ScalarMacroPayload` — FRED scalar fields (existing `AdmittedObservation` semantics)
- `PositioningPayload` — typed CFTC category position fields
- `AdmittedObservation` preserved unchanged for XA-02 backward compatibility

## Bounded CFTC catalog (5 markets)

| Market report ID | CFTC code | Report family | Scope | XA family | Domain |
|---|---|---|---|---|---|
| `CFTC_MARKET:13874+:TFF:FUTURES_ONLY` | 13874+ | TFF | FUTURES_ONLY | ES | EQUITIES |
| `CFTC_MARKET:067651:DISAGGREGATED:FUTURES_ONLY` | 067651 | DISAGGREGATED | FUTURES_ONLY | CL | ENERGY |
| `CFTC_MARKET:088691:DISAGGREGATED:FUTURES_ONLY` | 088691 | DISAGGREGATED | FUTURES_ONLY | GC | COMMODITIES |
| `CFTC_MARKET:020601:TFF:FUTURES_ONLY` | 020601 | TFF | FUTURES_ONLY | ZN | RATES |
| `CFTC_MARKET:023651:DISAGGREGATED:FUTURES_ONLY` | 023651 | DISAGGREGATED | FUTURES_ONLY | NG | ENERGY |

Relationship type: `REFERENCE_RELEVANT_TO` (positioning reference metadata, not causal).

## Temporal semantics

- `event_time` = position/as-of date
- `available_time` = official publication time (from `release_schedule` when known)
- `retrieval_time` = observed/retrieved time
- Report date ≠ publication availability unless source evidence proves equality

## Revision semantics

| Evidence | Classification |
|---|---|
| First fixture version / as-reported row | `ORIGINAL_OR_AS_REPORTED` |
| Explicit correction with version metadata | `REVISION_IDENTIFIED` |
| No revision metadata | `REVISION_STATUS_UNKNOWN` |

## Units

- Position fields: `contracts`
- Open interest: `contracts`
- `missing != zero`; no silent net-position derivation

## Query surfaces (XA03)

- `XA03.OP.STATUS` — unified vertical status (FRED + CFTC)
- `XA03.OP.VALIDATE`
- `XA03.OP.SHOW_SOURCE`
- `XA03.OP.SHOW_OBSERVATION`
- `XA03.OP.LIST_RELATIONSHIPS`
- `XA03.OP.ADMIT_FIXTURE`

## Protected boundaries

No XA-01 identity changes, no XA-02 FRED semantic changes, no OF/RT/EVIDENCE authority changes, no trading authority, no positioning analytics.

## Acceptance

Fixture classification: `FIXTURE`. Live CFTC smoke: `NOT_EXECUTED` unless explicitly run.
