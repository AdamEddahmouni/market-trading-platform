# Integrated Market Platform — governed foundation

This repository contains the governed, CPython 3.11 standard-library-only
foundation subject. Phases 0 through 8 are `PASS` on the admitted equity
intraday fixture (`ADMITTED-SHORTSQ-BIYA-BARS-001`). The machine-readable
binding is [canonical-authority.json](manifests/phase0/canonical-authority.json).

The active forward-looking authority is
[Canonical Foundation Design Revision 3](docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md),
approved at SHA-256
`7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`.
Revision 2 remains the incorporated Phase 0 safety authority.

| Phase | Status |
|---|---|
| Phase 0 — governance and no-live safety | `PASS` |
| Phase 0A — data feasibility | `PASS` (non-ES equity intraday admitted) |
| Phase 1 — foundational decisions | `PASS` |
| Phase 2 — canonical contracts and replay | `PASS` |
| Phase 3 — verified historical adapter | `PASS` |
| Phase 4 — runtime quality and state | `PASS` |
| Phase 5 — capability-supported features | `PASS` |
| Phase 5R — research/model infrastructure | `PASS` |
| Phase 6 — preregistered strategy | `PASS` |
| Phase 7 — risk, simulation, and accounting | `PASS` |
| Phase 8 — deterministic end-to-end acceptance | `PASS` (ES session remains deferred per ADR-DATA-001) |

The existing candidate evidence roots under `evidence/phase0/2E1E…` and
`evidence/phase0/6B31…` bind older repository subjects. They remain immutable and
do not establish acceptance for the current repository subject.

## Revision 3 guidance

- [External donor index](docs/research/donors/README.md)
- [Donor reuse and verification matrix](docs/research/donors/DONOR_REUSE_MATRIX.md)
- [Revision 3 roadmap projection](docs/roadmap/REVISION_3_ROADMAP.md)
- [Swim With the Whales doctrine](docs/architecture/SWIM_WITH_THE_WHALES.md)
- [Model research and historical datasets](docs/architecture/MODEL_RESEARCH_AND_DATASETS.md)

## Capability boundary

This repository has no provider, broker, market-data runtime, whale ingestion,
AI-trading, paper-trading, or live-trading capability. It has no Git remote.
Documentation of future interfaces is not implementation or authorization.
ES-session acceptance remains blocked per `ADR-DATA-001` until lawful ES bytes
are procured. Research UI, broker adapters, and whale ingestion require
separate ADR authorization.
