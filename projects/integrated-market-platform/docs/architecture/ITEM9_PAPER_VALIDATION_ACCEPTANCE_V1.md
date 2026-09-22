# Item 9 Paper Validation Acceptance V1

**Document ID:** `ITEM9_PAPER_VALIDATION_ACCEPTANCE_V1`

**Classification:** `CURRENT_CANONICAL_ARCHITECTURE`

**Schema:** `item9.paper-validation-acceptance/1.0.0`

**Bound protocol:** `item9.calibration-protocol/1.0.0`

**Status:** Pre-registered acceptance contract. **Not** `PAPER_VALIDATED`.
**Not** `CALIBRATED`. **Not** Full30. Live remains **OFF**.

Executable companions:

- `manifests/paper/item9_paper_validation_acceptance_v1.json`
- `manifests/paper/item9_prospective_paper_run_package_v1.json`
- readiness / preflight vocabulary in
  `src/market_platform_foundation/paper/calibration/item9_validation_readiness_contract.py`

Parent docs: [ITEM9_CALIBRATION_PROTOCOL_V1.md](ITEM9_CALIBRATION_PROTOCOL_V1.md),
[PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](PAPER_SIMULATOR_CALIBRATION_CONTRACT.md),
[PAPER_DECISION_LIFECYCLE.md](PAPER_DECISION_LIFECYCLE.md),
[IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md](IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md).

## Lifecycle (independent; never auto-promote)

```text
CALIBRATED
  → PAPER_VALIDATION_READY
  → PAPER_EMPIRICAL_ACTIVE
  → PAPER_VALIDATION_COMPLETE
  → PAPER_VALIDATED
```

Each arrow requires an explicit governed transition. Preflight readiness
(`ITEM9_CALIBRATION_READY_AWAITING_AUTHORIZATION`) is **not** `CALIBRATED`
and does **not** enter this ladder.

## Pre-registered minimums

Numeric floors that the repository has not yet governed stay
`UNSET/BLOCKING`. This document does **not** invent a passing N.

| Requirement | Policy |
|---|---|
| Forward opportunities | `UNSET/BLOCKING` |
| Fills | `UNSET/BLOCKING` |
| Sessions | `UNSET/BLOCKING` |
| Strategy coverage | `UNSET/BLOCKING` |
| Missing-evidence ceiling | `UNSET/BLOCKING` |
| Cost / fill models | Required when both sides report; otherwise `NOT_OBSERVABLE` |
| Settlement completeness | Required |
| Drawdown / return / hit-rate reporting | Required |
| Calibration-vs-forward degradation reporting | Required |
| Rejection / catastrophe / stop conditions | Required |

## Prospective run package

`item9.prospective-paper-run-package/1.0.0` is a **template**, not a started
session. It pre-declares manifest, immutable config, strategy and provider
requirements, universe, start/stop, risk, cost, fill, settlement, evidence
capture, opportunity and operator logs, order-ready / fill / position /
outcome lineage, attribution, diagnostics, and end-of-session seal.

## Lineage honesty

Reconstruct:

`raw observation → EventV1 → analysis → strategy candidate → OpportunityV1 →
thesis → operator decision → risk → order_ready → Paper order → fill →
position → monitoring → outcome → settlement → attribution`

using existing contracts (including OrderReady opportunity lineage). Missing
links stay `NOT_OBSERVED`. Strategy IDs on historical Mode B bar receipts stay
`NOT_APPLICABLE`.

## Prohibitions

- No auto-promotion across Paper states
- No claim of `PAPER_VALIDATED`, `FULL30_COMPLETE`, or `LIVE_READY` from this
  registration alone
- No fitting; `fitting_allowed` stays false
- Live execution stays OFF
