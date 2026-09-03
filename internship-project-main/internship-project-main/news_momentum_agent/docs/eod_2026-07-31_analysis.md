# EOD near-miss analysis — 2026-07-31

Session-level look at whether the **confidence** (and related LOG) gates filtered in a useful direction. Source of truth: [`../state/near_miss_eod_2026-07-31.json`](../state/near_miss_eod_2026-07-31.json) (also embedded under `near_miss` in [`../state/eod_summary_2026-07-31.json`](../state/eod_summary_2026-07-31.json)). Tracker detail: [`../state/near_miss_tracker_2026-07-31.json`](../state/near_miss_tracker_2026-07-31.json).

This is **suggestive evidence from one paper session**, not a validated edge study.

---

## What near-miss tracking is

When the live agent decides **LOG** (no trade) for a gated reason such as `low_confidence` or `liquidity_reject`, the near-miss tracker still looks up a would-be ATM contract, records an entry mark when quotes allow, and later applies the **same TP/SL / flatten rules** as live options exits — without placing an order. Outcomes are labeled `would_have_won`, `would_have_lost`, `would_have_flattened_flat`, or `unknown`.

That rejected pile is exactly what you want to inspect after a gate change: if the filter is doing real risk work, the shadows should skew toward losers, not winners.

---

## Today's numbers (actual)

**Headline:** `138 near-misses (56 low_confidence, 82 liquidity_reject)`  
**With a usable entry quote for shadow follow-up:** **80** of 138.

### By reject reason

| Reason | Count |
|--------|------:|
| `liquidity_reject` | 82 |
| `low_confidence` | 56 |

### Low-confidence shadow outcomes (aggregate)

| Outcome | Count |
|---------|------:|
| `would_have_lost` | **26** |
| `would_have_won` | **8** |
| `would_have_flattened_flat` | 15 |
| `unknown` | 7 |

Among decisive win/loss labels (**26 lost vs 8 won**), that is roughly **3.25:1 against** the rejected low-confidence set — losers dominate.

### Confidence bands (always with N)

| Band | N | would_have_won | would_have_lost | flattened | unknown | hit_tp |
|------|--:|---------------:|----------------:|----------:|--------:|-------:|
| **0–44** | **55** | 7 | **26** | 15 | 7 | 7 |
| 45–59 | 0 | 0 | 0 | 0 | 0 | 0 |
| 60–64 | 1 | 1 | 0 | 0 | 0 | 1 |

The **0–44** band is the main story: **N=55**, **26 would_have_lost vs 7 would_have_won** (~**3.7:1** against inside that band). Almost every low-confidence near-miss with a scored band sat here — which matches a sample-size-penalized formula that keeps thin-evidence setups from looking “high confidence.”

The single **60–64** name (N=1) would have hit TP. That is interesting as a possible false-negative anecdote, **not** a rate — N=1 cannot move the gate.

EOD trade-log rejection tallies the same day (`eod_summary`): `liquidity_reject` 63, `low_confidence` 53, `log_other` 1 — same direction as the near-miss reason split (counts differ slightly because EOD aggregates decision rows and near-miss has its own cooldown/eligibility rules).

---

## Why this matters (plain language)

A risk gate that filters candidates **should** leave a rejected pile that skews toward losers. That is the point of the filter.

- If rejected shadows were **even** win/loss, or worse **more winners than losers**, that would argue the confidence threshold is **too strict** — blocking good trades along with bad ones.
- Today's skew (**losers >> winners** among low-confidence shadows) is the signature of a gate that looks **correctly cautious**, not reckless (trade everything) and not obviously over-blocking on this one session's sample.
- It does **not** by itself prove profitability of the trades that *did* clear (TGB / NWL / COIN on this day were still a **losing** paper session overall). It only speaks to whether the **filtered-out** mass looked toxic in shadow space.

---

## Link to the confidence-formula fix

Earlier in the week, thin agreement (small `n_dir`) could still look “confident enough,” which helped produce bad paper outcomes (including painful Path B / liquid-name episodes such as **QQQ / IWM**-style losses that motivated tightening evidence requirements). The fix was a **sample-size penalty**:

`sample_factor = min(1, max(0, n_dir − 1) / 3)`  

so **n_dir=2** cannot clear a high Path B bar on agreement alone.

Today's near-miss pile is the first **session-level, quantitative** check that the fixed formula is filtering in the intended direction: the setups that stayed in **0–44** confidence and were LOGed would mostly have been shadow losers under the same exit rules. That closes a loop — **bug found → formula fixed → one day's rejected pile skews the right way** — without claiming the fix is fully validated.

Liquidity rejects (82 of 138) are a separate gate; many never get a fair shadow mark (`no_0dte_chain_exists`, stale quote, empty chain). Those support the “small-cap news ≠ tradeable options” lesson more than the confidence math.

---

## Caveats (do not overstate)

1. **One day.** Even with N=55 in the largest band, a single session is not durable calibration. The research pipeline already requires **N≥30** and **chronological out-of-sample** checks before calling a pattern real; gate evaluation deserves the same multi-session bar before “confirmed.”

2. **Shadows ≠ fills.** Labels use mid/mark-style follow-up and the same TP/SL rules as paper exits. They do **not** fully capture slippage, NBBO, or the exact quote/spread noise behind the live **COIN** stop (−$410 in ~48s). Directionally informative; not as precise as realized P&L.

3. **Precision ≠ recall.** More would-have-losers than winners among rejects is good for **precision of avoidance** (dodging bad trades). It does **not** measure **false negatives** (good setups blocked). The lonely 60–64 TP hit is a reminder that question is open. Answering it needs more sessions and the same N-floor / OOS discipline as the pattern miner.

4. **Paper book still not profitable.** Gate health on rejects does not erase underwater TGB/NWL marks or the COIN loss. Treat this write-up as gate diagnostics, not a performance claim.

---

## What to do with this next

- Keep exporting `near_miss_eod_*.json` every session and track **0–44 lost:won** (with N) over weeks.
- Only then consider moving confidence thresholds — not after one green-looking skew day.
- Prefer evaluating confidence and liquidity gates **separately** (today’s 56 vs 82 split already shows both are busy).
- When the parent stocks/futures project reuses these gates, copy the **near-miss discipline**, not just the formula constants.

---

*Generated from live state files for handoff. Numbers above match `near_miss_eod_2026-07-31.json` as of the session write.*
