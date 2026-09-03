# External donor/reference index

Revision 3 is authoritative if this index conflicts with it. The workspace root
is a collection; the seven entries below are external donor/reference projects,
not canonical repositories, clean-clone dependencies, package dependencies, or
runtime dependencies. They remain outside `integrated-market-platform/`.

| # | Exact observed collection path | Reference value | Governed note |
|---:|---|---|---|
| 1 | `Eric_futuresX-main` | futures, depth, sessions, replay, and execution experiments | external collection note only |
| 2 | `tradingCVDBubble-main (1)` | CVD, OFI, aggressor and depth measurements | external collection note only |
| 3 | `short-squeeze-project` | provenance, freshness, missingness, and readiness gates | external collection note only |
| 4 | `internship-project-main` | news/options workflow, audit, liquidity, and paper evaluation | external collection note only |
| 5 | `L1VolumeBubble-main (1)` | volume-anomaly and absorption visualization | external collection note only |
| 6 | `DS-340W-Fantasy-Football-Prediction-main/DS-340W-Fantasy-Football-Prediction-main` | time-series model and robustness research patterns | [DS340W_NOTES.md](DS340W_NOTES.md) |
| 7 | `DS-440-CAPSTONE-GridIQ-main/DS-440-CAPSTONE-GridIQ-main` | dataset, cache, API, UI, persistence, and grounded-chat patterns | [GRID_IQ_NOTES.md](GRID_IQ_NOTES.md) |

The complete component classification is in
[DONOR_REUSE_MATRIX.md](DONOR_REUSE_MATRIX.md). Conservative rights states are
in
[the donor permissions record](../../superpowers/governance/2026-08-14-donor-code-permissions.json).

## Boundary rules

- Do not edit, move, rename, stage, initialize Git in, or normalize a donor.
- Do not run donor entry points, installs, migrations, remote fetches, or AI calls.
- Do not copy donor data, outputs, private databases, credentials, or source code.
- Reuse begins from an accepted ADR, rights/provenance evidence, a separately
  authorized phase, canonical semantics, and verification—not donor proximity.
- `PORT_ADAPT` means independent reimplementation; ambiguity defaults to
  `CONCEPT_ONLY` or `DO_NOT_USE`.
