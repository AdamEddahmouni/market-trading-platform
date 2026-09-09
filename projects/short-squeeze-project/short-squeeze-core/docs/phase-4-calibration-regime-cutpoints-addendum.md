# Phase 4 — Regime cutpoints and purge/embargo addendum (open item O-2)

**Status:** DRAFT — outcome-blind, written before any Phase 4 fitting; **pending
reviewer confirmation** (open item O-2 in the
[Phase 4 calibration preregistration](phase-4-calibration-preregistration.md)).
Fitting must not start until this addendum is confirmed.
**Version:** `phase_4_regime_addendum.v0.1-draft`

## 1. Outcome-blindness statement

All cutpoints and buffer values below were chosen from **public calendar references
only** and from the pre-registered acquisition design constants (the frozen-boundary
instant `2026-07-18T13:37:55Z` and the batch-05 boundary design date `2026-08-17`,
both recorded in the acquisition design docs before this addendum). **No dataset
boundary timestamps and no outcome labels were inspected** to choose these values.
Any amendment to this addendum must itself be outcome-blind and recorded in the
revision history before any fit.

## 2. Cited calendar

| Regime boundary | Date (UTC) | Citation |
|---|---|---|
| Meme episode (core reference) | January 2021 | U.S. SEC, [Staff Report on Equity and Options Market Structure Conditions in Early 2021](https://www.sec.gov/files/staffreport-equity-options-market-struct-condition-early-2021.pdf) (Oct 2021), documenting the Jan 21–28, 2021 episode |
| Start of the 2022 rate-hike cycle | **2022-03-16** | Federal Reserve FOMC statement — [first target-range hike](https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm) |
| First rate cut of the normalization cycle | **2024-09-18** | Federal Reserve FOMC statement — [first target-range cut](https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm) |

## 3. Regime slice partition (half-open intervals, UTC)

Every boundary time `t` belongs to exactly one slice:

| Slice | Interval `[start, end)` | Rationale (cited) |
|---|---|---|
| `pre-2020` | `t < 2020-01-01` | Calendar year boundary; pre-pandemic market structure |
| `meme-regime` | `2020-01-01 ≤ t < 2022-03-16` | Pandemic retail-trading surge era whose documented core is the Jan-2021 meme episode (SEC staff report); terminates at the first FOMC hike |
| `high-rate` | `2022-03-16 ≤ t < 2024-09-18` | Elevated-target-range era: from the first hike to the first cut (FOMC calendar) |
| `post-normalization` | `t ≥ 2024-09-18` | Era after the first rate cut (FOMC calendar) |

Membership rule: intervals are **half-open `[start, end)`** at **00:00:00 UTC**; a
boundary time exactly equal to a cutpoint belongs to the **later** slice.

Slice membership is assigned by **boundary time** (consistent with the chronological
walk-forward ordering in the preregistration §7). Empty slices (or slices with fewer
boundaries than the §8 feasibility minimum) are **reported as empty and never
padded, re-weighted, or silently dropped** (preregistration §6).

## 4. Purge and embargo values

- **Purge `w` = 30 calendar days** per training boundary.
- **Embargo `e` = 15 calendar days** per training boundary.

Rationale (outcome-blind sizing against the pre-registered design, not against the
data):

- The longest pre-registered forward horizon is 20 trading days (spec §9); 20 trading
  days ≈ 28 calendar days, so a 30-calendar-day purge clears the longest possible
  label window before the evaluation fold.
- The 15-calendar-day embargo adds a serial-correlation buffer beyond the purge
  (repeated-symbol boundaries are additionally grouped per ADR-0054, so whole symbol
  clusters never straddle a fold).
- Both values are in **calendar days from each training boundary time**, applied
  before the evaluation fold starts.

**Re-derivation rule:** if open item O-1 later extends the supported horizons, the
purge must be re-derived as `w ≥ longest forward horizon in calendar days + 2` (and
`e = w / 2`, rounded up) in a new outcome-blind addendum revision — the same formula
that yields the current fixed values (20 trading days ≈ 28 calendar days → `w` =
28 + 2 = 30, `e` = 30 / 2 = 15); the values in this addendum are fixed for the
current preregistered design.

## 5. Interaction with the other pre-registered rules

- Grouped symbol clusters (ADR-0054) are excluded from the evaluation fold regardless
  of purge/embargo arithmetic.
- Fold results are reported per fold and pooled; the pooled report is judged against
  preregistration §8 (C-1..C-3) with the regime slice breakdown reported as §6
  requires.
- The degeneracy gate (preregistration §7) still applies: if the chronological
  partition leaves fewer than two non-empty evaluation folds, the result is
  `NOT_CALIBRATED` and the degeneracy is named — no random or time-shuffled split is
  substituted.

## 6. Acceptance (open item O-2)

A reviewer can confirm that: (1) the cutpoints come from the cited public calendar
and were chosen without inspecting dataset timestamps or outcomes; (2) the slice
partition is exhaustive over all possible boundary times; (3) the purge/embargo
values cover the longest pre-registered forward horizon; and (4) any future change
requires a new outcome-blind revision recorded here.

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial outcome-blind draft: slice partition from SEC staff report + FOMC calendar; purge 30 / embargo 15 calendar days; re-derivation rule recorded |
| 2026-09-05 | Audit correction (v0.1-draft → no version bump needed, same date): re-derivation rule aligned to the formula that reproduces the fixed values (`w ≥ horizon calendar days + 2`, `e = w / 2` rounded up) so the rule is self-consistent with purge 30 / embargo 15 |