# Integrated Market Platform — governed foundation

Local market operating workstation: **Demo** (fixture replay), **Paper**
(internal simulation under env gates), **Live** (broker-observed read-only).
**Live production execution is not authorized** in this repository.

**Documentation:** [docs/README.md](docs/README.md) · [AGENTS.md](AGENTS.md) ·
[Engineering Handbook](docs/engineering/ENGINEERING_HANDBOOK.md) ·
[Architecture](docs/architecture/ARCHITECTURE.md) ·
[Project Status](docs/PROJECT_STATUS.md) ·
[Provider readiness](docs/engineering/PROVIDER_READINESS.md)

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
| UI-002 — expanded research UI | `PASS` (Institutional Flow, Model Lab, Simulation Lab) |
| Phase 9 — provider contracts and EDGAR whale ledger | `PASS` (fixture-first `regulatory_disclosure` on BIYA) |
| Phase 10 — whale order_flow family | `PASS` (fixture-first `order_flow` on NVDA slice) |
| Phase 11 — whale options family | `PASS` (fixture-first `options` on BIYA slice) |
| Phase 12 — whale large_transactions family | `PASS` (fixture-first `large_transactions` on NVDA slice) |
| Phase 13 — whale order_book family | `PASS` (fixture-first `order_book` on NVDA slice) |
| Phase 14 — whale futures_positioning family | `PASS` (fixture-first ES depth on `ADMITTED-L2-ES-001`) |
| Phase 15 — whale public_catalyst family | `PASS` (fixture-first catalyst on `ADMITTED-CATALYST-BOXL-001`) |
| Phase 16 — whale fund_etf_cross_asset family | `PASS` (fixture-first fund/ETF on `ADMITTED-ETF-CROSSASSET-NVDA-001`) |
| MRA-001 — grounded Market Research Assistant | `PASS` (deterministic evidence retrieval on admitted fixture) |
| MRA-002 — Anthropic LLM assistant | `PASS` (mocked HTTP acceptance; live inference when `ANTHROPIC_API_KEY` set) |
| Platform P0 — bitemporal reference store + PIT joins | `PASS` (fixture scope; FAST + FULL invariants) |
| Platformization P0–P4-4B — paper execution, live observational data, local state, unified workstation, discovery, Tradier sandbox broker-paper adapter, broker/ledger reconciliation | `COMPLETE_WITH_LIMITATIONS` (see [platformization roadmap](docs/research/PLATFORMIZATION_ROADMAP.md)) |
| Public-data providers — macro / energy / sec / short-intelligence / observational / finviz-discovery | `IMPLEMENTED` (fixture-first; live probes opt-in; captures **not admitted**) |

The next campaign after BUILD35 is the
[whole-repository closure audit](docs/engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md),
`POST-BUILD35-REPOSITORY-CLOSURE-001`—not BUILD36. Its canonical inventory
classifies every significant historical subsystem as `CANONICAL`, `WRAPPED`,
`RETAINED_SUPPORTING`, `SUPERSEDED`, `DUPLICATE`, `DEAD`, or `UNINTEGRATED`
before any cleanup or integration action is taken.

## Validation cadence

Manifest-driven validation replaces ad-hoc full-suite runs after every edit.
Use the canonical developer router described in [AGENTS.md](AGENTS.md) and
[Developer Operating System](docs/engineering/DEVELOPER_OPERATING_SYSTEM.md).

```powershell
python tools/imp.py test affected         # after each edit
python tools/imp.py validate domain <name> # domain milestone
python tools/imp.py validate full         # major checkpoint (offline only)
python tools/imp.py validate live <provider> # opt-in live boundary only
python tools/provider_readiness.py --probe-local  # value-blind provider check
```

Legacy wrapper: `python tools/run_all_tests.py` (strictly offline, delegates to manifest).

## One-click local start and stop (Windows)

For a new checkout, double-click [SETUP_PLATFORM.cmd](SETUP_PLATFORM.cmd).
It runs a value-blind preflight, repairs the project `.venv`, installs the
declared Python and UI dependencies, creates `.local`/`.private`, and checks
`.env` syntax without printing secrets. Missing Windows software is reported
with an install instruction; it is never installed silently. After successful
setup, choose **Enter Demo** to launch the workstation or **Continue setup**
to exit and configure providers later.

From File Explorer, double-click [START_PLATFORM.cmd](START_PLATFORM.cmd)
to start the API and UI, wait for both to become ready, and open the Mixed Live
screener. Double-click [STOP_PLATFORM.cmd](STOP_PLATFORM.cmd) to stop only
the launcher-owned API/UI process trees. [PLATFORM_CONTROL.cmd](PLATFORM_CONTROL.cmd)
provides Start/Open, Open Browser, Status, Finviz Status, Stop/Exit, and
leave-running choices in one menu.

The platform binds only to `127.0.0.1`: API port `8766`, UI port `5173`. The
browser control center is `/control`, and the launcher-owned loopback
supervisor is `127.0.0.1:8767`. Child output is retained in
`.local/platform-backend.log`, `.local/platform-ui.log`, and
`.local/platform-control.log`; lifecycle state is in the gitignored
`.local/platform-launcher.json`. The control center shows independent provider
readiness, masked configuration, refresh/restart actions, and guarded update
checks. Updates are blocked for dirty worktrees and only use explicit
fast-forward pulls; no reset, stash, or force operation is performed.

A stale state file cannot make Stop kill an unrelated process because the
current Windows command identity must still match the launcher record. Provider
secrets stay in the existing `.env`/`.private` locations, are allowlisted and
written atomically, and are never included in status, operation, or error
responses.

Prerequisites are the repository CPython 3.11 `.venv`, Node.js/npm, and a prior
`npm install` in `ui/`. When `%USERPROFILE%\moomoo-api-test\.venv` exists, the
API automatically uses it so the Moomoo SDK is available; otherwise it uses the
repository venv. Moomoo OpenD must be running separately on loopback port
`11111` for Moomoo quotes. The launcher enables observational data and internal
paper simulation but never enables live order execution.

Pre-land acceptance (2026-08-21): FAST 18 passes; mutation 6/6 detected; FULL 1183 passes / 7 skips — [reports/pre-land-full.json](reports/pre-land-full.json).
Post-land FULL (2026-08-22): 1391 tests / 7 skips with **one documented failure** — the Phase 1 ADR acceptance-index line-ending drift ([PHASE1_ADR_LINE_ENDING_DRIFT](docs/engineering/PHASE1_ADR_LINE_ENDING_DRIFT.md)); no other failures or errors. **Resolved the same day:** the Phase 1 decision bundle was re-published with true LF-byte hashes and the verifier constants updated; FULL is now green — 1485 tests / 7 skips / 0 failures / 0 errors ([reports/post-drift-fix-full.json](reports/post-drift-fix-full.json)).

## Five-lane cooperative expansion (fixture scope)

Active forward work beyond governed Phases 0–16 is tracked in
[Platform Cooperative Master Roadmap](docs/research/PLATFORM_COOPERATIVE_MASTER_ROADMAP.md).
Latest cooperative milestones: **MC16 — Multi-document LLM synthesis** (separate cluster synthesis fields with MC7/MC8 optional enrichment on BOXL fixtures; no universal news score), **MC15 — Cross-entity propagation** (separate `propagated_*` fields on BOXL/NVDA graph fixtures; no universal news score), **MC14 — Social / author intelligence** (influence vs accuracy on admitted BOXL social fixtures), **F11 — Advanced modeling baseline** (EQUITY_INDEX + ENERGY/CL engineered forecaster + F11-S1 walk-forward gate vs F5 trend-only on admitted fixtures), **OF12 — Advanced LOB baseline** (M8 engineered forecaster + OF12-S1 walk-forward gate on admitted ES/NVDA fixtures), **PI13 — Forced-flow / dislocation engine** (metaorder completion + exhaustion + leverage stress without catalyst at cutoff on admitted NVDA fixtures), **PI12 — Large derivatives participant research**, **PI11 — Cross-asset participant context** (equity crowding fused with F4 COT on admitted BIYA/ES fixtures), **PI10 — Consensus / disagreement / crowding** (instrument-level alignment on admitted BIYA fixtures), and **PI9 — Copyability** (follower return scoring on admitted BIYA disclosure fixtures). **MC11 — Macro context** and **PI8 — Contextual intent** also complete on fixtures.

Completed cooperative milestones on admitted fixtures include O6–O9, OF6–OF12, F4–F11, SS P4–P7, Market Context MC1–MC16, Participant PI1–PI13, and SHARED P2–P4 (incl. futures regime fusion). See
[SHARED P4 EV / Opportunity Layer Spec](docs/research/SHARED_P4_EV_OPPORTUNITY_SPEC.md).

The existing candidate evidence roots under `evidence/phase0/2E1E…` and
`evidence/phase0/6B31…` bind older repository subjects. They remain immutable and
do not establish acceptance for the current repository subject.

## Platformization (P0–P4-4C)

Transition from replay-only research UI to a provider-agnostic market
operating workstation, tracked in the
[platformization roadmap](docs/research/PLATFORMIZATION_ROADMAP.md):

| Milestone | Delivered |
|---|---|
| P0 | Orthogonal `data_mode` × `execution_mode` × `execution_authority`, event-sourced paper ledger, `/paper/*` API, CI — [PLATFORM-PAPER-001](docs/superpowers/specs/2026-08-21-platform-paper-001-design.md) |
| P1 | Interactive internal simulation (preview + submit → `BarConservativeSimulator`), trace/cancel, parity — [P1](docs/superpowers/specs/2026-08-21-platform-p1-interactive-terminal.md), [order lifecycle](docs/superpowers/specs/2026-08-21-platform-p1-order-lifecycle.md), [execution trace](docs/superpowers/specs/2026-08-21-platform-p1-execution-trace.md) |
| P2/P2.1 | Live observational Moomoo runtime with display vs execution admission — [PLATFORM-DATA-001](docs/superpowers/specs/2026-08-21-platform-data-001-design.md) |
| P3/P3.1 | Durable SQLite state, operator workflow, restart recovery, live internal paper closure — [PLATFORM-STATE-001](docs/superpowers/specs/2026-08-21-platform-state-001-design.md), [P3.1 closure](docs/superpowers/specs/2026-08-21-platform-p31-live-execution-closure.md) |
| P3.2 | Unified live decision workstation (lane evidence envelope, What Matters Now, evidence drawer) — [P3.2](docs/superpowers/specs/2026-08-21-platform-p32-unified-live-workstation.md) |
| P3.3 | Finviz Elite discovery, prospective PIT capture, decision-research foundation — [P3.3](docs/superpowers/specs/2026-08-21-platform-p33-finviz-discovery-research.md) · [DECISION-RESEARCH-001 milestone A](docs/superpowers/specs/2026-08-22-decision-research-001-design.md) |
| P4-4A | Tradier sandbox broker-paper adapter, idempotent submission, broker lifecycle mapping, sandbox-contract fixtures, gate PASS — [PLATFORM-P4-001](docs/superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md) |
| P4-4B | Broker/ledger reconciliation engine: deterministic reports (`P4-REC-001`), append-only `ReconciliationRecorded` events, `project_risk.reconciliation_status`, zero silent mismatches (`P4-REC-002`), gate PASS — [PLATFORM-P4-001](docs/superpowers/specs/2026-08-22-platform-p4-broker-paper-001-design.md) |

P4 sub-milestones **4A** (Tradier sandbox broker-paper adapter + idempotent
submission), **4B** (broker/ledger reconciliation), and **4C** (Moomoo paper
adapter) plus the `/paper/broker/*` read-only observability endpoints
(orders/account/positions/reconciliation/health) are **implemented** —
offline and fixture-first; the 4A and 4B gate tools report aggregate PASS
(`evidence/platform/broker-paper-gate-report.json`,
`evidence/platform/reconciliation-gate-report.json`). Limitations: 4A/4B wire
specifics depend on exercising the real Tradier sandbox (tracked in
[Tradier provider notes](docs/providers/TRADIER_PAPER.md)); 4C is
fixture-proven only — the Moomoo OpenAPI is reachable solely through the
proprietary OpenD gateway (TCP-only), so real-wire behavior remains
unconfirmed. P5 status: neutral security foundations landed
(`ROLE_ENFORCEMENT_STATUS=MODEL_ONLY_NOT_ENFORCED`); hosted deployment and
auth enforcement are not started. P6 status: shadow/forward-validation
infrastructure landed; no forward-validation evidence has been collected.
Production execution (`LIVE-001`) is blocked pending separate authorization.

## Revision 3 guidance

Revision 3 is **effective** (exact-hash approval 2026-08-14;
`resolve_canonical_authority()` → `PASS`). The frozen specification header still
says `PROPOSED_PENDING_EXACT_HASH_APPROVAL` — see
[effectivity notice](docs/superpowers/governance/2026-08-14-foundation-revision-3-effectivity-notice.md).

- [External donor index](docs/research/donors/README.md)
- [Donor reuse and verification matrix](docs/research/donors/DONOR_REUSE_MATRIX.md)
- [Revision 3 roadmap projection](docs/roadmap/REVISION_3_ROADMAP.md)
- [Market Context target architecture](docs/research/MARKET_CONTEXT_TARGET_ARCHITECTURE.md)
- [Five-lane roadmap reconciliation](docs/research/FIVE_LANE_ROADMAP_RECONCILIATION.md)
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

This repository has no production broker runtime, on-chain ingestion,
live social API connection, crypto research adapter, AI-trading, or
live-trading capability. **Internal paper execution** (Platformization
P0–P3.3) exists as an event-sourced simulation ledger reachable only
under explicit env gates (`IMP_PAPER_EXECUTION=1`,
`IMP_LIVE_INTERNAL_SIMULATION=1`). **Broker paper execution** (P4-4A/4B) is a
Tradier **sandbox-only** adapter that fails closed unless all of
`IMP_TRADIER_PAPER=1`, `IMP_BROKER_PAPER_EXECUTION=1`, a token, and the
sandbox endpoint are set — it has no live order path, and its delayed-sandbox
fills are authoritative only for the `BROKER_PAPER` ledger, never research
data. Broker/ledger reconciliation (4B) is append-only and fail-closed: every
mismatch surfaces as an immutable ledger event and is resolved or held open
(`P4-REC-001/002`) — differences are never silently absorbed. Live execution
(`LIVE-001`) remains blocked and requires separate authorization.
The repository remote is `origin` →
`https://github.com/AdamEddahmouni/integrated-market-intelligence-platform.git`.

### Observational and public-data providers (fixture-first)

All live captures and observational probes are **not admitted research datasets**.
Admission requires separate phase gates and lawful fixture procurement.

| ADR | Source | Scope |
|---|---|---|
| [ADR-LIVE-001](docs/superpowers/decisions/2026-08-20-adr-live-001-observational-market-data-boundary.json) | Moomoo OpenD | Read-only observational boundary (`127.0.0.1:11111`); serialized canonical events only. See [Moomoo observational provider](docs/providers/MOOMOO_OBSERVATIONAL.md). |
| [ADR-EDGAR-001](docs/superpowers/decisions/2026-08-20-adr-edgar-001-public-sec-source.json) | SEC EDGAR | Public read-only REGULATORY transport (`SEC_USER_AGENT`, 5 req/s Fair Access). Distinct from Phase 9 fixture whale ledger. See [SEC EDGAR provider](docs/providers/SEC_EDGAR.md). |
| [ADR-FTD-001](docs/superpowers/decisions/2026-08-20-adr-ftd-001-sec-fails-to-deliver.json) | SEC FTD | Public fails-to-deliver files. See [SEC FTD provider](docs/providers/SEC_FAILS_TO_DELIVER.md). |
| [ADR-SHORT-001](docs/superpowers/decisions/2026-08-20-adr-short-001-short-intelligence-sources.json) | FINRA / Nasdaq / NYSE / CBOE Reg SHO | Observational short-intelligence; threshold routing. See [FINRA / Nasdaq short intelligence](docs/providers/FINRA_NASDAQ_SHORT_INTELLIGENCE.md) and [US threshold coverage](docs/providers/US_THRESHOLD_COVERAGE.md). |
| [ADR-FRED-001](docs/superpowers/decisions/2026-08-20-adr-fred-001-dual-api-macro-source.json) | FRED / ALFRED | Macro series with revision-aware PIT. See [FRED / ALFRED provider](docs/providers/FRED_ALFRED.md). |
| [ADR-COT-001](docs/superpowers/decisions/2026-08-20-adr-cot-001-cftc-public-source.json) | CFTC COT | Futures positioning snapshots. See [CFTC COT provider](docs/providers/CFTC_COMMITMENTS_OF_TRADERS.md). |
| — | EIA Open Data | Energy fundamentals. See [EIA provider](docs/providers/EIA_ENERGY_FUNDAMENTALS.md). |
| — | NOAA / NWS / CPC | Weather-demand evidence; no credential required. See [Weather provider](docs/providers/NOAA_NWS_CPC_WEATHER.md). |
| — | CBOE public options statistics | Publisher/venue semantics enforced. See [CBOE options statistics](docs/providers/CBOE_PUBLIC_OPTIONS_STATISTICS.md). |
| — | Finviz Elite | Read-only DISCOVERY/CONTEXT exports (`FINVIZ_API_KEY`); prospective capture only, no retroactive screen reconstruction, never orders. See [Finviz Elite provider](docs/providers/FINVIZ_ELITE.md) and [capability matrix](docs/research/finviz-elite-capability-matrix.md). |

Phase 9 whale families remain **fixture-first** on admitted slices: `regulatory_disclosure` (BIYA), `order_flow` (NVDA), `options` (BIYA), and Phases 10–16 families on their admitted fixtures. Unconfigured whale capabilities remain fail-closed stubs.

ES-session acceptance remains blocked per `ADR-DATA-001` until lawful ES bytes
are procured. UI-001 provides replay-only research UI on the admitted fixture.
Additional broker execution adapters (IBKR, Alpaca, Moomoo execution),
non-disclosure whale ingestion, crypto expansion, and prediction-market
expansion require separate ADR authorization and phase gates.

## Research UI V1

- [UI-001 design spec](docs/superpowers/specs/2026-08-18-ui-001-research-ui-v1-design.md)
- [Short-squeeze read-only integration lane](docs/integration/SHORT_SQUEEZE_LANE.md)
- [Order Flow / microstructure integration lane](docs/integration/ORDER_FLOW_LANE.md)
- Start API: `python tools/ui1/run_ui_api.py --serve --port 8766`
- Restart live observational API (no hot reload; kill stale `:8766` listeners first): `powershell -File tools/ui1/restart_ui_api.ps1`
- `IMP_MOOMOO_LIVE=1` is observational market data only — it does not authorize execution
- Frontend: see [ui/README.md](ui/README.md)

## Grounded research assistant (MRA-001 / MRA-002)

- [MRA-001 design spec](docs/superpowers/specs/2026-08-18-mra-001-grounded-assistant-design.md)
- [MRA-002 Anthropic design spec](docs/superpowers/specs/2026-08-18-mra-002-anthropic-assistant-design.md)
- Default inference: `grounded.evidence` (deterministic explain/inspect retrieval)
- **Anthropic LLM** (when `ANTHROPIC_API_KEY` is set): `anthropic.messages` with grounded evidence pack + fallback
- Copy [`.env.example`](.env.example) and set `ANTHROPIC_API_KEY` before starting the API
- Rollback to abstaining stub: `IMP_ASSISTANT_STUB=1`
- Force grounded-only: `IMP_ASSISTANT_PROVIDER=grounded`
- MRA-001 acceptance evidence: `python tools/mra001/run_mra001_pipeline.py --output-dir evidence/mra001/build-run`
- MRA-001 publish PASS: `python tools/mra001/publish_mra001_pass.py`
- MRA-001 verify publication: `python tools/mra001/verify_mra001_publication.py`
- MRA-002 acceptance evidence: `python tools/mra002/run_mra002_pipeline.py --output-dir evidence/mra002/build-run`
- MRA-002 publish PASS: `python tools/mra002/publish_mra002_pass.py`
- MRA-002 verify publication: `python tools/mra002/verify_mra002_publication.py`

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:IMP_ASSISTANT_PROVIDER = "anthropic"
python tools/ui1/run_ui_api.py --serve --port 8766
```
