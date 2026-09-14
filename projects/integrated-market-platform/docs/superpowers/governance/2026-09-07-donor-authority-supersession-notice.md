# Donor Authority Supersession Notice

**Status: CURRENT** (2026-09-07; amended 2026-09-14) · **Classification:**
`GOVERNANCE` · **Truth class:** `CURRENT_CANONICAL_TRUTH`

## What changed

The professor corrected the donor identity on 2026-08-28: the donor materials
that were believed to come from Lucas Bichara actually came from **Lucas
Heller** — and Lucas Heller's DS-340W and GridIQ materials were **not**
intended donors for this platform. Every governance record below predates that
correction and must no longer be read as current authorization.

## Superseded records (authorization basis superseded)

| Record | Path | Disposition |
|---|---|---|
| Donor code/data permissions record | `docs/superpowers/governance/2026-08-14-donor-code-permissions.json` | SUPERSEDED — annotated in place |
| ADR-DONOR-001 component disposition | `docs/superpowers/decisions/2026-08-15-adr-donor-001-component-disposition.json` | SUPERSEDED — historical record; preserved byte-for-byte to satisfy the Phase 1 decision-bundle hash binding; this notice is the current disposition |
| ADR-GRIDIQ-001 port-adapt patterns | `docs/superpowers/decisions/2026-08-16-adr-gridiq-001-port-adapt-patterns.json` | SUPERSEDED — annotated in place |
| GridIQ port phase gate | `docs/superpowers/governance/2026-08-16-gridiq-port-phase-gate.json` | SUPERSEDED — annotated in place |
| Donor reuse matrix | `docs/research/donors/DONOR_REUSE_MATRIX.md` | SUPERSEDED — annotated in place |
| GridIQ notes | `docs/research/donors/GRID_IQ_NOTES.md` | SUPERSEDED — annotated in place |
| DS-340W notes | `docs/research/donors/DS340W_NOTES.md` | SUPERSEDED — annotated in place |
| External donor/reference index | `docs/research/donors/README.md` | SUPERSEDED — annotated in place; Heller rows re-attributed as mistaken transfers |
| Revision-3 donor integration plan | `docs/superpowers/plans/2026-08-14-revision-3-donor-integration-and-evidence-transition.md` | SUPERSEDED — annotated in place |
| Phase 0A donor characterization plan | `docs/superpowers/plans/2026-08-15-phase-0a-data-feasibility-and-donor-characterization.md` | SUPERSEDED — annotated in place |
| Provider duplication audit | `docs/engineering/PROVIDER_DUPLICATION_AUDIT.md` | SUPERSEDED — donor-related rows annotated in place |
| IMP work log (donor-era entries) | `docs/engineering/WORK_LOG.md` | SUPERSEDED — donor-era entries annotated at the head |
| Competitive & interaction research | `docs/product/ux/competitive-research.md` | SUPERSEDED — donor-related references annotated in place |
| Phase 0A collection fixture inventory | `docs/research/fixtures/2026-08-15-phase-0a-collection-fixture-inventory.md` | SUPERSEDED — annotated in place |
| Revision-3 donor preservation manifests | `docs/superpowers/governance/2026-08-14-revision-3-donor-preservation-before.json`, `...-difference.json` | SUPERSEDED — annotated in place |

## Hash-bound records (not annotated in place)

These files keep their bound bytes so Phase 0 / Phase 0A / Phase 1 hash
verifiers stay honest. Do **not** add banners. This notice is the current
disposition for Heller / GridIQ / DS-340W **donor-authorization** language
inside them.

| Record | Path | Binding | What this notice supersedes |
|---|---|---|---|
| Foundation Revision 3 | `docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md` | SHA-256 `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35` (verified on this tree) | Inventory rows 6–7 and §§5–6 "donor assessments" for DS-340W and GridIQ. Remainder of Revision 3 (authorized donors, model/dataset architecture, whale doctrine, no-live boundary) is unchanged. |
| Phase 0A design spec | `docs/superpowers/specs/2026-08-15-phase-0a-data-feasibility-and-donor-characterization-design.md` | logical ID `phase0a.design_specification` in Phase 0A approvals / authorization (do not rewrite) | Characterization of DS-340W / GridIQ as collection donors (§1 item 3, §9 table). |

Do not resolve a conflict between a SUPERSEDED Heller record and Revision 3 by
treating Revision 3 as still authorizing those materials as IMP donors.

## What remains valid

- **Native IMP implementations are untouched and remain valid.** Any code in
  `src/market_platform_foundation/` (including `donor_patterns/`, the dataset
  projection/cache subsystem under `storage/*`, the assistant audit store, and
  UI patterns) that was historically described as GridIQ-inspired was
  independently reimplemented from a legitimate platform requirement
  (**ADAPT**). It does not depend on GridIQ or DS-340W donor authorization.
- **Authorized donors remain authorized** where the professor/user explicitly
  directed them (CVD, Options, futuresX patterns, short-squeeze bridge/gates).
- **Historical records are preserved for provenance only.** Hash-bound
  specifications are not rewritten. Annotated records keep their historical
  body.

## Operating rule

Lucas Heller's DS-340W and GridIQ materials must not be used as authorization
for future implementation. **Current identity authority** for those names is
this notice — not Revision 3, not the historical donor index, and not
ADR-GRIDIQ-001. The index at `docs/research/donors/README.md` is provenance
only.
