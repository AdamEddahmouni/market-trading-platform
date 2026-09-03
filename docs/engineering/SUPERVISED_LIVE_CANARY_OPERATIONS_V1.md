# Supervised Live Canary Operations (BUILD 30)

BUILD 30 proves **repeated human-supervised canary operation**. It does **not** reduce human authorization or confirmation requirements and does **not** enable autonomous live trading.

## Core principle

> Operational maturity is demonstrated when safety controls remain intact after repetition, failure, restart, and ambiguity—not when those controls are gradually removed because earlier canaries happened to succeed.

## Authority hierarchy

```text
Program policy ≠ session authorization
Session authorization ≠ order confirmation
Order confirmation ≠ risk approval
Risk approval ≠ broker submit
```

All remain required for every live order.

## Program policy vs session authorization

`LiveCanaryProgramPolicyV1` defines the **upper operational envelope**:

- max sessions
- cumulative order count
- cumulative notional
- cooldown between sessions
- incident halt rules
- program expiry

It does **not** authorize orders. Every session still requires:

1. `CanaryAuthorizationPreviewV1`
2. explicit human approval
3. `LiveExecutionAuthorizationV1` bound to that preview

## Per-order confirmation

Per-order human confirmation remains mandatory across all BUILD 30 sessions. Stale confirmations are invalidated on restart; fresh confirmation is required before any submit after restart.

## Program caps

Program-level caps accumulate across sessions. Successful sessions **cannot** increase caps. Final allowable exposure is the most restrictive of:

- BUILD 22 risk
- BUILD 29 canary policy
- session authorization
- BUILD 30 program cap
- reconciled account state

## Session boundaries

Before every session:

- program active and not expired
- cooldown satisfied (eligibility only—not auto-start)
- fresh broker health
- fresh account identity
- clean reconciliation checkpoint
- no ambiguous prior submission
- no unexplained broker order
- kill switch known
- fresh human authorization

After every session:

- orders, fills, positions, open orders reconciled
- authorization consumed/disabled
- session report emitted

Unresolved ambiguity keeps the session in `SESSION_RECONCILING` or pauses the program.

## Incident policy

Incident types include broker disconnect, account mismatch, ambiguous submission, broker-only/local-only orders, unexpected fills, reconciliation failure, cap violation attempts, and external account activity.

| Severity | Default actions |
| --- | --- |
| INFO | LOG_ONLY |
| WARNING | LOG_ONLY, RECONCILE_REQUIRED |
| CRITICAL | BLOCK_NEW_SUBMITS, MANUAL_REVIEW_REQUIRED, HALT_PROGRAM |

Critical incidents do not auto-resume. Resume requires incident resolution evidence, clean reconciliation, and `LiveOperationalResumeApprovalV1` when configured—resume approval does not authorize an order.

## Reconciliation checkpoints

`LiveReconciliationCheckpointV1` records matched, local-only, broker-only, and conflict sets at session boundaries. Session N+1 requires a fresh clean checkpoint—not assumption that the prior order finished.

## Restart safety

On restart:

- load program/session state
- reconcile broker/account state
- remain blocked for new submits
- invalidate stale confirmations (default)
- kill switch unknown state = BLOCK

## External activity

Manual broker orders and position changes are detected as external activity. They pause progression and require human review—they are not silently adopted into platform lineage.

## Program completion

At program completion or expiry:

- live canary program authority expires
- new live submissions disabled
- kill switch blocks program scope

A later program requires new governance.

## Performance limitation

Repeated supervised micro-canaries are too controlled and small to prove scalable live strategy performance. Live PnL does not tune strategy, retrain models, or promote champions.

## Next boundary (BUILD 31 — not implemented)

A future BUILD 31, if justified, should focus on operator control plane, multi-session observability, broker incident drills, and reconciliation dashboards—not removal of human approval.
