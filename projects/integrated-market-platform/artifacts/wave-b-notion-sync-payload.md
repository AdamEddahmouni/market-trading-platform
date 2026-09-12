# Wave B closure — Notion sync payload

**Observed:** 2026-09-11  
**Package 3 baseline:** `613a6b4` (calibration comparator + bridge fixes)  
**Disposition:** PARTIALLY_COMPLETE (external / owner blockers)

## Executive summary

Wave B closed prerequisite implementation packages 1–5 from `reconciliation-gate.json` plus the offline **provider snapshot comparison harness**. Qualifying FTEP-V1-001 activation remains blocked by owner decisions, ES futures entitlement probe, and live news gaps.

## Provider capability table (operator view)

| Provider / path | Matrix role | Live probe (Wave A/B) | Campaign note |
| --- | --- | --- | --- |
| Moomoo OpenD | Primary observational MD | NEEDS_LOCAL_PRIVATE_PROBE | ES futures quote entitlement not evidenced |
| IBKR CP Gateway | Secondary observational | NEEDS_LOCAL_PRIVATE_PROBE | Delayed/history; not ES headline news |
| Finviz Elite | Equity news candidate | UNCONFIGURED | No live probe in Wave A |
| NewsAPI / Finnhub | Bounded live windows | Catalog + keys | Not historical PIT archives |
| Tradier / Alpaca paper | Fixture-only adapters | N/A | Sandbox tokens do not enable live HTTP in repo |
| Premium wires (Reuters, DJ, etc.) | Catalog only | EXT-NEWS | Not operational |

## ES / news gates

- **PASS:** canonical news fixtures, aggregator bridge, recorded-eval forward bridge, offline gap/readiness tooling.
- **FAIL:** observational live ingress, equity-scoped news → ES linkage, Finviz live news.
- **BLOCKED:** FTEP manifest owner decisions (OD-1–OD-11), Moomoo `US_FUTURES_QUOTE`, G-A6/G-A7 campaign binding, calibration numeric thresholds.

## Remaining blockers

1. Owner manifest decisions and manifest freeze (OD-11).
2. Local private probes: Moomoo OpenD, Finviz, G-A5 broker audit refresh.
3. External provider contracts for premium news and historical PIT archives.
4. Deferred: unified UI matrix, FTEP-ACT-04 live ingress, FTEP-ACT-06 auto-bridge.

## Commands (copy block)

```
python tools/provider_readiness.py audit --json
python tools/provider_readiness.py campaign-readiness FTEP-V1-001 --json
python tools/providers/capability_matrix.py --output artifacts/wave-a-findings/capability-matrix-snapshot.json
python tools/providers/snapshot_compare.py tests/fixtures/providers/frozen_compare_sample.json
```

## Doc anchor

`docs/engineering/PROVIDER_ACTIVATION_INCREMENT.md`
