# 03 — Donor-to-IMP Integration Map

Status: **COMPLETE for WS03 (2026-09-06)**. Forensic trace of every donor into
the current IMP implementation (`projects/integrated-market-platform/`,
baseline `d691050` / child `main` @ `072e62e`). No remediation executed.
Scope authority is WS02's ledger; this file maps provenance only.

## Headline findings

1. **No DIRECT_COPY from any donor anywhere.** Every donor-derived component is
   an independent reimplementation (PORT_ADAPT) with honest docstrings
   ("reimplemented from CVD Bubble concepts", "PORT_ADAPT from Eric_futuresX
   concepts (stdlib only)", "no donor code copy").
2. **GridIQ/DS-340W (mistaken donors) influenced code only via ADR-approved
   PORT_ADAPT patterns (GridIQ), or not at all (DS-340W).** Zero GridIQ/
   DS-340W/fantasy/nflverse identifiers exist in IMP code or tests. The
   authorization basis of the GridIQ ADR predates the professor's correction
   and must be re-annotated — but the implementation itself is independent and
   the capability is required → KEEP, no code change.
3. **Authorized donors (CVD, Options, futuresX) supplied concepts, not code:**
   `donor_patterns/` holds IMP's own lane formulas; admitted fixtures are
   research-only slices with explicit admission manifests.
4. **Claude Code News: NOT_YET_INTEGRATED** (zero matches in IMP).
5. **No IBKR/Tradovate/TradingView/Unusual Whales/iVolatility/Topstep client
   code in IMP.** IBKR appears only as fixture provenance metadata and
   capability listings. CVD L1/L2 IB runtime integration is a missing
   authorized capability (WS04/WS05), not donor contamination.

## Integration map (donor → feature → introduction → current → disposition)

| INT ID | Source | Donor feature/pattern | Introduction evidence | Current IMP location | Provenance | Authorization | Dependency impact | Disposition | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| INT-001 | SRC-002 GridIQ | Dataset projection + disk/memory cache patterns (nflverse_parquet / nflverse_schedules / nflverse_pbp_store concepts) | `6adeeec` (8/16, ADR-GRIDIQ-001 PORT_ADAPT "no donor code copy") + `5ec19a7` (8/16, storage relocation) | `src/market_platform_foundation/storage/{dataset_reader,projection_cache,bounded_memory_cache,dataset_cache,precision_policy}.py`, `research/{dataset_pipeline,dataset_reader}.py`; used by `research/evaluation.py` (walk-forward), `ui_api.projections`, `research/__init__` exports | STRUCTURAL_DERIVATION / REIMPLEMENTED_FROM_REQUIREMENT (independent; sha256 content-addressed, logical_ids, ADR-DCACHE-001/RDATA-001 idioms; zero GridIQ identifiers) | LEGITIMATE_REQUIREMENT (supporting architecture) — authorization basis superseded post-correction | FOUNDATIONAL (Phase 5R research, evaluation, UI projections) | KEEP_AS_IS + governance re-annotation (KEEP_BUT_REATTRIBUTE) | CONFIRMED |
| INT-002 | SRC-002 GridIQ | Assistant audit store (conversation-persistence concepts) | Phase gate 3 (ADR-LLM-001 ACCEPTED; "reimplemented only behind the inference boundary with no Gemini coupling") | `src/market_platform_foundation/assistant/` (AssistantAuditStore, AbstainingInferenceStub) | CONCEPTUAL_INFLUENCE (independent, provider-neutral) | LEGITIMATE_REQUIREMENT (MRA audit) | MEDIUM (assistant services/tests) | KEEP_AS_IS + re-annotation | MODERATE (gate evidence; store is independent) |
| INT-003 | SRC-002 GridIQ | UI API client validation/hooks (endpoints.ts concepts) | Phase gate 2 (UI-001 PASS; "without adopting Axios or browser token storage") | `ui/` api client + React Query hooks | CONCEPTUAL_INFLUENCE (independent) | LEGITIMATE_REQUIREMENT (UI-001) | MEDIUM | KEEP_AS_IS + re-annotation | MODERATE |
| INT-004 | SRC-002 GridIQ | Research visualization (DashboardCharts concepts) | Phase gate 4 (UI-001 PASS) | `ui/` research visualization components | CONCEPTUAL_INFLUENCE (independent) | LEGITIMATE_REQUIREMENT | LOW | KEEP_AS_IS + re-annotation | MODERATE |
| INT-005 | SRC-003 CVD Bubble | Lee-Ready aggressor classification, BVC, cumulative delta, OFI events | `3fe0b96` (8/16, donor bridge lanes) + later lane work; Q-series hardening | `src/.../donor_patterns/cvd_formulas.py`; consumers `order_flow/{cvd,aggressor,ofi,lob_baseline}.py`, `intelligence/signals/trade_direction.py`, `providers/adapters/fixture_order_flow.py` | REIMPLEMENTED_FROM_CONCEPT ("reimplemented from CVD Bubble concepts") | AUTHORIZED_DONOR_INTEGRATION (CVD = authorized; IB L1+L2 required) | FOUNDATIONAL (order-flow lane) | KEEP_AS_IS (correctness = WS05, Q-series already hardened numerics) | CONFIRMED |
| INT-006 | SRC-003 CVD Bubble | NVDA order-flow fixture slice | `4dc6ca0` (8/16, Phase 10) | `tests/fixtures/providers/order_flow/nvda_order_flow_slice.json` (+ admission_manifest) | FIXTURE_IMPORT — `donor_reference: "tradingCVDBubble-main/demo_data manifest (NVDA 2026-07-22)"`, `research_only: true`, bars `source: "ibkr_tick"`; no donor bytes admitted | AUTHORIZED (admission_id `ADMITTED-CVD-NVDA-ORDERFLOW-001`) | Tests + `providers/adapters/fixture_order_flow.py` | KEEP_AS_IS | CONFIRMED |
| INT-007 | SRC-004 internship (Options) | Options confirmation lane (liquidity gate, confirmation score) | `3fe0b96` + options lane work | `src/.../donor_patterns/options_lane.py`; consumers `options/{execution,strategy}.py`, `providers/adapters/fixture_options.py`, `providers/adapters/option_contract_builder.py` | REIMPLEMENTED_FROM_CONCEPT ("reimplemented from options_confirmation_engine concepts"); zero donor terminology (odte/herd/options_score/net_delta_oi = 0 matches) | AUTHORIZED_DONOR_INTEGRATION (Options = authorized; paid providers NOT required) | HIGH (options execution/strategy gates) | KEEP_AS_IS | CONFIRMED |
| INT-008 | SRC-004 internship (Options) | BIYA options fixture slice | Phase 11 | `tests/fixtures/providers/options/biya_options_slice.json` (+ admission_manifest) | FIXTURE_IMPORT — `donor_reference: "internship-project trade_log field shapes (PORT_ADAPT; no demo bytes admitted)"`, `research_only: true` | AUTHORIZED (`ADMITTED-OPTIONS-BIYA-001`) | Tests (`test_options_o6`, `test_options_contract`, etc.) + `fixture_options.py` | KEEP_AS_IS | CONFIRMED |
| INT-009 | SRC-004 internship (Options) | Donor runtime-state research bridge | `3fe0b96` | `donor_bridge/internship_client.py` + `donor_bridge/projections.py` (reads trade_log/watchlist/health state files); consumed via `providers/projections.py` (catalyst bridge) | DEPENDENCY_ONLY (read-only evidence bridge to donor state; no code import) | AUTHORIZED research bridge | LOW (research endpoints) | KEEP_AS_IS (research-only; donor isolation test enforces no execution path) | CONFIRMED |
| INT-010 | SRC-005 Eric_futuresX | Futures contract/depth lane patterns (third-Friday, quarterly months, RTH, depth imbalance) | post-3fe0b96 lane work | `donor_patterns/futures_lane.py` ("PORT_ADAPT from Eric_futuresX concepts (stdlib only)"), `donor_patterns/order_book_lane.py` ("no donor code copy"); consumers `futures/roll.py`, `providers/adapters/fixture_futures.py`, `futures_contract_builder.py`, `fixture_order_book.py`, `order_flow/lob_baseline.py` | STRUCTURAL_DERIVATION (independent, stdlib-only) | AUTHORIZED_OR_PREVIOUSLY_AUTHORIZED_FUTURE_CANDIDATE (professor: "Eric's using IB data") | MEDIUM (futures lane) | KEEP_AS_IS (architecture decision WS05/07) | CONFIRMED |
| INT-011 | SRC-005 Eric_futuresX | IBKR Level-2/execution runtime | — | NONE — zero matches for level2IBKR/ibkr_manager/reqMktDepth/Topstep in IMP | NOT_INTEGRATED | — | none | NO_ACTION_NEEDED (IB runtime is future authorized work) | CONFIRMED |
| INT-012 | SRC-006 Claude Code News | Entire system (MES news trader, Tradovate, CDP, ladder) | — | NONE — zero matches for Tradovate/NEWS_QTY/morning_brief/broker_ui/SIGUSR | NOT_INTEGRATED (NOT_YET_INTEGRATED) | AUTHORIZED_FUTURE_DONOR (reference) | none | NO_ACTION_NEEDED; evaluate at WS05/07 as Futures reference | CONFIRMED |
| INT-013 | SRC-001 DS-340W | Time-series model patterns | — | NONE — zero code/test matches (docs-only: DS340W_NOTES, reuse matrix) | NOT_INTEGRATED (DOCUMENTATION_ONLY) | KNOWN_MISTAKEN_DONOR | none | NO_ACTION_NEEDED (code); re-annotate docs | CONFIRMED |
| INT-014 | SRC-008 short-squeeze (original) | Provenance/freshness/missingness gates | `3fe0b96` | `donor_patterns/provenance_gates.py` ("reimplemented from short-squeeze screener patterns") | REIMPLEMENTED_FROM_REQUIREMENT (original project) | LEGITIMATE (original scope) | MEDIUM | KEEP_AS_IS | CONFIRMED |
| INT-015 | SRC-008 short-squeeze | Squeeze server research bridge | `3fe0b96` | `donor_bridge/squeeze_client.py` + `donor_bridge/projections.py` (`fetch_frozen_candidate_detail`, `:8787`), consumed by `providers/projections.py` | DEPENDENCY_ONLY (read-only HTTP research bridge to governed squeeze server) | LEGITIMATE (original scope) | LOW | KEEP_AS_IS | CONFIRMED |
| INT-016 | none (independent) | EDGAR whale vocabulary | later whale work | `donor_patterns/edgar_whale.py` ("professor brief + ADR-WHALE-001 alignment") | INDEPENDENT_IMP_EVOLUTION | AUTHORIZED (whale lane) | MEDIUM | KEEP_AS_IS | CONFIRMED |
| INT-017 | none (independent) | fund_etf / catalyst / large_print / order_book lane patterns | later lane work | `donor_patterns/{fund_etf_lane,catalyst_lane,large_print_lane,order_book_lane}.py` | INDEPENDENT_IMP_EVOLUTION | AUTHORIZED (whale/market-context lanes) | MEDIUM | KEEP_AS_IS | CONFIRMED |

## GridIQ contamination trace (SRC-002, priority)

- **6adeeec** (2026-08-16, AdamEddahmouni) "feat: port GridIQ dataset projection and cache patterns" — added ADR-GRIDIQ-001 (PORT_ADAPT, "no donor code copy"; GridIQ Gemini/localStorage-auth/gridiq.db permanently excluded), the port phase gate, `research/evaluation.py` rerouted to `build_research_dataset_from_events`, and five test files incl. `tests/gridiq/test_required_future_tests.py` (conformance harness mapped to GRID_IQ_NOTES required future tests).
- **5ec19a7** (same day) introduced the actual modules: `storage/{dataset_reader,projection_cache,bounded_memory_cache}.py` + `research/dataset_pipeline.py` (circular-import fix relocation).
- **Current descendants:** `storage/*` (5 modules), `research/dataset_pipeline.py`, `research/dataset_reader.py` (re-export), `research/evaluation.py`, `ui_api/projections.py`, assistant audit store (gate 3), UI client/hooks + visualization (gates 2/4).
- **Independent requirement:** dataset projection/caching/manifest binding = supporting architecture (Tier E) — IMP needs it regardless of GridIQ.
- **Dependents:** walk-forward evaluation, Phase 5R research pipeline, UI research projections, assistant audit conformance tests. Removal would be FOUNDATIONAL-impact — but removal is NOT proposed: implementation is independent (no GridIQ identifiers; canonical IMP idioms; ADR-DCACHE-001/ADR-RDATA-001) and capability is required.
- **Recommended disposition:** `KEEP_AS_IS` for code; `KEEP_BUT_REATTRIBUTE` for governance (supersede ADR-GRIDIQ-001's authorization framing, permissions record, phase gate, reuse matrix rows, GRID_IQ_NOTES — see Documentation corrections).
- Evidence confidence: CONFIRMED (ADR text, gate PASS records, module docstrings, byte-level inspection, zero identifier matches).

## DS-340W trace (SRC-001)

No influence found in code or tests. References exist only in governance
docs (DS340W_NOTES.md, DONOR_REUSE_MATRIX Phase 5R rows, permissions record,
fixture inventory, revision-3 plans). IMP's Phase 5R baseline/model layer
(`research/baseline_naive.py`, `model_spec.py`) is independent. Disposition:
NO_ACTION_NEEDED for code; re-annotate docs.

## CVD / Level 2 integration trace (SRC-003)

- Fixture: `ADMITTED-CVD-NVDA-ORDERFLOW-001` — FIXTURE_IMPORT from donor demo_data manifest (NVDA 2026-07-22), research_only, bars carry `source: "ibkr_tick"`. Active in order-flow tests + `fixture_order_flow.py` adapter.
- Code: `donor_patterns/cvd_formulas.py` (Lee-Ready aggressor, BVC, cumulative_delta, OFI) — REIMPLEMENTED_FROM_CONCEPT, feeding the entire order-flow lane. Q-series formula ledger (89 rows) hardened numerics (Q3 OFI-not-tradable-zero, etc.).
- Data/code separation: DATA provenance = fixture slice (donor-shaped, PIT-aligned, research-only); CODE provenance = independent reimplementation. No donor runtime data or code in IMP.
- IB L1/L2 runtime adapter: MISSING (authorized capability, WS04/WS05 gap).
- Correctness boundary: CVD semantics differences donor-vs-IMP → `CORRECTNESS_REVIEW_REQUIRED` at WS05 (no conclusion made here).

## Options integration trace (SRC-004)

- Fixture: `ADMITTED-OPTIONS-BIYA-001` — field-shape PORT_ADAPT, "no demo bytes admitted", research_only. Active in options tests + `fixture_options.py`.
- Code: `donor_patterns/options_lane.py` (liquidity_gate, confirmation_score) — REIMPLEMENTED_FROM_CONCEPT; zero donor terminology leakage (odte/herd/options_score/net_delta_oi/unusual_whales/ivolatility = 0 matches repo-wide).
- Bridge: `donor_bridge/internship_client.py` reads donor state files as research evidence only (no code import; isolation test enforces no execution path).
- Unusual Whales / iVolatility: NOT adopted, NOT required (trial-provider donor choice per IMG-003).

## Eric futuresX integration trace (SRC-005)

- Concepts adopted: contract-month/third-Friday/RTH/depth-imbalance patterns (`futures_lane.py`, `order_book_lane.py`) — PORT_ADAPT, stdlib-only, used by futures lane + fixture adapters.
- NOT adopted: IBKR client, Level-2 feed, Topstep, GUI, backtesting harness, paper executor. IB runtime = missing authorized work.
- Role: authorized source evidence for Futures (professor: "Eric's using IB data"); relationship to CCN = SEPARATE strategies (WS02 D2/D16, final decision WS05/07).

## Claude Code News integration trace (SRC-006)

NOT_YET_INTEGRATED — zero matches for its distinctive identifiers in IMP.
No import needed during WS03. It is a primary authorized Futures reference for
WS05/WS07 (news-driven execution model, Tradovate path, bracket/ladder
mechanics, one-trade-per-day discipline, honest-limits documentation).

## Donor fixture registry

| Fixture ID | Donor | Raw source | Transform | Current location | Lane | Tests | Status |
|---|---|---|---|---|---|---|---|
| ADMITTED-CVD-NVDA-ORDERFLOW-001 | SRC-003 CVD Bubble | `tradingCVDBubble-main/demo_data` manifest (NVDA 2026-07-22) | Bounded PORT_ADAPT slice, PIT-aligned to BIYA replay window; `source: "ibkr_tick"`; research_only | `tests/fixtures/providers/order_flow/nvda_order_flow_slice.json` | Order flow / Phase 10 | `test_order_flow_engine`, `test_order_flow_metaorder` | ADMITTED_AND_ACTIVE (research-only) |
| ADMITTED-OPTIONS-BIYA-001 | SRC-004 internship | `trade_log` field shapes (no demo bytes) | PORT_ADAPT field shapes; research_only | `tests/fixtures/providers/options/biya_options_slice.json` | Options / Phase 11 | `test_options_o6`, `test_options_contract` | ADMITTED_AND_ACTIVE (research-only) |
| (internal) ES synthetic / NVDA metaorder / MBO / signed-flow / earnings slices | none (whale/metaorder/options phases) | synthetic + public-data shaped | internal | `tests/fixtures/providers/...` | Whale/Options later phases | multiple | ADMITTED (no donor lineage) |

## Provider coupling map

| Provider | In IMP? | Evidence | Classification |
|---|---|---|---|
| Interactive Brokers | NO client; metadata only (`source: "ibkr_tick"` in fixtures; `provider_capabilities.py` listing; institutional_ignition/lending_adapter mentions) | grep | AUTHORIZED_PLATFORM_PROVIDER (scope-required for CVD L1/L2) — adapter MISSING |
| Tradovate | none | grep zero | DONOR_SPECIFIC (CCN) — not integrated |
| TradingView | none | grep zero | DONOR_SPECIFIC (CCN) |
| Unusual Whales / iVolatility | none | grep zero | DONOR_SPECIFIC (never adopted; not required) |
| Topstep | none | grep zero | DONOR_SPECIFIC (futuresX) |
| FinViz / FinViz Elite | yes — own P3.3 lane | IMP docs | AUTHORIZED_PLATFORM_PROVIDER |
| Anthropic | optional — MRA-002 | IMP README | AUTHORIZED_OPTION |
| Gemini | none | grep zero (excluded per ADR-GRIDIQ-001) | EXCLUDED |
| MongoDB | none in runtime (InMemory default; optional test-only) | IMP docs | NOT_REQUIRED |
| Moomoo OpenD / Tradier sandbox / SEC/FRED/COT/EIA/NOAA/CBOE | yes — observational + public providers | IMP README ADR table | AUTHORIZED_PLATFORM_PROVIDER |

## Mistaken-donor dependency graph (SRC-001/002)

| Artifact | Current purpose | Donor evidence | Independent requirement? | Dependents | Impact if removed | Proposed disposition | Native replacement needed? |
|---|---|---|---|---|---|---|---|
| storage/dataset_reader + projection_cache + bounded_memory_cache + research/dataset_pipeline | Phase 5R dataset projection/caching/manifest | ADR-GRIDIQ-001 (PORT_ADAPT) | YES — supporting architecture | evaluation.py, ui_api.projections, Phase 5R tests | FOUNDATIONAL | KEEP_AS_IS (code); re-annotate governance | NO — already native (PORT_ADAPT) |
| assistant/AssistantAuditStore | MRA audit store | phase gate 3 (concept) | YES | assistant services/tests | MEDIUM | KEEP_AS_IS | NO |
| ui api client/hooks + visualization | UI-001 surface | phase gates 2/4 (concept) | YES | UI tests | MEDIUM/LOW | KEEP_AS_IS | NO |
| DS-340W (any) | none in code | docs only | n/a | none | NO_DEPENDENTS | NO_ACTION_NEEDED | NO |

Removal blockers: none (no removal proposed). Migration order: governance
re-annotation first (WS07 Wave 1), then optional package renaming (D18).

## Native replacement candidates

**None required** — every GridIQ/DS-340W-derived component is already an
independent reimplementation behind its own ADR (PORT_ADAPT) or absent. The
"native replacement" for GridIQ was performed at introduction (8/16). Remaining
work is provenance re-annotation, not reimplementation.

## Removal candidates

**No code removal candidates.** Mistaken-donor scope exists only in governance
documents (supersede, don't delete — preserve history per program rules).
Donor-specific provider couplings that were never adopted (Unusual Whales,
iVolatility, Topstep, Gemini, MongoDB) need no removal since they are absent.

## Authorized donor features to preserve

- CVD order-flow formulas (INT-005) + admitted NVDA fixture (INT-006).
- Options lane gates (INT-007) + BIYA fixture (INT-008) + research bridge (INT-009).
- Futures contract/depth patterns (INT-010) — with architecture decision deferred.
- Squeeze bridge + provenance gates (INT-014/015) — original scope.
- Squeeze/catalyst research bridges (read-only evidence lanes).

## Tests protecting donor-derived behavior

| Test area | Behavior asserted | Fixture source | Classification |
|---|---|---|---|
| `tests/gridiq/test_required_future_tests.py` | Dataset projection/cache conformance (independent impl) | sample-research-rows.jsonl | PROTECTS_LEGITIMATE_REQUIREMENT (name references donor notes → annotate) |
| `tests/donor_bridge/*` (16 files) | Research bridges + cross-lane adapters (read-only) | squeeze server / internship state | PROTECTS_LEGITIMATE_REQUIREMENT |
| `tests/order_flow/*` (engine/metaorder) | CVD/OFI/aggressor on admitted fixture | ADMITTED-CVD-NVDA-ORDERFLOW-001 | PROTECTS_LEGITIMATE_REQUIREMENT (research-only fixture) |
| `tests/options/*` (o6, contract) | Options gates on admitted fixture | ADMITTED-OPTIONS-BIYA-001 | PROTECTS_LEGITIMATE_REQUIREMENT |
| `tests/futures/*`, Q-series formula tests | futures_lane/order_book patterns; formula ledger goldens | internal + fixtures | PROTECTS_LEGITIMATE_REQUIREMENT |

No test was found protecting mistaken-donor behavior or donor implementation
details; no deletions proposed.

## Documentation / governance corrections needed (pre-Heller-correction assumptions)

Documents that still treat GridIQ/DS-340W as legitimate donors and predate the
professor's correction (preserve as history, add superseded headers/annotations
at WS07 Wave 1):
- `docs/superpowers/governance/2026-08-14-donor-code-permissions.json`
  (PROTO-GRIDIQ-001 / PROTO-DS340W-001 "Lucas email permission" — the wrong Lucas)
- `docs/superpowers/decisions/2026-08-16-adr-gridiq-001-port-adapt-patterns.json`
  (authorization basis superseded; implementation stands independently)
- `docs/superpowers/governance/2026-08-16-gridiq-port-phase-gate.json`
- `docs/superpowers/decisions/2026-08-15-adr-donor-001-component-disposition.json`
- `docs/research/donors/DONOR_REUSE_MATRIX.md`, `GRID_IQ_NOTES.md`,
  `DS340W_NOTES.md`, `README.md`
- `docs/superpowers/plans/2026-08-14-revision-3-donor-integration-and-evidence-transition.md`,
  `2026-08-15-phase-0a-data-feasibility-and-donor-characterization.md`
- `docs/engineering/PROVIDER_DUPLICATION_AUDIT.md`, `docs/engineering/WORK_LOG.md`
  (donor-era entries), `docs/product/ux/competitive-research.md`,
  `docs/research/fixtures/2026-08-15-phase-0a-collection-fixture-inventory.md`
- `docs/superpowers/governance/2026-08-14-revision-3-donor-preservation-{before,difference}.json`

Note: the name "Heller" appears nowhere in IMP docs; the false legitimacy is
carried by the GridIQ/DS-340W donor records. Re-annotation should add the
correction context without erasing history.

## False-legitimacy chronology (Heller incident)

| Date | Event | Evidence |
|---|---|---|
| 2026-08-14 | Donor refs registered; permissions record cites "Lucas email permission"; revision-3 donor integration proposed; preservation evidence bound | `db3a7fb`, `68d0069`, `64cb64e` |
| 2026-08-16 | GridIQ PORT_ADAPT ADR + dataset subsystem implemented; donor bridge lanes added; Phase 10 CVD fixture admitted | `6adeeec`, `5ec19a7`, `3fe0b96`, `4dc6ca0` |
| 2026-08-18 | Phases 13–16, UI-002, MRA-001, donor integration lanes published | `d169cb8` |
| ~2026-08-28 | Professor corrects: Heller was the wrong Lucas | IMG-006 (email subject); controller §3 |
| 2026-09-06 | This program; correction not yet reflected in IMP governance docs | WS01/02/03 |

## Provenance-related technical debt

| ID | Category | Severity | Item | Evidence | Proposed |
|---|---|---|---|---|---|
| TD-P1 | PROVENANCE/STALE_DOCUMENTATION | P2 | Donor governance docs (9+) treat GridIQ/DS-340W as legitimate donors; pre-date correction | doc list above | WS07 Wave 1: supersede headers + correction context |
| TD-P2 | PROVENANCE/MIGRATION | P3 | `donor_patterns/` package name implies donor-derived code; content is independent lane formulas | docstrings | WS07: rename/annotate package or add namespace note |
| TD-P3 | PROVENANCE | P3 | `tests/gridiq/test_required_future_tests.py` name/docs reference donor notes | file head | WS07: annotate as conformance harness for independent impl |
| TD-P4 | PROVIDER_COUPLING | P2 | IB L1/L2 runtime adapter missing for authorized CVD capability | zero IBKR client matches | WS04/05: gap → COMPLETE backlog (not debt) |
| TD-P5 | STALE_DOCUMENTATION | P3 | short-squeeze snapshot manifest lag (WS01 finding) | manifest vs child HEAD | WS06 |

## Current-scope domains with no donor lineage

Bonds · Crypto · Whale (independent doctrine + EDGAR) · Industry ·
Government (independent providers) · Gold · Silver · Commodities →
`NO_DONOR_LINEAGE_IDENTIFIED` — acceptable per WS02; protected from removal.