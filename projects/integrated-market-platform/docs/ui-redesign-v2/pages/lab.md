# LAB — `/lab` (+ `/lab/validation`, `/lab/simulation`, `/lab/chart-lab`)

## Purpose

IMP's operator-facing experimental workbench: configure/inspect governed
research and testing workflows, understand what can actually be run, and hand
results to Research. Landed on current contracts (UIR-01H). Contract map:
[lab-contract-map.md](../lab-contract-map.md).

Lab is **process**. Research is **interpretation**. Same GET payloads; different
jobs. **NO LAB MUTATIONS.**

## Primary user questions

1. What experiment or validation workflow am I working on?
2. What is being tested?
3. What recorded inputs/configuration govern it?
4. What can actually be run from this interface? (Nothing on the UI API.)
5. What evidence/result currently exists?
6. What remains pending or unavailable?
7. What does this result prove — and what does it not prove?
8. How does the result flow back into Research?

## Information hierarchy

- **L1:** workflow identity, availability (Read-only / Local tooling / Not yet available), current snapshot summary.
- **L2:** recorded target, methodology, assumptions.
- **L3:** concise result + Research handoff. Compact outcome tables; interpretation stays in Research.
- **L4:** hashes, raw epistemic/authority values, JSON specs (`<details>`).

## Routes

| Route | Section | Fetches |
|---|---|---|
| `/lab` | Overview | models + simulation |
| `/lab/validation` | Validation workbench | models |
| `/lab/simulation` | Simulation workbench | simulation |
| `/lab/chart-lab` | Chart adapter playground | none |

`/research/vela-chart-lab` redirects to `/lab/chart-lab`. `/lab` no longer
redirects to Research.

No empty Methodology, Runs, or FTEP tabs. Those appear as disclosures or
Overview gaps.

## Interactions

- Tabs are routes (`LinkTabs`).
- Research links: `/research/validation`, `/research/simulation`.
- Chart Lab tick-sim/backfill remain local React state.
- No Run / submit / cancel / retry buttons for validation or simulation.

## States

- Loading / error per workbench (humanized `ErrorState` + retry = refetch).
- Empty: no interpretation rows / no fills — honest cutoff language.
- Demo / Paper / Live: same workflows; mode notes only. Live data ≠ Live experiment authority.

## Data dependencies

- `queryKeys.researchModels`, `queryKeys.researchSimulation` unchanged.
- Chart Lab: local synthetic feed.

## Acceptance

1. `/lab` is a useful workbench; nav Lab ≠ Research.
2. Only real workflows shown; FTEP/hypotheses explicit gaps.
3. Simulation not labeled FTEP; validation not production readiness.
4. Evidence class/raw boundary preserved in L4.
5. Bundle: Lab lazy; Vela stays off the entry chunk.
