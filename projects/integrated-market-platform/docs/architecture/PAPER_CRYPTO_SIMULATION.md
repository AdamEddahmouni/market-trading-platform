# Paper crypto sizing and simulated short policy release

Owner-approved and serving as of 2026-10-28 19:13 UTC. Development runtime sources remain unchanged at `d192eb52`; serving base is `75ab7f3a` plus the retained overlay. Previous versions are under execute/draft-preimages.

## Application order

1. A.patch on d192eb52: fractional venue minimums, optional crypto notional caps, unchanged equity/ETF share caps, fractional long accounting, server-sized capped exits.
2. **B.patch depends on A.patch**: explicit default-off simulated crypto shorts, exact fractional open/cover/borrow accounting, account-scale short valuation, separate crypto margin terms, reservation correction and maintenance retries.
3. Amended IMP-009-with-tests.patch: superseded-run handle ownership fix. It needs no historical store mutation.

The final A → B → IMP-009 application is byte-identical to the tested/deployed 17-file candidate (`execute/final-package-check.json`). EXTENSION.patch is the cumulative release artifact. No draft source patch was applied to the development checkout.

## Approved frozen terms

The owner approved $5,000 per-order and per-position crypto notional caps (500000 account minor units), 100% additional collateral (10000 bps), 50% maintenance (5000 bps), and 43.8% annual simulated borrow (4380 bps, 365-day accrual, rounded up to account minor units). The new account starts at $100,000 simulated cash. These are simulation assumptions; no real venue borrow or broker authority is granted.

Creation is explicit: allow_short=true, allow_crypto_short=true, plus both crypto_notional_caps fields. Absent crypto terms, previous policies/accounts keep their prior identity and behavior; opting in changes the frozen hash and requires a new account. The old account was closed with no exposure and its history remains. Existing automation scopes/risk controls were copied and compared field by field. US_ETFS remains off.

Covers use current account-scale market_value_minor and fractional quantities, with the frozen terms consistently used for admission, collateral, maintenance and borrow. Reversals and missing opt-in remain rejected. Equity/ETF price, SSR, margin/borrow rules and Paper authority checks remain intact.

## Verification

Combined candidate: 432 tests pass in 16 suites; all suite logs are execute/final-*.txt. Standalone A final focus: 68 pass; B crypto-short focus: 21 pass. Original B and IMP-009 failures remain in prior receipts. Both normal long/short exits above the cap failed first (execute/exit-red-test_paper_crypto_shorts.txt), then passed through the canonical controller → Action handoff → preview → submit path in two separate capped decisions. Exact accounting, fractional open, partial/full cover, margin, borrow, reversal rejection, missing-policy rejection and existing equity/crypto-long compatibility are covered.

Independent release review completed with no further important defect. Backend process quiescence was enforced before module replacement and account replacement. The manifest verifies 2,319 files; frozen-account-verified.json establishes approved crypto terms directly from the stored policy because the experiment API omits some crypto fields.

## Limits and rollback

Full validate changed and execution-path checkpoint are deferred until after 20:00 Eastern and must be compared to the recorded baseline. New suites were directly invoked; integration with the normal validation inventory belongs to development integration. Controlled fixtures do not prove natural crypto fills or strategy performance. Venue minimums can leave dust; mark-to-order price movement can reject a close; fees accrue on the existing session-date transition. The experiment API's crypto-term visibility is a deferred minor and read-only stored-policy evidence is retained.

Rollback source/manifest copies are execute/extension-preimages. A new crypto-enabled account must remain stopped if rolling code back to an older implementation. Runtime rollback does not undo a frozen account or its history. Historical audit repair is separately documented and backed up; it is not a financial correction.

## Crypto close residuals (exit series, serving since 2026-10-29 02:44 UTC)

**Closable remainder.** A capped crypto exit is sized so that whatever stays open can still be closed by venue-valid orders. Each order is at least the instrument's minimum quantity and minimum notional, and at most the frozen crypto order cap. When the whole position can be split into such orders, sizing keeps the remainder splittable. When no legal split exists, sizing returns zero and the preview fails closed.

**Residual guard at execution.** The simulator checks a reducing crypto fill against the position's remaining quantity at the **actual fill price**.
- A full-size fill (not limited by print participation) that would leave a nonzero residual below the venue minimum quantity or minimum notional is rejected with `SIM_CRYPTO_CLOSE_RESIDUAL_BELOW_MINIMUM`. A rejection changes no cash, position or print capacity. The controller's existing backoff and a fresh decision handle the retry.
- A fill already limited by print participation is trimmed to the largest step-aligned quantity that leaves a legal residual. It is rejected only if that trim would fall below the venue minimum quantity. A trimmed fill is an ordinary `PARTIALLY_FILLED` order, and the controller cancels the unfilled remainder.

**Limits.** These checks use actual execution evidence, not future prices. A later price move can still make a remaining position fall below the minimum notional. With liquidity below one legal lot, an exit waits at a legal position. Like other partial fills, a partial or trimmed fill may be below the minimum notional. Non-crypto instruments are unaffected.

**Owner decisions of 2026-10-29 (after the fresh-context review):**
- *Residual buffer.* Capped sizing and the participation trim leave the minimum notional **plus 2%** (`CRYPTO_RESIDUAL_NOTIONAL_BUFFER`), so one lower print cannot strand the remainder. When the buffer would leave no legal split or trim, the exact minimum is used instead, so the buffer never makes a closable position unclosable. Legality checks still use the exact venue minimum.
- *Trim visibility.* A trimmed close carries the informational reason code `SIM_CRYPTO_CLOSE_TRIMMED_TO_LEGAL_RESIDUAL`; the order is still `PARTIALLY_FILLED`.
- *No opening dust.* A participation-limited opening (or adding) fill that would leave a position below the minimum notional at its fill price is not made (`SIM_NO_ELIGIBLE_VOLUME`).
- *Close sizing faults.* A bad instrument field while sizing an automation close blocks that close (`PAPER_CLOSE_SIZING_*`), not the whole cycle.

## Unplanned equity carry and the crypto scope (owner decision 2026-10-29)

An unplanned US equity carry (an automation position left open over a close it was not approved to carry) holds back **equity-session** entries until it is closed at the next open. The continuous crypto scope keeps trading; every portfolio-level gate (valuation, exposure, daily loss, short margin, working orders) still applies to it.

## Held equity quotes (serving since 2026-10-29 03:50 UTC)

Held equities keep their own `paper-portfolio-marks` quote subscription on every portfolio-mark pass, whether or not a cached mark exists. Before this, a held equity whose candidate subscription was released kept a stale cached mark and was never resubscribed, so market exits found no post-intent L1 event (`SIM_NO_POST_SIGNAL_BAR`). On 2026-10-28 that exhausted RCL's six end-of-day closes and left an unplanned carry that blocked all entries. Quota refusals are still recorded, never worked around; crypto marks are unchanged.
