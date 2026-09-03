# BUILD 22 — Deterministic Paper Execution & Risk (V1)

> BUILD 22 converts an unexpired `OpportunityV1` into a deterministic trade proposal only after explicit paper portfolio/risk evaluation. Approval authorizes paper simulation only. It does not authorize or route a real broker order.

## Build boundaries

| Build | Responsibility |
| --- | --- |
| BUILD 21 | Opportunity authority — is there an eligible opportunity? |
| BUILD 22 | Paper execution authority — sizing, risk, paper order simulation |
| BUILD 23 | Monitoring, governance, rollback |

```text
OpportunityV1 → ExecutionPolicyV1 → PaperPortfolioSnapshotV1
  → TradeProposalV1 → RiskDecisionV1 → Paper Order → Paper Fill
```

## Input authority

Only `OpportunityV1` may initiate intelligent-engine trade proposals.

Forbidden:

- `ForecastV1 → TradeProposalV1`
- `SignalV1 → TradeProposal`
- LLM → order construction

## ExecutionPolicyV1

- Immutable, versioned, deterministic identity (`EXECPOL-{sha256}`).
- `mode = PAPER` only. Live-mode policies are rejected at construction.
- Default sizing: `FIXED_FRACTION_NAV_WITH_CAPS`.
- `trade_fraction_nav` defaults to `0.01` (1% of equity).
- Probability edge does **not** scale position size in v1.
- No Kelly sizing (directional probability alone is insufficient for payoff-aware sizing).

## Sizing

```text
base_notional = floor(equity_minor * trade_fraction_nav)
```

Then capped by (in order):

- `max_trade_notional_minor`
- `max_trade_fraction_nav`
- remaining position headroom (`max_position_notional_minor` / fraction)
- symbol concentration (`max_symbol_concentration_fraction`)
- gross exposure (`max_gross_exposure_fraction`)
- net exposure (`max_net_exposure_fraction`)
- available paper cash (long buys)

```text
quantity = floor(target_notional / reference_price_minor)
```

Reference price:

- LONG / BUY → ask
- SHORT / SELL → bid

Reference price is used for sizing/risk only. Paper fill price comes from the existing `BarConservativeSimulator` (bar high/low conservative model).

## Exposure

```text
gross = sum(abs(position market values))
net = sum(signed position market values)
```

Example: +50k long and -50k short → gross 100k, net 0.

## RiskDecisionV1

Decisions: `APPROVE`, `REDUCE`, `REJECT`, `FAIL_CLOSED`.

- Requested size is preserved on `TradeProposalV1`.
- Approved size is on `RiskDecisionV1` only (proposal is never mutated).
- Reduction requires `allow_size_reduction = true` on policy.

Opportunity expiry: at `decision_time_ns >= valid_until_ns` → reject (exact boundary expired).

## Paper integration

Reuses platform P1 paper ledger (`PaperExecutionLedger`, `submit_interactive_order`).

- No duplicate paper ledger.
- Idempotency key derived deterministically from `RiskDecisionV1`.
- `execution_authority` must be in `PAPER_EXECUTION_AUTHORITIES` (`AUTHORIZED`, `PAPER_ONLY`).
- No IBKR/Moomoo/Tradier/tastytrade order APIs in BUILD 22 path.

## Cash / short policy (v1 limitations)

- Cash-only long purchases (no margin model).
- Short selling disabled by default (`allow_short = false`).
- No borrow availability fabrication.
- Daily loss guard when `start_of_day_equity_minor` is present on portfolio snapshot.

## Temporal integrity

Forbidden pre-trade / fill inputs:

- `OutcomeV1`
- future terminal prices
- BUILD 15 settlement target prices

Portfolio snapshot must satisfy `captured_at_ns <= risk_decision_time_ns`.

## Persistence

Intelligence repository stores:

- `execution_policies`
- `paper_portfolio_snapshots`
- `trade_proposals`
- `risk_decisions`

Paper orders/fills remain in the canonical paper execution ledger.

## BUILD 23 handoff

BUILD 23 can consume immutable BUILD 22 records for telemetry, drift monitoring, champion health, anomaly detection, and governed rollback without rewriting historical proposals, risk decisions, or paper fills.
