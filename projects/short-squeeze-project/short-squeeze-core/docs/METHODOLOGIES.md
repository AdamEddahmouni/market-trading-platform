# Methodologies

## Legacy Prime Setup

A preserved baseline projection used for comparison. Its result is independent of
the canonical research policy.

## Peer Reference Methodology

A generic reference profile. It reports
`REFERENCE_DEFINITION_INCOMPLETE` when a supplied definition cannot be evaluated
without inventing evidence.

## Evidence-Gated Prime v1

Machine identifier: `adam_evidence_gated_prime.v1`.

The identifier remains stable for API compatibility; the organization-neutral
display label is **Evidence-Gated Prime v1**. The methodology evaluates only
admissible evidence and preserves unknown or conflicted results.

### Pressure dimension (65% minimum weight)

| Component | Weight | Normalization | Real-time source |
|---|---|---|---|
| Published SI % | 30 | linear(5, 30) | Finviz Elite Short Float % |
| Days to Cover | 25 | linear(1, 7) | Finviz Elite Short Ratio |
| Cost to Borrow | 20 | linear(2, 50) | IBKR borrow fee (not implemented; requires verified API mechanism and entitlement) |
| Borrow Avail % Float | 15 | inverse_linear(0.1, 10) | IBKR shortable shares / Finviz float |
| Float Shares | 10 | inverse_linear(10M, 50M) | Finviz Elite Shares Float |

### Ignition dimension (65% minimum weight)

| Component | Weight | Normalization | Real-time source |
|---|---|---|---|
| Current % Change | 35 | linear(0, 20) | IBKR canonical `PERCENTAGE_RETURN` |
| Relative Volume | 30 | linear(1, 10) | Finviz Elite Relative Volume |
| Bar Acceleration | 20 | linear(0, 5) | Computed from IBKR bar returns |
| Catalyst Age | 15 | step(24h, 72h) | News headlines / SEC filing `filed_at` |

### Classification thresholds

| Classification | Conditions |
|---|---|
| PRIME | Pressure >= 70, Ignition >= 70, HIGH coverage (85%+) |
| SUBPRIME | (Pressure >= 70 AND Ignition >= 50) OR (Ignition >= 70 AND Pressure >= 50) |
| WATCH | Pressure >= 50 OR Ignition >= 50 |
| NOT_QUALIFIED | Both dimensions below 50, sufficient evidence |
| UNEVALUABLE | Insufficient evidence (< 65% supported weight in either dimension, or a critical domain missing) |
| CONFLICTED | Material provider conflicts in evidence inputs |

### Scoring behavior (0.16.0)

- The evidence-gated floor is aligned to Finviz-supported weight (**65%**), so
  `LOW_COVERAGE` alone does not force `UNEVALUABLE` when both dimensions score.
- Finviz mapping conflicts are **withheld** from scoring rather than silently merged.
- Estimated DTC (from Short Float / Avg Volume) and Finviz day-change remain
  **display-only** when IBKR canonical return is missing.
- Borrow availability % float is **research-admissible** only when both IBKR and
  Finviz legs are eligible.

### Real-time evidence availability

With Finviz Elite configured: Pressure 65/100 (SI + DTC + float) meets the
minimum dimension weight and is evaluable when Ignition also scores. Pressure
reaches 80/100 when IBKR borrow availability is also available.

With Finviz Elite + full IBKR entitlements: both dimensions evaluable.

## Canonical Phase 3A

Canonical Phase 3A is a transparent, preregistered rule evaluation. Missing
evidence is `UNKNOWN`, not `FAIL`. Provider display fields do not become canonical
inputs without matching semantics, time basis, units, and provenance.

## Canonical research detection

Research detection is distinct from outcome confirmation and predictive
validation. The frozen demonstration remains outcome-incomplete and unevaluable
as a predictive claim. Offline Phase 3E stage acquisition for historical cohorts
does not change that product limitation—see [reproducibility.md](reproducibility.md).
