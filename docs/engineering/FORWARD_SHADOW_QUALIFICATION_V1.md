# BUILD 26 — Forward Shadow Qualification

> BUILD 26 evaluates the frozen BUILD 25 release candidate prospectively on data that arrives after the qualification run begins. It collects forward evidence but does not adapt the system being qualified.

## Core principle

```text
BUILD 25 = scientific/system release-candidate acceptance
BUILD 26 = prospective real-world shadow qualification
```

Forward evidence is evidence. It is not permission to mutate or trade.

## Forward vs replay

| Class | Meaning |
| --- | --- |
| `ACTUAL_FORWARD` | Prediction persisted before horizon with live/observational ingress |
| `REPLAY` | Deterministic reproduction from captured evidence |
| `COUNTERFACTUAL` | Synthetic what-if; never forward evidence |

Replay reproduction does not become an additional forward observation.

## Forward integrity

A forecast is eligible as forward evidence only when:

- forecast decision existed before target outcome
- ledger entry registered before target horizon completed
- input observations were available at decision time
- evidence class is `ACTUAL_FORWARD`
- no outcome was known at registration time

`ForwardPredictionReceiptV1` provides machine-verifiable receipts.

## Frozen system under test

Once a qualification run begins, the predictive system must remain frozen. Champion, policy, or feature-schema changes require a new run or explicit segmentation.

## Providers

See `artifacts/forward-qualification/BUILD26_PROVIDER_CAPABILITIES.json` for the runtime capability matrix.

Primary forward path: Moomoo/OpenD when `IMP_MOOMOO_LIVE=1` and OpenD is reachable. Fixture replay remains available for CI.

## Execution safety

```text
LIVE DATA ≠ LIVE TRADING
```

BUILD 26 requires:

- `execution_mode = NONE`
- `execution_authority = BLOCKED`

No broker orders. No real account mutation.

## Outcome timing

BUILD 15 settlement remains authoritative. No early labeling. Pending predictions remain visible in reports.

## Sample limitations

`INSUFFICIENT_FORWARD_EVIDENCE` is a valid scientific outcome. Thresholds are frozen in `ForwardQualificationSpecV1` and must not be weakened after observing results.

## Qualification vs promotion

A `ForwardQualificationReportV1` does not promote models, activate runtime, or authorize live execution.

`QUALIFIED ≠ live-trading authorization`

## Evidence handoff

```text
ForwardQualificationReport
  → BUILD 23 monitoring / drift
  → BUILD 24 ResearchTrigger
  → BUILD 17 ResearchFinding
  → BUILD 18 candidate
  → BUILD 19 validation
  → BUILD 20 promotion
  → BUILD 23 activation
  → new BUILD 26 qualification run
```

The current run never adapts itself.
