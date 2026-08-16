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
| UI-001 — replay-only research UI V1 | `PASS` (stdlib API + `ui/` frontend subject) |

The existing candidate evidence roots under `evidence/phase0/2E1E…` and
`evidence/phase0/6B31…` bind older repository subjects. They remain immutable and
do not establish acceptance for the current repository subject.

## Revision 3 guidance

- [External donor index](docs/research/donors/README.md)
- [Donor reuse and verification matrix](docs/research/donors/DONOR_REUSE_MATRIX.md)
- [Revision 3 roadmap projection](docs/roadmap/REVISION_3_ROADMAP.md)
- [Swim With the Whales doctrine](docs/architecture/SWIM_WITH_THE_WHALES.md)
- [Model research and historical datasets](docs/architecture/MODEL_RESEARCH_AND_DATASETS.md)

## Future expansion (planning only — not authorized)

- [Crypto & influence expansion design](docs/superpowers/specs/2026-08-16-crypto-influence-expansion-design.md)
- [Crypto & influence expansion track](docs/roadmap/CRYPTO_INFLUENCE_EXPANSION_TRACK.md)
- [Crypto architecture index](docs/architecture/CRYPTO_ASSET_AND_CAPABILITY_MODEL.md)
- [Influence intelligence](docs/architecture/INFLUENCE_INTELLIGENCE.md)
- [On-chain intelligence](docs/architecture/ON_CHAIN_INTELLIGENCE.md)
- [Crypto profitability research](docs/architecture/CRYPTO_PROFITABILITY_RESEARCH.md)
- [Experiment roadmap](docs/research/CRYPTO_INFLUENCE_EXPERIMENT_ROADMAP.md)
- [Prediction markets expansion design](docs/superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)
- [Prediction markets expansion track](docs/roadmap/PREDICTION_MARKETS_EXPANSION_TRACK.md)
- [Prediction market capability model](docs/architecture/PREDICTION_MARKET_CAPABILITY_MODEL.md)
- [Prediction market probability research](docs/architecture/PREDICTION_MARKET_PROBABILITY_RESEARCH.md)
- [Prediction market whale intelligence](docs/architecture/PREDICTION_MARKET_WHALE_INTELLIGENCE.md)
- [Prediction markets experiment roadmap](docs/research/PREDICTION_MARKETS_EXPERIMENT_ROADMAP.md)

Documentation of future interfaces is not implementation or authorization.

## Capability boundary

This repository has no provider, broker, market-data runtime, whale ingestion,
on-chain ingestion, social API connection, crypto adapter, AI-trading,
paper-trading, or live-trading capability. It has no Git remote.
ES-session acceptance remains blocked per `ADR-DATA-001` until lawful ES bytes
are procured. UI-001 provides replay-only research UI on the admitted fixture.
Broker adapters, whale ingestion, crypto expansion, and prediction-market expansion
require separate ADR authorization and phase gates.

## Research UI V1

- [UI-001 design spec](docs/superpowers/specs/2026-08-18-ui-001-research-ui-v1-design.md)
- [Short-squeeze read-only integration lane](docs/integration/SHORT_SQUEEZE_LANE.md)
- Start API: `python tools/ui1/run_ui_api.py --serve --port 8766`
- Frontend: see [ui/README.md](ui/README.md)
