# BUILD 27 Known Limitations Register

## KL-027-001 — Minimum forward paper sample not yet accumulated

- **Scope:** Paper execution qualification evidence
- **Why it exists:** BUILD 27 infrastructure can complete before sufficient live forward opportunities accumulate
- **Risk:** Disposition may be `INSUFFICIENT_PAPER_EXECUTION_EVIDENCE`
- **Mitigation:** Fixture lifecycle proves execution integrity; live accumulation continues separately
- **Blocking:** no

## KL-027-002 — BarConservativeSimulator not quote-touch fill

- **Scope:** Fill realism
- **Why it exists:** Canonical BUILD 22 path uses bar high/low, not top-of-book touch
- **Risk:** Fill may be more conservative than quote mid; documented as `BAR_CONSERVATIVE_FILL`
- **Mitigation:** Quote cross-check in qualification; ask/bid reference preserved separately
- **Blocking:** no

## KL-027-003 — Queue position unmodeled

- **Scope:** Fill realism
- **Why it exists:** No L3/order-queue model in v1 simulator
- **Risk:** Limit-order touch semantics not fully representative
- **Mitigation:** Explicit `QUEUE_POSITION_UNMODELED` limitation
- **Blocking:** no

## KL-027-004 — Zero-fee paper policy

- **Scope:** Accounting
- **Why it exists:** Paper ledger uses zero explicit fees by default
- **Risk:** Paper PnL omits real broker fees
- **Mitigation:** Documented; not live PnL
- **Blocking:** no

## KL-027-005 — Real Moomoo session may be unavailable locally

- **Scope:** Provider plane
- **Why it exists:** OpenD requires local gateway
- **Risk:** Bounded real-provider paper smoke may be `NOT EXECUTED`
- **Mitigation:** Fixture replay qualification path
- **Blocking:** no

## KL-027-006 — BUILD 26 forward sample may be insufficient

- **Scope:** Lineage
- **Why it exists:** Inherited BUILD 26 `INSUFFICIENT_FORWARD_EVIDENCE`
- **Risk:** Paper qualification binds BUILD 26 architecture, not necessarily large forward cohort
- **Mitigation:** Forward receipt lineage required when counting forward paper evidence
- **Blocking:** no
