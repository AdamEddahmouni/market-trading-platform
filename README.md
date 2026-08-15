# Integrated Market Platform — governed foundation

This repository contains the governed, CPython 3.11 standard-library-only Phase
0 structural and evidence subject. Its Phase 0 status is `PASS`, published per [phase-0-pass-publication](docs/superpowers/governance/2026-08-15-phase-0-pass-publication.json).

The active forward-looking authority is
[Canonical Foundation Design Revision 3](docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md),
approved at SHA-256
`7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`.
Revision 2 remains the incorporated Phase 0 safety authority. The machine-readable
binding is [canonical-authority.json](manifests/phase0/canonical-authority.json).

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

This repository has no provider, broker, market-data, model runtime, whale
ingestion, AI-trading, strategy, paper-trading, or live-trading capability. It
has no Git remote. Documentation of future interfaces is not implementation or
authorization. Forecast, strategy, intent, independent risk, authorized
execution, and accounting remain separate gates.
