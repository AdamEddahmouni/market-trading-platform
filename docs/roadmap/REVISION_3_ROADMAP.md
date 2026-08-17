# Revision 3 roadmap projection

This is a navigational projection of Revision 3 Section 20, not an independent
authority. Revision 3 controls on conflict. No phase is started, completed, or
authorized by this file.

| Phase | Revision 3 projection | Authorization state |
|---|---|---|
| Phase 0 — governance and structural no-live safety | Structural no-live safety and governance evidence accepted for the current repository subject. | `PASS` |
| Phase 0A — data feasibility and donor characterization | Characterize admitted sources and the two new donors without running remote fetches or importing donor code/data. | `PASS` — non-ES equity intraday source admitted; ES-session bundle remains blocked |
| Phase 1 — foundational decisions | Consider dataset identity, PIT feature semantics, model identity/reproducibility, cache semantics, institutional evidence, donor reuse, and provider-neutral LLM boundaries. | `PASS` — all registry ADRs accepted; Phase 2 remains unauthorized |
| Phase 2 — canonical contracts and replay | Establish identity, availability, revision, quality, and deterministic replay contracts before model work. | `PASS` — contracts and replay proven on synthetics; Phase 3 remains unauthorized |
| Phase 3 — verified historical adapter | Prove admitted source capability and dataset manifests before market-model evaluation. | `PASS` — admitted equity intraday source normalized; Phase 4 remains unauthorized |
| Phase 4 — runtime quality and state | Establish quality and state behavior; caches may not weaken replay determinism. | `PASS` — bar quality replay and cache proven on admitted fixture; Phase 5 remains unauthorized |
| Phase 5 — capability-supported features | Add only evidence dimensions actually supported by admitted data; institutional interfaces cannot imply unavailable capabilities. | `PASS` — capability-supported features proven on admitted fixture; Phase 5R published |
| Phase 5R — research/model infrastructure | Under separate authority, may add research datasets, targets, model interfaces, baselines, manifests, PIT walk-forward evaluation, calibration, serialization, and artifact identity. | `PASS` — research/model infrastructure proven on admitted fixture; Phase 6 published |
| Phase 6 — preregistered strategy | Forecasts and whale evidence may be explicit inputs but cannot replace preregistration, abstention, or strategy semantics. | `PASS` — preregistered strategy proven on admitted fixture; Phase 7 remains unauthorized |
| Phase 7 — risk, simulation, and accounting | Independent risk, conservative simulation, cash/position/P&L reconciliation, and attribution remain mandatory. | `PASS` — risk, simulation, and accounting proven on admitted fixture; Phase 8 remains unauthorized |
| Phase 8 — deterministic end-to-end acceptance | Acceptance remains evidence-bound and makes no unsupported edge claim. | `PASS` — end-to-end acceptance proven on admitted fixture; ES session remains deferred |
| UI-001 — replay-only research UI V1 | Read-only API and React frontend on admitted fixture; REPLAY mode only. | `PASS` — UI-001 proven on admitted fixture |
| Phase 9 — provider contracts and EDGAR whale ledger | Capability-split provider interfaces; fixture-first SEC EDGAR disclosure ingestion; whale ledger; `regulatory_disclosure` wiring. | `PASS` — offline fixture slice on BIYA admitted context |
| Phase 10 — whale order_flow family | Fixture-first NVDA CVD order-flow slice; `order_flow` institutional family; read-only workspace API and UI panel. | `PASS` — ADMITTED-CVD-NVDA-ORDERFLOW-001 |
| Phase 11 — whale options family | Fixture-first BIYA options-activity slice; `options` institutional family; read-only workspace API and UI panel. | `PASS` — ADMITTED-OPTIONS-BIYA-001 |
| Phase 12 — whale large_transactions family | Fixture-first NVDA large-print slice; `large_transactions` institutional family; read-only workspace API and UI panel. | `PASS` — ADMITTED-LARGE-PRINTS-NVDA-001 |

## Accepted foundational ADRs (Phase 1 registry)

All registry ADRs listed in Revision 3 Section 21 are `ACCEPTED`. Phase 1 is
`PASS`. See `manifests/phase1/adr-registry.json`.

An ADR cannot accept itself or authorize its own implementation.

## Later research tracks

### Revision 3 tracks (deferred)

Institutional/Whale Intelligence, a grounded Market Research Assistant, and
expanded Research UI remain separately authorized tracks. They do not run ahead
of the serial foundation.

### Crypto & influence expansion (proposed — not authorized)

Cryptocurrency as a first-class future asset family; on-chain intelligence;
influence intelligence; cross-venue intelligence; crypto derivatives; and
profitability research extensions are documented as a **future expansion track**:

- [Crypto & Influence Expansion Design](../superpowers/specs/2026-08-16-crypto-influence-expansion-design.md)
- [Expansion track roadmap](CRYPTO_INFLUENCE_EXPANSION_TRACK.md)

No roadmap row grants provider access, broker access, on-chain ingestion, social
API connection, model implementation, whale ingestion, AI integration, paper
orders, or live orders.

### Prediction markets expansion (proposed — not authorized)

Prediction/event markets as a first-class future research and trading domain;
event intelligence; fair-probability research; public participant intelligence;
cross-platform and cross-asset intelligence; resolution semantics; and simulation
extensions are documented as a **future expansion track**:

- [Prediction Markets Expansion Design](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)
- [Prediction markets expansion track](PREDICTION_MARKETS_EXPANSION_TRACK.md)

Initial provider candidates for feasibility characterization: Kalshi, Polymarket /
Polymarket US, and other lawful API-accessible exchanges discovered during research.
No roadmap row grants Kalshi/Polymarket adapter implementation, prediction-market
ingestion, execution, or trading.
