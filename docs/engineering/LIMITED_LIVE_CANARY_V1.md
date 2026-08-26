# Limited Live Canary V1 (BUILD 29)

> **BUILD 29 authorizes only a temporary, explicitly human-approved micro-notional live canary. It does not enable autonomous or generally available live trading.**

## Core Principle

```text
BUILD 28 = pre-live safety certification
BUILD 29 = human-authorized micro-notional live canary
BUILD 29 ≠ general live trading
BUILD 29 ≠ autonomous live trading
```

A successful canary proves containment under human supervision. It is not permission for unrestricted live trading.

## Human Gates

BUILD 29 requires two independent human gates:

1. **Canary envelope authorization** — operator reviews `CanaryAuthorizationPreviewV1` and explicitly approves exact caps, broker, account, symbol scope, and duration.
2. **Per-order confirmation** — operator confirms each exact `BrokerOrderIntentV1` before submission.

No single API may prepare, authorize, and submit silently.

## Absolute Caps

First-canary limits are **absolute micro-notional caps**, not NAV-scaled:

- Default max single-order notional: $25.00
- Default max total canary notional: $25.00
- Default max order count: 1

Account equity, buying power, and model confidence can only **reduce** approved size — never increase it.

## Live Account Safety

Real account state is used only for:

- live risk overlays
- authorization validation
- reconciliation

It is **not** predictive model input. More buying power does not grant permission to size larger.

## Ambiguous Submission

If transport outcome is unknown (`SUBMISSION_STATUS_UNKNOWN`):

```text
NO BLIND RESUBMIT → RECONCILE FIRST
```

## External Broker Activity

Manual trades outside the platform appear as broker-only state. Unexplained broker orders in authorized scope block new canary submissions.

## Auto-Disable

After canary completion, order-count exhaustion, authorization expiry, or critical error:

```text
live submission capability → DISABLED
```

Authorization is consumed and cannot be silently reused.

## No Autonomous Live Loop

Models, LLMs, agents, and forecasts cannot:

- authorize a canary
- confirm orders
- raise caps
- clear the kill switch

Global kill switch remains `ACTIVE_BLOCK`; canary uses a narrowly scoped temporary permit only.

## Contracts

| Contract | Purpose |
| --- | --- |
| `LiveCanaryPolicyV1` | Immutable canary envelope with absolute caps |
| `CanaryAuthorizationPreviewV1` | Human-reviewable preview before authorization |
| `HumanCanaryApprovalV1` | Recorded explicit human canary approval |
| `LiveExecutionAuthorizationV1` | Temporary authorized state bound to preview |
| `LiveOrderConfirmationV1` | Per-order human confirmation |
| `LivePortfolioSnapshotV1` | Broker-observed safety snapshot |
| `BrokerSubmissionReceiptV1` | Immutable submit evidence |
| `LiveFillReceiptV1` | Broker fill evidence |
| `LiveCanaryRunV1` | Canary run manifest |
| `LiveCanaryQualificationReportV1` | Final qualification disposition |

## Dispositions

- `CANARY_NOT_EXECUTED` — no real order (no authorization, no opportunity, or blocked)
- `CANARY_EXECUTED_CLEAN` — authorized mock/real canary completed and reconciled
- `CANARY_EXECUTED_WITH_LIMITATIONS` — executed with known limitations
- `CANARY_HALTED_SAFE` — halted without integrity violation
- `CANARY_INVALID_RECONCILIATION` — reconciliation failure
- `CANARY_INVALID_EXECUTION_INTEGRITY` — execution integrity failure

Never: `AUTONOMOUS_LIVE_TRADING_APPROVED`
