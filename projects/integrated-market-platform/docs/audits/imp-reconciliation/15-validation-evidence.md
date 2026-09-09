# 15 — Validation Evidence

Status: **CURRENT (WS05 appended 2026-09-07)**. Every validation claim in the
program is recorded here with method, result, baseline, and confidence. No row
claims completion it did not produce. WS05 added a source-inspection evidence
table (no re-runs; WS04 baseline reused).

## Baseline (captured 2026-09-06, this session)

| Item | Value | Method | Confidence |
|---|---|---|---|
| Parent HEAD | `d691050` on `hardening/sprint-1-3-honesty` | `git log` | CONFIRMED |
| IMP child HEAD | `072e62e` on `main` (archived remote) | `git -C integrated-market-platform log` | CONFIRMED |
| Snapshot sync | `integrated-market-platform/` ≡ `projects/integrated-market-platform/` (only `__pycache__` differs) | `diff -rq` | CONFIRMED |
| Monorepo manifest | 3 governed snapshots (governed-ticker-metadata, equity-data-v1, short-squeeze) | `workspace-manifest.json` | CONFIRMED |
| Donor trees | 5 present locally + 2 absent; none contain `.git` | `ls -a` per folder | CONFIRMED |

## Prior forensic run evidence (2026-09-06, `codex/imp-forensic-reconciliation` worktree; recorded, not re-run this session)

| Item | Result | Where recorded | Confidence |
|---|---|---|---|
| FAST suite | 21 passed in 23.235s | `.planning/2026-09-06-forensic-reconciliation/findings.md` | MODERATE (prior-run log; not re-verified) |
| Full baseline | Running at cutoff (incomplete) | same | UNKNOWN (unfinished) |
| Historical closure claim | ~2209 tests / 1 failure / 92 errors; focused closed / global blocked | same; root plan | UNVERIFIED_CURRENT — requires reproduction before any classification |
| npm | PATH shim resolves missing `npm-cli.js` despite env reporting available | same | MODERATE |
| Docs checker | excludes `docs/platform/` and future audit path | same | MODERATE |
| UI | typecheck + tests logs exist in planning dir | `ui-tests.log`, `ui-typecheck.log` | UNVERIFIED_CURRENT |

## Program validation protocol (standing)

- Canonical IMP commands (from `projects/integrated-market-platform/AGENTS.md`,
  run at repo root):
  `python tools/imp.py env` · `format` · `lint` · `validate fast` ·
  `test focused <selector>` · `test affected` · `validate changed` ·
  `validate full` · `review` · `closure`
- Test inventory authority: `tools/validation_manifest.json`; Python validation
  authority: `tools/validate.py`.
- Monorepo guard: `python tools/monorepo_guard.py validate --remote`
  (parent; last documented pass 2026-09-04 per hardening plan P1-7).
- Validation must be manifest-driven and offline by default; live boundaries
  are opt-in only.

## WS01 evidence (2026-09-06, this session; all read-only)

| Item | Result | Method | Confidence |
|---|---|---|---|
| Donor source-file census | GridIQ 0 py / 0 js; CVD 1 py; internship 0 py; futuresX 0 py; Claude Code News 49 js/ts/mjs | `find` counts excluding venv/node_modules/caches | CONFIRMED |
| Donor total file counts | GridIQ 5; CVD 28,361; internship 48,272; futuresX 9,888 | `find -type f \| wc -l` | CONFIRMED |
| GridIQ db schema | tables: users/games/plays/cache/conversations/messages/alembic_version | `python sqlite3` introspection | CONFIRMED |
| futuresX IBKR usage | `reqMktDepth`, `placeOrder`, `127.0.0.1`, `ES` in `level2IBKR.cpython-313.pyc` and `ibkr_manager.cpython-313.pyc`; test `test_bracket_orders` pyc | `grep -a` bytecode strings | CONFIRMED |
| CVD remnant | `finviz/api_keys.py` (empty FinViz token), CVD_135 tick/wick reports, module pyc census (tick_collector, aggressor, session_grid, validate_moc, bvc, …) | file inspection + pyc name census | CONFIRMED |
| Internship remnant | state/*.json (BOXL watchlist w/ social signals; OCE signals w/ put/call ratios); module pyc census (odte_*, herd_scorer, paper_trader, …) | file inspection + pyc name census | CONFIRMED |
| Claude Code News source | 14 modules in `news/live/`; `src/` TradingView CDP client + MCP server; fingerprints MES/BRIEF_/Tradovate/tradingview/ladder/launchd/SIGUSR/TP CAPPED | `grep -rhoE` + file listing | CONFIRMED |
| External repo verification | GridIQ 200 (FastAPI+React+Gemini, Render); DS-340W 200 (R scripts match reuse matrix); tradingCVDBubble 200 (MongoDB+IBKR+FinViz, port probing); internship-project 200 (README docs incl. HANDOFF.md) | `read_url` (GitHub, 2026-09-06) | CONFIRMED (HTTP 200 + content match) |
| Git-history donor anchors | commits `6adeeec`, `4dc6ca0`, `3fe0b96`, `d169cb8`, `68d0069`, `64cb64e`, `db3a7fb`, `34abd14` | `git log --all -i -E --grep` | CONFIRMED |
| Short-squeeze snapshot lag | manifest `78b7467`; child `fix/frozen-followups` @ `9de7b2f` clean; 316-file diff vs snapshot | `git` + `diff -rq` | CONFIRMED |

No product validation commands were run during WS01 (read-only audit). Prior-run evidence above remains prior-run, not re-run.

## WS02 evidence (2026-09-06, this session; read-only)

| Item | Result | Method | Confidence |
|---|---|---|---|
| Tier A image census | 7 PNG present in `project-scope-images/` (640 KB–1.1 MB each) | `ls -la` / `find` | CONFIRMED |
| OCR tool availability | No tesseract/PIL/pytesseract/easyocr; Windows.Media.Ocr (en-US) available | probes | CONFIRMED |
| OCR extraction | 7/7 images transcribed (chars 1,349 / 1,870 / 2,185 / 1,568 / 1,758 / 1,564 / 1,605) | `.freebuff/ocr-images.ps1` (Windows.Media.Ocr, scaling to engine MaxImageDimension) | CONFIRMED (transcripts in `.freebuff/ocr-output/`) |
| Verbatim professor evidence | Central message IMG-005 (CVD/Level2 IB L1+L2 required; IB for options "maybe"; "Eric's using IB data"; integrated-platform mandate); IMG-001 "Both use Interactive Brokers API"; IMG-006 "This is Future Project."; IMG-003 options trial-providers + unprofitable disclaimer | OCR transcripts | CONFIRMED (high-text images) |
| Donor provenance confirmations | Hyuntae Jeong hzj5293@psu.edu (7/27); Eric Strzalkowski eks5832@psu.edu (7/31); Eric_futuresX circulated to CVD group 6/6/2026; Lucas Bichara ljb6293@psu.edu OneDrive "Claude Code News" (9/6) | IMG-002/003/004/006 | CONFIRMED |
| Heller correction marker | Email subject "Future Project — Hello Adam: This was not..." visible (dated ~8/28) | IMG-006 sidebar | CONFIRMED (subject only; full text via controller §3) |
| Roadmap cross-reference | IMP Five-Lane reconciliation (Platform/SS/Options/Futures/OrderFlow/Market Context), Swim-With-the-Whales doctrine, MASTER_ROADMAP v1.3 | `head` reads | CONFIRMED (Tier F) |

No product validation commands were run during WS02 (read-only audit + OCR).

## WS03 evidence (2026-09-06, this session; all read-only)

| Item | Result | Method | Confidence |
|---|---|---|---|
| Anchor commit catalog | `6adeeec` (8/16 GridIQ PORT_ADAPT + ADR + gate + tests), `5ec19a7` (8/16 storage modules), `3fe0b96` (8/16 donor bridge lanes), `4dc6ca0` (8/16 Phase 10 CVD fixture), `d169cb8` (8/18 phases/UI/MRA), `db3a7fb`/`68d0069`/`64cb64e` (8/14 donor governance) — all present in parent + child history | `git show --stat`, `git show -s --date=short` | CONFIRMED |
| ADR-GRIDIQ-001 | PORT_ADAPT accepted; "no donor code copy"; GridIQ Gemini/localStorage-auth/gridiq.db permanently excluded; phase-gate PASS rows for dataset_reader, ui api client/hooks, assistant audit store, research visualization | `git show 6adeeec:<adr>` + phase gate JSON | CONFIRMED |
| GridIQ module lineage | `storage/{dataset_reader,projection_cache,bounded_memory_cache}.py` + `research/dataset_pipeline.py` first added by `5ec19a7` (8/16); current code: sha256 content-addressing, logical_ids, ADR-DCACHE-001/RDATA-001 refs; zero GridIQ identifiers | `git log --diff-filter=A --follow` + file read | CONFIRMED |
| Identifier sweeps (IMP tree) | 0 matches repo-wide for: unusual_whales/ivolatility/odte/herd_scorer/net_delta_oi/options_score/options_bias (options donor); level2IBKR/ibkr_manager/live_rr/data_collecter/topstep/reqMktDepth (futuresX); Tradovate/NEWS_QTY/morning_brief/broker_ui/SIGUSR (CCN); nflverse/fantasy_football/gridiq (GridIQ); 0 "heller" matches in docs+src | `code_search` + `grep -ri` | CONFIRMED |
| Admitted fixture manifests | CVD: `donor_reference: tradingCVDBubble-main/demo_data manifest (NVDA 2026-07-22)`, research_only, bars `source: ibkr_tick`; Options: `internship-project trade_log field shapes (PORT_ADAPT; no demo bytes admitted)` | `cat` admission_manifest.json + slice heads | CONFIRMED |
| Production import edges | order_flow/cvd/aggressor/ofi/lob_baseline → donor_patterns.cvd_formulas; options execution/strategy → options_lane; futures/roll + fixture_futures → futures_lane/order_book_lane; providers/projections → donor_bridge.{projections,futures_client,bridge_depth_state,participant_adapter,opportunity_adapter}; institutional_13f + edgar adapters → edgar_whale | `grep -rn` src | CONFIRMED |
| Donor-pattern docstrings | "Lee-Ready aggressor and BVC estimators — reimplemented from CVD Bubble concepts"; "Options confirmation lane patterns — reimplemented from options_confirmation_engine concepts"; "Futures depth lane patterns — PORT_ADAPT from Eric_futuresX concepts (stdlib only)"; "Order-book depth helpers (PORT_ADAPT; no donor code copy)"; "Provenance/freshness/missingness gates — reimplemented from short-squeeze screener patterns"; edgar_whale "professor brief + ADR-WHALE-001" | `head` reads | CONFIRMED |
| Test lineage | `tests/gridiq/test_required_future_tests.py` (conformance harness for independent impl); `tests/donor_bridge/*` (16 files); fixture-based tests (`test_order_flow_engine`, `test_options_o6`, `test_options_contract`, `test_participant_derivatives`) | `grep -rln` + `ls` | CONFIRMED |
| Provider presence | IBKR: metadata only (fixture `source: ibkr_tick`, provider_capabilities, institutional_ignition/lending_adapter); no IBKR/Tradovate/TradingView/Topstep/Gemini/MongoDB client code | `grep -rli` | CONFIRMED |
| Doc-lineage (GridIQ/DS340W) | Referenced only in governance docs: permissions record, ADR-GRIDIQ-001, phase gate, ADR-DONOR-001, DONOR_REUSE_MATRIX, GRID_IQ_NOTES, DS340W_NOTES, revision-3 plans, PROVIDER_DUPLICATION_AUDIT, WORK_LOG, fixture inventory | `grep -rli` docs | CONFIRMED |

No product validation commands were run during WS03 (forensic read-only).

## WS04 evidence (2026-09-06/07, this session; fresh product validation)

Baseline: `projects/integrated-market-platform/` snapshot, parent
`hardening/sprint-1-3-honesty` @ `d691050`. Interpreter: project `.venv`
(3.11.15 uv-managed + `tzdata` + numpy/pymongo/scikit-learn, created per
AGENTS.md — the documented local validation environment; system `python` is
3.10 which cannot collect the suite). Live gates stripped by `validate.py` in
all runs; nothing network-enabled was executed.

| Date/time | Command (cwd = snapshot root) | Scope | Result | Duration | Failures | Interpretation |
|---|---|---|---|---|---|---|
| 2026-09-06 21:47 UTC | `tools/imp.py env` (python 3.10) | env | OK | — | — | Python 3.10.11; repo needs 3.11 (StrEnum) — first reproduction |
| 2026-09-06 21:48 UTC | `tools/imp.py validate fast` (3.10) | fast | ERROR | 0.2s | ImportError StrEnum | confirms LOCAL_DEVELOPMENT.md note |
| 2026-09-06 21:48 UTC | `validate fast` (3.11, no tzdata) | fast | ERROR | 0.4s | ZoneInfoNotFoundError America/New_York | needs tzdata in venv (AGENTS.md) |
| 2026-09-06 21:50 UTC | `validate fast` (3.11 venv + tzdata) | fast | ERROR | 0.7s | ModuleNotFoundError numpy | documented intelligence dep missing |
| 2026-09-06 21:52 UTC | `validate fast` (venv + tzdata + numpy/pymongo/sklearn) | fast | **PASSED 21 tests** | 9.3s | 0/0 | fresh FAST baseline |
| 2026-09-06 22:0x UTC | `validate domain order-flow --workers 2` | order-flow | 539 tests, 11 skipped | 98.4s | 1 failure (cross_lane golden) | failure = pre-existing dirty `fusion.py`/`opportunity.py` (WS01 exclusion) |
| 2026-09-06 | `validate domain options` | options | 583 tests, 11 skipped | 93.4s | 0/0 | passed |
| 2026-09-06 | `validate domain futures` | futures | 526 tests, 11 skipped | 97.5s | 0/0 | passed |
| 2026-09-06 | `validate domain short-intelligence` | short-intel | 64 tests | 1.9s | 0/0 | passed |
| 2026-09-06 | `validate domain participant` | participant | 503 tests, 11 skipped | 92.6s | 1 failure (same cross_lane) | dirty-tree only |
| 2026-09-06 | `validate domain sec` | sec | 37 tests | 1.5s | 0/0 | passed |
| 2026-09-06 | `validate domain macro` | macro | 304 tests | 6.8s | 0/0 | passed |
| 2026-09-06 | `validate domain energy` | energy | 324 tests | 6.8s | 0/0 | passed |
| 2026-09-06 | `validate domain ui` | ui | 759 tests, 13 skipped | 320.5s | 0/0 | passed |
| 2026-09-06 | `validate domain core` | core | 2808 tests, 48 skipped | 316.7s | 1 failure (same cross_lane) | dirty-tree only |
| 2026-09-06 | `validate changed` (JSON) | changed | 21 tests | 1.8s | 0/0 | **under-select**: monorepo `projects/` path prefix matches no suite globs (same as WORK_LOG 09-05) |
| 2026-09-06 | `validate full --workers 2 --json .local/ws04-full.json` | full | **3580 tests, 48 skipped** | 451.0s | **1 failure** (cross_lane golden), 0 errors | 60 suites; sole failure = excluded dirty-tree golden; **fresh FULL baseline (M6/M7 CLOSED)** |
| 2026-09-06 | `ui: npm test -- --run` | UI | 85 files / **438 passed** | 57s | 0 | passed |
| 2026-09-06 | `ui: npm run typecheck` | UI typecheck | PASSED | — | 0 | passed |

Historical reconciliation (evidence in 08): prior receipt
`artifacts/developer-workflow/full-validation-receipt-20260904.json` = 3487
passed/43 skipped/0/0 in 437s (59 suites) — consistent with WS04 fresh run;
WORK_LOG 09-02 `2209/1/92` = dirty-tree blocked baseline (now superseded);
WORK_LOG 09-05/06 `3569`/`3575` green — consistent with WS04 fresh run.

Source inspection evidence (read-only): lane module census
(`order_flow/*`, `options/*`, `futures/*`, `short_intelligence/*`,
`market_context/*`, `participant/*`, `xa01..xa05/*`, `ui_api/*`, `market_data/*`,
`tools/ibkr/*`); provider/fixture census (`tests/fixtures/providers/*`);
`ui/src` route + `laneRegistry.ts` census; API route census (`server.py`);
MASTER_ROADMAP grep (new domains absent); WORK_LOG/TECH_DEBT/PROGRAM_STATUS
read; `tools/ibkr` git provenance (`4853df0`, 2026-08-24, child repo).

## WS05 evidence (2026-09-07, this session; source-inspection only — WS04 baseline reused, no reruns needed)

WS05 is architecture-heavy; per controller §93 no full re-validation was run.
The WS04 fresh baseline (above: FAST 21, FULL 3580/48/1-excluded/0, UI 438,
typecheck clean) remains the runtime baseline and was not rerun. All WS05
conclusions rest on targeted read-only source inspection of the canonical
snapshot at `d691050`.

| Item | Result | Method | Confidence |
|---|---|---|---|
| Operational identity + mode model | `OperationalIdentity(mode,broker,account_id,portfolio_id,environment)`; mode validated against {DEMO,PAPER,LIVE}; cache keys = sha256(canonical(mode+broker+account+env+portfolio+logical_id)); demo views prefixed `demo:` | read `operational_identity.py`, `operating_modes.py` | CONFIRMED |
| Order lifecycle state set | CREATED, RISK_ACCEPTED/REJECTED, SUBMITTED, WORKING, ACTIVATED, PARTIALLY_FILLED, FILLED, CANCEL_PENDING, CANCELLED, REJECTED, EXPIRED; **no PREVIEW/CONFIRMED/REPLACE states**; transitions enforced by `validate_order_transition` | read `paper/contracts.py` | CONFIRMED |
| Preview→submission binding | Submit re-derives intent from request body; no preview_id/hash/cursor binding server-side; `confirmedRequestIsCurrent` (UI) covers instrument/side/quantity/order_type only; risk re-run at submit | read `ui_api/paper_projections.py` (`_preview/_submit`), `ui/src/components/paper/OrderTicket.tsx` | CONFIRMED |
| Idempotency | `lookup_idempotent_order` before submit; `LEDGER_ROUTE_LOCK` serializes ledger-mutating routes; UI generates one random attempt key per preview and reuses for submit | read `ui_api/server.py`, `paper/ledger.py`, `paperOrderDraft.ts` | CONFIRMED |
| Risk scope | `evaluate_risk` = kill switch + max_order/max_position/max_open_orders (share units); **grep: zero buying_power in `risk/`** → cash never checked | `grep -rn buying_power risk/` (0 hits); read `risk/decision.py` | CONFIRMED |
| Ledger scope | `PaperExecutionLedger.open_session` binds one instrument per session; `PaperAccountCreated` carries single instrument_id/symbol; `position_shares` share-denominated | read `paper/ledger.py`, `portfolio/ledger.py` | CONFIRMED |
| Options ledger numeric base | `build_options_ledger_state(*, initial_cash: float)` — float; equity ledger int minor units | grep + read `portfolio/options_ledger.py` | CONFIRMED |
| Futures sim P&L numeric base | `simulate_futures_roll`/`simulate_variation_margin_change`/`simulate_calendar_spread_pnl` use float (`round(...,6)`); `contracts/futures.py` uses Decimal | read `execution/simulator.py`, `contracts/futures.py` | CONFIRMED |
| L2 book semantics | `observational_state.apply_admitted` replaces whole book per DEPTH event (`update_semantics="SNAPSHOT"`); no insert/update/delete, no book TTL; `on_reconnect` resets admission sequence state only | read `market_data/observational_state.py`, `market_data/live_admission.py` | CONFIRMED |
| Depth staleness | Stale check gated `"L1" in capability or "SNAPSHOT" in capability` — DEPTH/ORDER_BOOK events never flagged STALE | read `market_data/live_admission.py` (lines ~203-224) | CONFIRMED |
| Live book payload quality | `build_live_order_book_payload` hardcodes `"book_state_valid": True`; exposes BBO only | read `ui_api/live_projections.py` | CONFIRMED |
| OFI pairing | `compute_multilevel_ofi` ranks levels (level N→N across snapshots); empty rank contributes whole size as add | read `order_flow/ofi.py` | CONFIRMED |
| CVD formulas | Lee-Ready + midpoint + tick rule + prev_dir in `classify_aggressor`; BVC erf-CDF w/ 50/50 fallbacks; CS OFI w/ NaN→0; cumulative delta no reset semantics | read `donor_patterns/cvd_formulas.py`, `order_flow/{aggressor,cvd}.py` | CONFIRMED |
| XA-01 asset classes | `XaAssetClass`/`InstrumentKind` lack CRYPTO; `SOVEREIGN_DEBT` present; bond fields flat strings; `paper/contracts.ASSET_CLASSES` includes CRYPTO/PREDICTION_MARKET (2nd vocabulary) | read `xa01/enums.py`, `xa01/contracts.py`, `paper/contracts.py` | CONFIRMED |
| Futures contract/roll/continuous | `FuturesContract` family-vs-contract + Decimal spec; `select_lead_contract` returns `execution_contract_id` from tradable contracts; continuous points carry contract_id (never executable in research engine) | read `contracts/futures.py`, `futures/{roll,continuous}.py` | CONFIRMED |
| IBKR tooling | `tools/ibkr/client.py` read-only REST allowlist + `RequestPacer` penalty box + capture; `tws_client.py` L1; **no reqMktDepth anywhere** | read `tools/ibkr/client.py`; grep reqMktDepth | CONFIRMED |
| Timestamp set | event/provider/available/received/ingested ns in `TimestampSet`; Moomoo naive ET parse documented; `event_time_ns_from_payload` never uses received as fake event time | read `market_data/{timestamps,provider_time}.py` | CONFIRMED |
| FRED vintage semantics | `vintage_date`, `revision_number`, `revision_delta`, ALFRED knowledge intervals, `cot_point_in_time_valid` publication-delay PIT | read `fred/*`, `contracts/futures.py` | CONFIRMED |
| Cache scoping | `AccountSnapshotCache` keys identity-scoped; per-entry refresh locks; stale-on-failure flags | read `ui_api/account_snapshot_cache.py` | CONFIRMED |
| Frontend query keys | workspace lane keys `["workspace", symbol, lane]` — no mode dimension; paper portfolio split by view mode; live canary keys account-scoped | read `ui/src/api/hooks.ts` | CONFIRMED |
| Restart recovery | SQLite event replay; config-hash compatible_resume; authority re-derived per execution mode env gate; live marks restored with `mark_quality="RESTORED"` | read `local_state/startup.py` | CONFIRMED |
| Tradier wire | fail-closed `BROKER_TRANSPORT_NOT_IMPLEMENTED` without fixture record; recorded responses only | read `providers/adapters/tradier_paper.py` | CONFIRMED |
| Cross-lane fusion | `fused_net_ev = gross_ev × occurrence × liquidity × futures_regime`; typed inputs w/ source_refs; already-net friction tolerance; occurrence uses uncalibrated squeeze probability (Phase 4 NOT_CALIBRATED) with disclaimer; golden failure = dirty-tree environmental | read `cross_lane/{fusion,opportunity}.py` (read-only; files untouched) | CONFIRMED |
| Evidence chain | LaneId/EvidenceSignal/provenance-class + DAG validation (MC-D20); participant `ParticipantEvidenceEnvelope` (participant_type/mechanism/directional_clarity/horizon/provenance/quality); EvidenceV1 specialist contract | read `cross_lane/evidence.py`, `participant/evidence.py`, `intelligence/contracts/evidence.py` | CONFIRMED |
| Mode authority doc | backend env-gated authority is the only safety boundary; frontend gating UX-only; LIVE-001 blocked; broker-paper separate gates | read `docs/architecture/MODE_AUTHORITY.md` | CONFIRMED |
| Secrets | `assert_no_secrets_in_payload` blocks responses; `credential_audit.py` redaction scan; IBKR client sanitizes; no exposure found | read `ui_api/server.py`, `credential_audit.py`, `tools/ibkr/client.py` | CONFIRMED |

No product validation commands were run during WS05; no code was changed.

## WS06 evidence (2026-09-07)

WS06 is a read-only audit; no full re-validation was needed (code untouched,
WS04 baseline stands). Targeted commands executed and recorded below.

| Command | Result | Notes |
|---|---|---|
| `python tools/validate.py changed --paths-file … --explain` (4 controlled cases) | Under-selection reproduced | (1) `projects/integrated-market-platform/src/...paper/execution.py` → **zero suites, full_suite_required=false** (monorepo prefix); (2) `fixtures/order_flow/admitted_cvd_nvda.json` → zero suites; (3) `config/modes.yaml` → zero suites; (4) `tests/fixtures/order_flow/foo.json` → zero suites. `src/market_platform_foundation/numeric.py` → UNKNOWN_EXECUTABLE_PATH → 5 core suites (blunt escalation). Mandatory invariants errored locally only due to system Python 3.10 (StrEnum) — environment, not selection (see below) |
| `.venv/Scripts/python.exe` version check | Python 3.11.15 present | System Python 3.10 first in PATH reproduced WS04 env note; `.venv` is the canonical interpreter |
| `grep -c shared modules in tools/validation_manifest.json` | `numeric.py/clock.py/errors.py/assertions.py/authority.py/evidence.py/market_sessions.py` = 0 hits each; `canonical.py` = 1; `operating_modes.py` = 1 | Shared-module glob coverage gap (07 §17.3) |
| `.local/ws04-full.json` per-suite parse | SLOWEST: platform 106.1s, donor_bridge 83.5s, ui1 79.2s, intelligence 52.2s, integration 50.1s, providers 38.9s; total 451.0s | MEASURED validation latency breakdown (07 §23 PERF-001) |
| `.local/developer-workflow/telemetry.jsonl` parse | validate domain ×22 (2463.7s), validate full ×4 (2130.7s), validate changed ×6 (443.6s ≈ 74s avg), test focused ×5, validate fast ×4 | Real agent command usage; changed escalations are not cheap (07 §18 DEV-001) |
| `python tools/check_docs_links.py` (`.venv` 3.11) | **OK: checked links in 162 governance markdown files** | Docs link audit clean (07 §20 DOC-006) |
| grep production-ready claims in `docs/` + `README.md` | 0 hits | No false production-readiness claims (07 §20 DOC-002) |
| Frontend endpoint-caller greps | `/paper/{account,positions,fills,risk}` = 0 non-test refs; `/workspace/:symbol/market-context` = no hook/route/lane | Dead-endpoint candidates DEL-01/02 (07 §15) |
| Third-party import census (`src/` + `tools/`) | numpy + scikit-learn (intelligence), pymongo (intelligence/xa04 mongo repos + tools/platform/bootstrap), ib_insync (`tools/ibkr/tws_client.py`), anthropic (assistant, stub default) | Dependency classification DEP-001 (07 §21) |
| Route/component census | App.tsx 564 lines; 25 explicit routes; 184 component files; 85 UI test files; schemas.ts 2,000 lines; laneRegistry 11 lanes | Frontend route/component/schema inventory (07 §4/§5/§12) |
| workspace-manifest.json + child HEADs (WS01 base) | SS manifest `78b7467` vs child `9de7b2f` vs plan `41f52bb`; GTM `1398da3` and EQ `ad54fb8` match snapshots | REPO-001 CONFIRMED stale (07 §22) |

Note: controlled `--explain` runs used the system Python 3.10 in PATH, where
mandatory invariants error on `StrEnum` import (an environment mismatch, not
selection behavior); the *selection verdicts* (which suites are chosen) are
independent of the interpreter and are the recorded evidence. `.venv` 3.11
was used for docs-link validation and JSON analysis.

## WS07 evidence (2026-09-07; planning-only — WS04 baseline reused, no product validation runs)

Per controller §70, WS07 runs targeted evidence checks only. No full suite was
executed; the WS04 fresh baseline (FAST 21 / FULL 3580/48/1-excluded/0 / UI
438 / typecheck clean) remains the standing runtime baseline.

| Item | Result | Method | Confidence |
|---|---|---|---|
| Canonical audit ingestion | All 14 WS01–WS06 files read; no internal contradiction requiring re-investigation (WS04's WS03 correction, WS06 FC-18/19 proofs, WS05 blocker register mutually coherent) | read_files (00–15) | CONFIRMED |
| `validate changed` under-selection structure re-verified | `EXECUTABLE_ROOTS = {src, tools, ui, manifests}` (no `projects`); suite globs child-relative (`tests/postroot/test_*.py` etc.); `_is_executable_or_config` excludes fixtures/config; `full_suite_required` runs `_offline_core_diagnostics` (5 suites) not the full 60 | read `projects/integrated-market-platform/tools/validate.py` L41/150-237 + `validation_manifest.json` | CONFIRMED (matches WS06 FC-18/FC-19) |
| Query-key mode-scoping re-verified | `queryKeys.workspaceOrderFlow = ["workspace", symbol, "order-flow"]` — no mode dimension; `queryKeys.test.ts` asserts account isolation but not mode isolation | read `ui/src/api/hooks.ts`, `queryKeys.test.ts` | CONFIRMED (matches WS05 ARCH-005 / WS06 UX-009) |
| Backlog quality-gate audit | 68 items; every P1 finding/blocker/missing domain/deletion/consolidation/test-gap maps to an owner; all acceptance criteria non-placeholder; all items in a wave | write-time reconciliation against 04/05/06/07/08/10/14 | CONFIRMED |
| No product validation commands run | n/a | per controller §70 (planning-heavy) | — |

No code was changed during WS07; no deletions; no remediation begun.

## G0 evidence (2026-09-07; execution — first post-reconciliation implementation increment)

G0 executed on the working tree (branch `hardening/sprint-1-3-honesty`); the
G0 changes are uncommitted working-tree state alongside pre-existing dirty
files. Canonical interpreter: `.venv/Scripts/python.exe` (Python 3.11.15) for
interactive runs; system Python 3.13.1 used here for the focused/FULL runs
(StrEnum-safe, same selection semantics).

| Item | Result | Method | Confidence |
|---|---|---|---|
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** in 2.6s | `tools/imp.py validate fast` (3.13) | CONFIRMED |
| FULL closure (final) | **3602 tests, 48 skipped, 1 failure, 0 errors** in 471.1s; sole failure = pre-existing dirty-tree `cross_lane` golden `test_bullish_active_squeeze_fusion_golden` (replay-hash mismatch from untouched `cross_lane/fusion.py` + `opportunity.py`) — same excluded known failure as the WS04 baseline | `tools/imp.py validate full --json` (final post-test-add run) | CONFIRMED |
| Test-count reconciliation | 3580 → 3602 (+22 net): 16 new G0 `tests/validation/` tests (12 selection + 4 env exit) minus 1 rename (`full_suite_required` → `core_checkpoint_required`) plus 7 real-manifest selection tests (RealManifestSelectionTests) | diff vs HEAD + final FULL count | CONFIRMED |
| Focused tooling tests | 81 passed, 9 subtests (validation + phase1 ADR verifier) | `pytest tests/validation tests/phase1` (3.13) | CONFIRMED |
| Docs-link validation | **OK: checked links in 163 governance markdown files** (162 + 1 new supersession notice) | `python tools/check_docs_links.py` | CONFIRMED |
| Monorepo guard | `monorepo validation passed` (exit 0): snapshot integrity, allowed paths, manifest consistency, overlay parity | parent `tools/monorepo_guard.py validate` | CONFIRMED |
| Controlled `validate changed` cases (selection semantics via `select_changed`) | A parent-prefixed `projects/integrated-market-platform/src/...paper/execution.py` → normalized `src/...`, OWNING_SUITE_SELECTION platform (+neighbors) = same as child-relative; A2 child-relative standalone → same platform selection; B `tests/fixtures/providers/order_flow/admitted_cvd_nvda.json` → OWNING order_flow+participant (+neighbors), no silent under-selection (was 0 suites at WS06); C `config/of03/workflows.json` → OWNING of03 (+neighbors); D mapped shared module `market_sessions.py` → DEPENDENT platform; D2 unbounded `numeric.py` → CORE_CHECKPOINT_ESCALATION (5 core diagnostics); E `docs/platform/MASTER_ROADMAP.md` → DOCUMENTATION_ONLY_CHECK (documentation cheap check only); F unknown executable → CORE_CHECKPOINT_ESCALATION UNKNOWN_EXECUTABLE_PATH; G evidence-only → EVIDENCE_ONLY_CHECK; H deleted/renamed path → still selects by path | `select_changed` API + `--explain` | CONFIRMED |
| `imp.py env` exit semantics | healthy env → exit 0; hard failures (`python_version_supported=False`) → exit 1 (unit-tested via `test_env_command_exit_code_tracks_hard_failures`); optional node missing → degraded, never fails | live run + `tests/validation/test_imp_cli.py` | CONFIRMED |
| Short-squeeze snapshot parity | parent snapshot `projects/short-squeeze-project/` == child `fix/frozen-followups` @ `9de7b2f` tracked content + declared `snapshot_overlay` (7 hardening-pin files); manifest records `9de7b2f` | `git ls-files` census + `monorepo_guard` | CONFIRMED |
| Donor-governance supersession | 12/12 enumerated records annotated in place with `SUPERSEDED`/`HISTORICAL` + Heller-correction context; ADR-DONOR-001 (byte-for-byte hash-bound by the phase1 verifier) superseded via the standing `2026-09-07-donor-authority-supersession-notice.md`; zero governance doc treats GridIQ/DS-340W as current-authorized | grep sweep + `test_adr_verifier.py` (PASS) | CONFIRMED |
| Roadmap/program truth | MASTER_ROADMAP § Domain capability state lists all 15 mandated domains with truthful states + references 12/13; PROGRAM_STATUS updated | grep + read | CONFIRMED |
| AGENTS.md canonical edit target | `projects/integrated-market-platform/` stated as canonical; child repo mirrors; `validate changed` supports both embeddings | read | CONFIRMED |
| Namespace annotations | `donor_patterns/__init__.py` + `tests/gridiq/test_required_future_tests.py` annotated (no renames, zero behavior change) | read | CONFIRMED |
| Cleanup | `pytest-equity-premerge-20260824/` already absent at G0 start; `pytest-equity-postmerge-20260824c/` = 0-file census but OS-wedged directory entry (WinError 5, cannot list/remove without elevation) → **UNRESOLVED, documented**; child CI workflow copies replaced with `README.md` pointers (parent CI canonical) | `find` census + `git status` | CONFIRMED |

## G1 evidence (2026-09-07; execution — Wave 1 identity slice)

G1 executed on the working tree (branch `hardening/sprint-1-3-honesty`)
uncommitted alongside pre-existing dirty files. Canonical interpreter:
`.venv/Scripts/python.exe` (Python 3.11.15).

| Item | Result | Method | Confidence |
|---|---|---|---|
| Identity inventory | One canonical vocabulary: `xa01.enums.XaAssetClass`/`InstrumentKind`; `paper.contracts.ASSET_CLASSES` = deprecated compat view (kept, PREDICTION_MARKET remains paper-local); no other asset-class enum exists as runtime authority (futures `FuturesFamily` is a family taxonomy, not an asset-class vocabulary) | grep sweep of `XaAssetClass`/`ASSET_CLASSES`/`InstrumentKind` | CONFIRMED |
| Vocabulary consolidation | `XaAssetClass` + `CRYPTO`, `BOND`; `InstrumentKind` + `CRYPTO_PAIR`, `BOND`, `CONTINUOUS_SERIES`, `COMMODITY_SPOT`; `Tradability` enum (TRADABLE/REFERENCE_ONLY/SYNTHETIC/CONTINUOUS_SERIES) | code + tests `tests/xa01/` | CONFIRMED |
| Crypto identity | `register_crypto_pair(base, quote, venue, network, product_type, provider alias)`; BTC/USD != BTC/USDT != venue-qualified; bare BTC never a pair; 9 tests | `tests/xa01/test_xa01_crypto_identity.py` | CONFIRMED |
| Bond identity | `register_bond` typed (issuer, CUSIP/ISIN alias, maturity, coupon, par, credit tier); corporate + sovereign; 9 tests | `tests/xa01/test_xa01_bond_identity.py` | CONFIRMED |
| Commodity identity | GOLD/SILVER explicit with `commodity_sector`; economic != spot != futures contract != continuous series; GLD proxy relationship; 7 tests | `tests/xa01/test_xa01_commodity_identity.py` | CONFIRMED |
| Tradability + continuous-future guard | `xa01.tradability` (default/validate/assert/is_executable), `resolver.resolve_executable_alias` (alias → continuous series rejected), `paper.contracts.build_user_order_intent` rejects non-executable refs (INSTRUMENT_NOT_EXECUTABLE); 6 required regression cases covered; 20 tests | `tests/xa01/test_xa01_tradability_guard.py` | CONFIRMED |
| Cross-asset collisions | EQUITY BTC != CRYPTO BTC/USD; EQUITY GC != COMMODITY GOLD; FUTURE ROOT ES != EQUITY ES; bond issuer vs equity ticker; option underlying vs contract; 7 tests | `tests/xa01/test_xa01_cross_asset_collisions.py` | CONFIRMED |
| Serialization | round-trip + deterministic encode + legacy-decode safe defaults + enum stability + XA-04 codec round trip; 9 tests | `tests/xa01/test_xa01_g1_serialization.py` | CONFIRMED |
| Focused regression | xa01 71 (12 existing + 59 new) · futures 65 · options 147 · contracts 38 · xa02 21 · xa03 31 · xa04 30 (6 skip) · xa05 15 · platform paper/operational-identity/broker 114 — all OK | `unittest discover` per suite | CONFIRMED |
| Paper compatibility | existing paper/broker/moomoo/ledger suites green; legacy equity intent build unchanged | `tests/platform/test_paper_p1` + others | CONFIRMED |
| Docs updates | XA-01 spec (vocabulary/tradability/invariant), MASTER_ARCHITECTURE cross-asset, PROGRAM_STATUS, WORK_LOG G1 entry, backlog BL-0101..0104, root-cause RC-004/RC-005 notes | read/diff | CONFIRMED |
| Scope protection | no portfolio migration, no risk redesign, no provider-live work, no product surfaces, no Live execution enablement (LIVE-001 untouched; live-execution-safety `CERTIFIED_ASSET_CLASSES` untouched) | git diff scope review | CONFIRMED |
| Backlog | BL-0101..0104 CLOSED_BY_G1; BL-0105 (G2 portfolio) remains OPEN and NOT STARTED | 12-master-backlog.md | CONFIRMED |
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** in 2.6s | `tools/imp.py validate fast` (3.11 venv) | CONFIRMED |
| Changed-validation | **1727 tests, 12 skipped, 1 failure, 0 errors** in 349.5s; sole failure = known pre-existing dirty-tree `cross_lane` golden (same test, same reason, G1 did not touch `cross_lane/`) | `tools/imp.py validate changed` | CONFIRMED |
| FULL closure | **3661 tests, 48 skipped, 1 failure, 0 errors** in 611.0s; sole failure = `test_bullish_active_squeeze_fusion_golden` (pre-existing dirty `cross_lane` golden, excluded baseline; unchanged by G1) | `tools/imp.py validate full` | CONFIRMED |
| Test-count reconciliation | 3602 → 3661 (+59) — exactly the 59 new G1 identity tests across `tests/xa01/` (10 crypto + 8 bond + 7 commodity + 18 tradability-guard + 8 collisions + 8 serialization); no test removed or weakened | diff vs G0 FULL count | CONFIRMED |
| Docs-link validation | **OK: checked links in 163 governance markdown files** | `python tools/check_docs_links.py` (3.11 venv) | CONFIRMED |
| Failure classification | 1 KNOWN_PREEXISTING_FAILURE (cross_lane golden); 0 NEW_G1_FAILURE; 0 ENVIRONMENTAL; 0 INTENTIONALLY_GATED | FULL log + `git status` cross_lane untouched | CONFIRMED |

## G2 evidence (2026-09-07; execution — Wave 1 portfolio core, BL-0105)

G2 executed on the working tree (branch `hardening/sprint-1-3-honesty`)
uncommitted alongside pre-existing dirty files. Canonical interpreter:
`.venv/Scripts/python.exe` (Python 3.11.15) for interactive/FAST/changed
docs runs; system Python 3.13.14 (`py -3.13`) for the FULL closure run
(StrEnum-safe, same selection semantics, consistent with G0 practice).

| Item | Result | Method | Confidence |
|---|---|---|---|
| Portfolio archaeology | Truth sources inventoried: `portfolio/ledger.py` (fill-driven equity, int minor units, parity baseline), `portfolio/options_ledger.py` (float, BL-0106 merge target), `paper/ledger.py` (event-sourced Paper lifecycle), `intelligence/execution` `PaperPortfolioSnapshotV1` (DERIVED_PROJECTION), `intelligence/live_canary` `LivePortfolioSnapshotV1` (DERIVED_PROJECTION), provider DTOs (PROVIDER_INPUT), frontend models (DERIVED_PROJECTION). No second mutable canonical ledger exists | grep sweep `PortfolioSnapshot`/`position_shares` + read of each owner | CONFIRMED |
| Canonical model | `portfolio/canonical.py`: `PortfolioKey` (account_id + mode + optional broker/portfolio/environment; mode validated against {DEMO,PAPER,LIVE}); `CashBalance` (per-currency Decimal); `ValuationMark` (price/currency/mark_type/source/source_time/observed_at/data_status); `PortfolioPosition` (quantity + quantity_unit SHARES/CONTRACTS/BASE_UNITS/FACE_VALUE, native_currency, multiplier, cost basis, realized P&L, valuation); `PositionValuation`; `PortfolioSnapshot` (key, base_currency, cash, positions, native + base totals, valuation_status, provenance); `CanonicalPortfolio` store with controlled mutation boundary (`apply_position_input`/`apply_snapshot` same-key enforced/`apply_cash`/`apply_adjustment`) and deterministic to_dict/from_dict (Decimal→string) | code + tests | CONFIRMED |
| Admission gate | `portfolio/admission.py` reuses XA-01 tradability: admitted = TRADABLE_SECURITY(EQUITY/ETF_FUND), OPTION_CONTRACT, FUTURE_CONTRACT, CRYPTO_PAIR; rejected = FUTURE_FAMILY, CONTINUOUS_SERIES, COMMODITY_ECONOMIC, COMMODITY_SPOT, INDEX_BENCHMARK, CURRENCY_UNIT, FX_PAIR, SOVEREIGN_SECURITY, BOND (reference-only), any non-TRADABLE tradability, unknown kinds/classes, and kind/asset-class mismatches (fail closed) | `tests/portfolio/test_canonical_admission.py` (23 tests) | CONFIRMED |
| Valuation engine | `portfolio/valuation.py` asset-aware dispatch: equity/ETF qty×mark; option contracts×premium×multiplier (multiplier from identity metadata, never assumed 100); futures notional + variation P&L vs reference (never equity-style cash value, negative contracts signed); crypto base-units × pair price (quote-currency native, USDT≠USD without explicit conversion); bond face × explicit price basis (PAR_PERCENT / CURRENCY_PER_FACE_UNIT) with optional accrued interest; wrong-currency/wrong-instrument marks rejected; missing/stale marks explicit, never zero; Decimal precision preserved | `tests/portfolio/test_valuation.py` (28 tests) | CONFIRMED |
| Cash + FX boundary | `portfolio/fx.py`: explicit `FxRate` + `FxFactsBundle`; `convert` never falls back to 1:1 and never invents a rate; missing FX → `MISSING_FX`; stale rate → `STALE`; inverse derivation exact; base aggregation reports COMPLETE/PARTIAL/MISSING_FX/STALE; native values retained alongside base totals | `tests/portfolio/test_cash_and_fx.py` (19 tests) | CONFIRMED |
| Account/mode isolation | Paper A ≠ Paper B ≠ Demo A ≠ Live A for equity/option/future/crypto positions and cash; no shared global position dict; snapshot identity hash account- and mode-scoped; foreign-key snapshot ingestion rejected | `tests/portfolio/test_isolation.py` (13 tests) | CONFIRMED |
| Provider normalization | `portfolio/provider_normalization.py`: provider symbol → XA-01 alias → canonical position input (option contract CONTRACTS+multiplier 100; future contract CONTRACTS; crypto pair BASE_UNITS + quote native; equity SHARES + cost basis); unknown/ambiguous → `UNRESOLVED_INSTRUMENT` (no mutation); continuous-future alias → NON_EXECUTABLE (no admission); reference bond alias → NON_EXECUTABLE | `tests/portfolio/test_provider_normalization.py` (10 tests) | CONFIRMED |
| Persistence | deterministic serialize (sort_keys JSON byte-identical), round-trip preserving Decimal exactness, account/mode scope, canonical instrument ids, cash-by-currency, multiplier/price-basis, incomplete valuation status (MISSING_MARK / MISSING_FX); legacy minimal shape decodes with safe defaults | `tests/portfolio/test_persistence.py` (9 tests) | CONFIRMED |
| Paper dual-run parity | `portfolio/paper_adapter.py` projects `PaperExecutionLedger` into a canonical snapshot using only public projections; parity verified for empty ledger cash (1,000,000.00), long position (qty/average/market value), cash after buy (985,000.00), partial reduction (60 remaining, realized 800.00), reversal (−50 shares), and stable identity hash | `tests/portfolio/test_paper_parity.py` (7 tests) | CONFIRMED |
| Backlog | BL-0105 updated to `COMPLETE_BY_G2` in `12-master-backlog.md`; BL-0106 (options ledger merge) and BL-0107 (futures Decimal) remain OPEN follow-ons | read/diff | CONFIRMED |
| Docs updates | G2 portfolio spec (single canonical architecture home), MASTER_ARCHITECTURE cross-asset pointer, PROGRAM_STATUS G2 row, WORK_LOG G2 entry; no portfolio contract duplicated into other authoritative docs | read/diff | CONFIRMED |
| Scope protection | no buying-power formula, no margin engine, no risk-engine, no trading-lifecycle redesign, no provider-live work, no Live execution enablement, no frontend/UI changes (paper/ledger.py and options_ledger.py untouched) | git diff scope review | CONFIRMED |
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** in 2.8s | `tools/imp.py validate fast` (3.11 venv) | CONFIRMED |
| Changed-validation | **1836 tests, 12 skipped, 1 failure, 0 errors** in 320.4s; sole failure = known pre-existing dirty-tree `cross_lane` golden `test_bullish_active_squeeze_fusion_golden` (same test, same reason; G2 did not touch `cross_lane/`); validation suite green after reconciling the offline-suite inventory count (60 → 61 for the new `portfolio` suite) | `tools/imp.py validate changed --json .local/g2-changed.json` (3.11 venv) | CONFIRMED |
| FULL closure | **3770 tests, 48 skipped, 1 failure, 0 errors** in 544.3s; sole failure = `test_bullish_active_squeeze_fusion_golden` (pre-existing dirty `cross_lane` golden, excluded baseline; unchanged by G2); `portfolio` suite 109 passed | `tools/imp.py validate full --json .local/g2-full.json` (py -3.13) | CONFIRMED |
| Test-count reconciliation | 3661 → 3770 (+109) — exactly the 109 new G2 portfolio tests across `tests/portfolio/` (admission 23 + cash/FX 19 + isolation 13 + paper parity 7 + persistence 9 + provider normalization 10 + valuation 28); no test removed or weakened (one inventory assertion reconciled: offline-suite count 60 → 61 in `tests/validation/test_validation_manifest.py`) | diff vs G1 FULL count + per-file counts | CONFIRMED |
| Docs-link validation | **OK: checked links in 163 governance markdown files** | `python tools/check_docs_links.py` (3.11 venv) | CONFIRMED |
| Failure classification | 1 KNOWN_PREEXISTING_FAILURE (cross_lane golden); 0 NEW_G2_FAILURE; 0 ENVIRONMENTAL; 0 INTENTIONALLY_GATED | FULL + changed logs + `git status` cross_lane untouched | CONFIRMED |

## G3 evidence (2026-09-07; execution — trading-correctness increment, BL-0201..BL-0209)

G3 executed on the working tree (branch `hardening/sprint-1-3-honesty`)
uncommitted alongside pre-existing dirty files. Canonical interpreter:
`.venv/Scripts/python.exe` (Python 3.11.15) for interactive/FAST/changed
runs. The separate child repo
`integrated-market-platform/` (repo root) is NOT the active G3 working tree
and was not edited.

| Item | Result | Method | Confidence |
|---|---|---|---|
| BL-0201 preview binding | Server-side preview record (`paper/preview.py` PreviewStore) binds preview_id + intent digest + account/mode/instrument/side/qty/type/limit + risk-policy revision + portfolio-state revision + bounded TTL; `verify_preview_submit` fail-closed (PREVIEW_NOT_FOUND/EXPIRED/INTENT_MISMATCH/ACCOUNT/MODE/PORTFOLIO_STALE/POLICY_STALE); UI route requires current matching preview; risk re-run at submit. Strategy automation path: `PreparedPaperExecution` with content-derived idempotency key verified at `_submit_prepared` (PREPARED_EXECUTION_IDEMPOTENCY_MISMATCH), and explicit prepared risk-reference-price handoff (approved_notional_minor // approved_quantity) into the final submit-time financial recheck | `tests/trading_correctness/test_preview_binding.py` (10) + `test_strategy_authority.py` (9) | CONFIRMED |
| BL-0202 cash enforcement | Internal gate `_enforce_buy_side_cash_availability` + broker gate `_enforce_broker_buy_side_cash_availability` on executable submit paths: required <= available (working-order obligations = working_remaining × effective price × multiplier); LIMIT prices at limit; MARKET uses conservative bar close/high (internal) or live mark (broker); fail-closed REQUIRED_PRICE_MISSING; strategy reference price from approved risk decision cannot bypass insufficient cash; currency from canonical instrument metadata when intent currency absent; exact boundary accepted, +1 unit rejected; partial-fill shrinks reservation; replace recomputes reservation | `tests/trading_correctness/test_financial_enforcement.py` (8) + `test_strategy_authority.py` | CONFIRMED |
| BL-0203 identity admission | Canonical admission at order boundary: tradable securities / option contracts (multiplier) / specific futures admitted; family/continuous/reference rejected; unresolved alias fails closed UNKNOWN_INSTRUMENT; ES family cannot masquerade as equity; arbitrary legacy equity fallback closed; operator fixtures register BIYA/AAPL canonically; MSFT preview mutation reaches PREVIEW_INTENT_MISMATCH specifically | `tests/trading_correctness/test_identity_admission.py` (11) | CONFIRMED |
| BL-0204 remainder truth | Requested/submitted/filled/working-remainder projection corrections; working obligations use `working_remaining` (not original desired quantity); REPLACED included in open obligation states and preview portfolio revision | `tests/trading_correctness/test_lifecycle_remainder.py` (14) | CONFIRMED |
| BL-0205 replace lifecycle | REPLACE_PENDING → REPLACED non-terminal evidence; filled quantity immutable; replace total >= cumulative filled; working remainder = replacement authorized total − fills; replace revision/count persisted in OrderReplaced body (replace_revision projection bug fixed); idempotent duplicate replace; REPLACED remains working obligation; cancel after replace; price/quantity replace recomputes cash; replay reconstructs truth | `tests/trading_correctness/test_replace_lifecycle.py` (13) | CONFIRMED |
| BL-0206 late-fill | `_cancel_broker_paper_order` calls cancel-time late-fill capture; late fill appended once with reconciliation provenance; duplicate fill IDs ignored; cancel does not erase prior fills; reconciliation event recorded; terminal broker orders not continuously re-polled; Tradier/Moomoo cancel status events via `events` collection (CancelDispatch fixture returns empty `events` stream) | `tests/trading_correctness/test_late_fill.py` (6) | CONFIRMED |
| BL-0207 idempotency + locking | Per-ledger `RLock` (`submit_critical_section`) covers idempotency lookup → conflict detection → intent/risk/order/fill append → `record_idempotent_order`; BROKER_PAPER records idempotency BEFORE external provider call and releases lock before the network call; thread-barrier concurrency proof (one order, one fill), IDEMPOTENCY_CONFLICT same-key/different-intent, independent account scope, restart/replay reconstruction; no GIL-reliance as concurrency proof | `tests/trading_correctness/test_idempotency_replay.py` (7) | CONFIRMED |
| BL-0208 CVD sessions | Deterministic CVD session semantics (`order_flow/cvd.py`); explicit reset, never silent; no exchange-calendar modeling added (out of scope) | `tests/trading_correctness/test_cvd_session.py` (5) | CONFIRMED |
| BL-0209 pretrade dispatch | Typed `evaluate_pretrade` / `PreTradeRiskContext` wired into BOTH internal and broker-paper BUY financial enforcement paths; typed context consumes canonical G1 identity + G2 cash; hooks can reject; hooks cannot bypass account/mode authority; default path performs authoritative checks; no duplicate conflicting financial implementation | `tests/trading_correctness/test_pretrade_hooks.py` (8) | CONFIRMED |
| Suite total | 87 baseline tests + 4 new strategy reference-price regression tests = **91 passed** | `unittest discover -s tests/trading_correctness` | CONFIRMED |
| Affected regressions | governed intelligence flow (test_build01_23_lifecycle) green with bars=[]; platform broker P4/P44/P4C/reconciliation/status-apply 93 passed; operator surface fixes incl. E5 parallel preview-first submit 16 passed; paper p0/p1/p31 passed; validation suite (82) incl. offline-suite count 62 reconciled; intelligence suite green | per-suite `unittest` runs | CONFIRMED |
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** in 3.1s | `tools/imp.py validate fast --json artifacts/g3-fast-report.json` (3.11 venv) | CONFIRMED |
| Changed-validation | **3224 tests, 48 skipped, 1 failure, 0 errors** in 547.2s; sole failure = known pre-existing dirty-tree `cross_lane` golden `test_bullish_active_squeeze_fusion_golden` (same test, same reason; G3 did not touch `cross_lane/` — the dirty fusion.py occurrence-weight hardening predates this increment) | `tools/imp.py validate changed --json artifacts/g3-changed-report.json` (3.11 venv) | CONFIRMED |
| FULL closure | **3861 tests, 48 skipped, 1 failure, 0 errors** in 450.2s; sole failure = `test_bullish_active_squeeze_fusion_golden` (pre-existing dirty `cross_lane` golden, excluded baseline; unchanged by G3) | `tools/imp.py validate full --json artifacts/g3-full-report.json` (3.11 venv) | CONFIRMED |
| Manifest | `trading_correctness` suite registered in `tools/validation_manifest.json` (offline, tiers changed+full, parallel_safety GLOBAL_STATE_MUTATION, source globs cover paper/risk/xa01/cvd/intelligence-execution/provider-adapters/ui_api); offline count 61 → 62 reconciled in `tests/validation/test_validation_manifest.py` with comment; pre-existing manifest schema 1.0 → 1.1 changes preserved | read/diff | CONFIRMED |
| Fixture corrections | P44/P4/P4C/reconciliation/status-apply broker ledgers apply live marks (UI-path parity, production gate unweakened); CancelDispatch fake returns `events=()`; E5 parallel test uses preview-first submit with PREVIEW_PORTFOLIO_STALE refresh-retry (never bypasses preview authority, still genuinely concurrent) | read/diff + runs | CONFIRMED |
| Failure classification | 1 KNOWN_PREEXISTING_FAILURE (cross_lane golden); 0 NEW_G3_FAILURE; 0 ENVIRONMENTAL; 0 INTENTIONALLY_GATED | FULL + changed logs + `git status` cross_lane untouched by G3 | CONFIRMED |

## G3.1 evidence (2026-09-08; closure — cross_lane golden-blocker reconciliation, BL-0210)

G3.1 executed on the working tree (branch `hardening/sprint-1-3-honesty`)
uncommitted alongside pre-existing dirty files. Canonical interpreter:
`.venv/Scripts/python.exe` (Python 3.11.15). G3.1 closes the single
pre-existing FULL failure that G3 had documented as an excluded baseline; it
makes no production-gate changes.

| Item | Result | Method | Confidence |
|---|---|---|---|
| BL-0210 occurrence honesty | `cross_lane/fusion.py` `_occurrence_weight` returns `(weight, fail_reason)` and never silently returns 1.0 for missing occurrence evidence: squeeze-aligned template with no hazard AND no occurrence model output → `UNAVAILABLE` (`OCCURRENCE_UNAVAILABLE`); non-squeeze-aligned path → factor 1.0 with explicit `OCCURRENCE_UNAVAILABLE` quality flag; `PAYOFF_ALREADY_NET_TOLERANCE` replaces the magic 1e-9; formula_ledger entries bumped to `shared_opportunity_v2+CROSS_LANE_FUSION_V2`; `SHARED_P4_EV_OPPORTUNITY_SPEC.md` updated to fusion v2 fail-closed occurrence | `tests/cross_lane/test_opportunity_fusion.py` (+6) + `test_portfolio_p5.py` (+3) | CONFIRMED |
| Golden reconciliation | `nvda_opportunity_fusion_expected.json` regenerated to hardened V2 semantics; hash forensics (`.local/g31-hash-forensics.py`) reconstruct the pre-hardening V1 snapshot and diff every field against V2, proving the golden delta is the intended occurrence-weight change, not drift | read/diff + forensics script | CONFIRMED |
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** in 2.5s | `tools/imp.py validate fast --json .local/g31-fast.json` | CONFIRMED |
| Changed-validation | **3233 tests (3185 passes + 48 skipped), 0 failures, 0 errors** in ~500s | `tools/imp.py validate changed --json .local/g31-changed.json` | CONFIRMED |
| FULL closure | **3870 tests, 48 skipped, 0 failures, 0 errors** — the previously excluded cross_lane golden failure is GONE; no known failure remains | `tools/imp.py validate full --json .local/g31-full.json` | CONFIRMED |
| Failure classification | 0 KNOWN_PREEXISTING_FAILURE; 0 NEW_G31_FAILURE; 0 ENVIRONMENTAL; 0 INTENTIONALLY_GATED | FULL + changed logs | CONFIRMED |
| Test-count reconciliation | 3861 → 3870 (+9: 6 opportunity-fusion + 3 portfolio-p5); no test removed or weakened | diff vs G3 FULL count + per-file counts | CONFIRMED |
| Docs closure | formula_ledger.json + SHARED_P4_EV_OPPORTUNITY_SPEC.md (fusion v2); backlog BL-0210 added; WORK_LOG G3.1 entry; PROGRAM_STATUS G3.1 row; 00-program-state refreshed; this section | read/diff | CONFIRMED |

## G4 evidence (2026-09-08; execution — multi-asset accounting kernel, BL-0211)

G4 executed on the working tree (branch `hardening/sprint-1-3-honesty`)
uncommitted alongside pre-existing dirty files. Canonical interpreter:
`.venv/Scripts/python.exe` (Python 3.11.15). G4 builds the canonical
multi-asset accounting foundation on the G3.1 green baseline.

| Item | Result | Method | Confidence |
|---|---|---|---|
| G3.1 precondition repair | Three callers of the already-landed fail-closed `register_future_contract` (no safe default multiplier) were updated to supply explicit multipliers (2 portfolio tests, 1 trading-correctness test, 1 xa01 adapter test) and a spec-less-future fail-closed test was added; portfolio suite 109 and trading_correctness 91 restored green before G4 work began | per-suite `unittest` runs | CONFIRMED |
| BL-0211 instrument economics | `portfolio/instrument_economics.py`: typed fail-closed `InstrumentEconomics` resolved from XA-01 descriptors (economics_from_descriptor) and runtime instrument refs (economics_from_instrument_ref); quantity unit kind-driven (SHARES/CONTRACTS/BASE_UNITS/FACE_VALUE); derivative multiplier required > 0 (MISSING/INVALID_CONTRACT_MULTIPLIER); missing currency and unknown kinds fail closed; multiplier=1 valid only for equity/ETF; no symbol heuristics | `tests/portfolio/test_instrument_economics.py` (27) | CONFIRMED |
| BL-0211 accounting kernel | `portfolio/accounting.py`: one exact-Decimal authority — notional / equity_notional / option_premium / future_exposure / future_variation_pnl / market_value_by_kind / cash_requirement_by_kind / realized_pnl_on_close / working_reservation; binary float rejected at the kernel boundary (UNSUPPORTED_BINARY_FLOAT); string-exact boundary conversion (Decimal(str)) for legacy seams | `tests/portfolio/test_instrument_economics.py` + `tests/trading_correctness/test_multi_asset_accounting.py` | CONFIRMED |
| BL-0211 canonical position validation | `CanonicalPortfolio.upsert_position` now rejects derivative positions without CONTRACTS quantity unit or positive multiplier (new `INVALID_POSITION_ECONOMICS`); serialization boundaries stay permissive (migration rule) | portfolio suite (136) | CONFIRMED |
| BL-0211 options convergence | `portfolio/options_ledger.py` rewritten to Decimal-exact (cash/premium/realized Decimal; float only at JSON presentation boundary in `options/execution.py`); module marked NON-AUTHORITATIVE compatibility over the O9 simulation lane; `build_canonical_option_positions` adapter aggregates same-identity partial fills into canonical CONTRACTS positions with exact premium cost basis; O9 golden snapshots unchanged (17 O9 tests green) | `tests/options/test_options_o9.py` (17) + multi-asset option proofs | CONFIRMED |
| BL-0211 futures Decimal | exact 1-contract / multi-contract / long-short sign / no-drift / replay proofs through the kernel + canonical valuation; family/continuous identities remain non-executable | `tests/trading_correctness/test_multi_asset_accounting.py` | CONFIRMED |
| BL-0211 per-currency obligations | `working_order_obligations_by_currency`, `currency_available_cash_minor`, per-currency `order_intent_financial_check` + `PreTradeRiskContext.currency_cash_minor`; USD bucket passes, matching non-USD bucket passes, missing bucket fails closed INSUFFICIENT_SETTLEMENT_CURRENCY — never 1:1; paper gates supply the single account-currency bucket (behavior unchanged) | multi-asset currency proofs + trading_correctness (122) | CONFIRMED |
| Affected regressions | options 147, execution, cross_lane, providers, ui1 (13), ui2 (5) all green; platform 474 (2 skipped) green | per-suite `unittest` runs | CONFIRMED |
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** | `tools/imp.py validate fast --json .local/g4-fast.json` | CONFIRMED |
| Changed-validation | **3347 tests, 48 skipped, 0 failures, 0 errors** | `tools/imp.py validate changed --json artifacts/g4-changed-report.json` (3.11 venv) | CONFIRMED |
| FULL closure | **3929 tests, 48 skipped, 0 failures, 0 errors** | `tools/imp.py validate full --json artifacts/g4-full-report.json` (3.11 venv) | CONFIRMED |
| Test-count reconciliation | 3870 → 3929 (+59: 27 instrument-economics + 31 multi-asset-accounting + 1 xa01 spec-less-future); no test removed or weakened | diff vs G3.1 FULL count + per-file counts | CONFIRMED |
| Failure classification | 0 KNOWN_PREEXISTING_FAILURE; 0 NEW_G4_FAILURE; 0 ENVIRONMENTAL; 0 INTENTIONALLY_GATED | FULL + changed logs | CONFIRMED |

## G5 evidence (2026-09-08; execution — canonical incremental L2 order-book engine, BL-0212)

G5 executed on the working tree (branch `hardening/sprint-1-3-honesty`)
uncommitted alongside pre-existing dirty files. Canonical interpreter:
`.venv/Scripts/python.exe` (Python 3.11.15). G5 resolves AB-003/ARCH-003
(snapshot-only L2 book), ARCH-006 (rank-pair OFI mis-pairing), and ARCH-009
(hardcoded `book_state_valid: True`) on the G4 green baseline.

| Item | Result | Method | Confidence |
|---|---|---|---|
| BL-0212 canonical contracts | `order_flow/order_book/contracts.py`: `DepthOperation` INSERT/UPDATE/DELETE/RESET; `DepthSide` BID/ASK; `DepthUpdate` carries instrument_id, side, operation, price, size, position (advisory rank metadata), source, source_time_ns, received_time_ns, sequence, subscription_id, provider_event_id, schema_version, provenance; Decimal-exact price/size via `Decimal(str(v))` boundary normalization (binary float rejected, non-finite rejected); explicit `ApplyResult` outcomes APPLIED/NOOP/DUPLICATE/REJECTED/INVALIDATED/RESET_APPLIED with reason + sequence_state + validity + generation + update_count; `BOOK_MODEL_VERSION=order_book/v1`, `DEPTH_EVENT_SCHEMA_VERSION=depth_event/v1` | `tests/order_flow/test_order_book_*.py` (82) | CONFIRMED |
| BL-0212 canonical engine | `order_flow/order_book/engine.py` `IncrementalOrderBook`: price-keyed side-ordered levels (bids descending, asks ascending); INSERT inserts + shifts deterministically (identical duplicate = benign NOOP; conflicting duplicate = STRUCTURALLY_CORRUPT invalidate — never silent overwrite); UPDATE replaces only that level (missing level fails closed LEVEL_NOT_FOUND, recovery required when book was valid); DELETE removes level + closes rank gap (absent price = benign NOOP; price/rank disagreement cannot delete an unrelated rank); position must agree with price-order rank or event is rejected; zero size only on DELETE; RESET clears all levels + advances generation + clears sequence continuity + marks RESET_PENDING (RESET is not DELETE); `book_state_valid` is derived truth; engine never reads a wall clock; deterministic `state_hash()` | sequence/reset/operations tests | CONFIRMED |
| BL-0212 sequence semantics | `SequenceState` NO_SEQUENCE (provider has no usable sequence — book operates but status truthfully says unprotected), BASE (first anchor), CONTIGUOUS, DUPLICATE (explicit no-op, never double-applied), GAP (fail closed → INVALID, recovery-required), REGRESSION (fail closed → INVALID, no silent mutation); recovery-required invalidation rejects further non-RESET events until explicit reset/snapshot | `tests/order_flow/test_order_book_sequence.py` | CONFIRMED |
| BL-0212 generation/reset | subscription identity gate: late events from an old subscription generation are explicitly REJECTED (GENERATION_MISMATCH); generation advances on RESET / subscription change; reset clears sequence continuity; fresh updates after reset re-establish validity | `tests/order_flow/test_order_book_reset_generation.py` | CONFIRMED |
| BL-0212 freshness | `order_flow/order_book/freshness.py`: pure `evaluate_book_freshness(book, as_of_time_ns, policy)` → FRESH / STALE / INVALID / UNAVAILABLE; thresholds live in `FreshnessPolicy` (default 5s), never projections; INVALID beats STALE; a stale-but-valid book is STALE, never silently collapsed to INVALID and never presented valid without qualifier; deterministic for fixed as_of_time | `tests/order_flow/test_order_book_freshness.py` | CONFIRMED |
| BL-0212 snapshot compatibility | `replace_from_snapshot` is an explicit ingestion compatibility mode — RESET-then-load, never confused with incremental UPDATE; deterministic projection to legacy snapshot dict shape with additive `book_status`/`book_status_reason`/`sequence_status`/`generation`/`model_version`/timestamps; `ingest_snapshot_dict` round-trips legacy snapshots through the canonical engine; snapshot import failures invalidate with the book cleared (no partial state) | `tests/order_flow/test_order_book_snapshot.py` | CONFIRMED |
| BL-0212 deterministic replay | `order_flow/order_book/replay.py`: same events → identical state + identical SHA-256; replay after restart reconstructs same levels; duplicate events never double-apply; RESET boundaries and sequence-gap invalidation replay identically; no wall clock inside replay; `measure_replay_throughput` evidence in `g5-order-book-replay-evidence.json` (~93k/45k/23k events/sec at 10/50/100 levels, 5 repeats — PERFORMANCE_MEASURED, no production claim) | `tests/order_flow/test_order_book_replay.py` + evidence JSON | CONFIRMED |
| BL-0212 empty/one-sided/crossed | empty book = UNAVAILABLE (fresh) / INVALID (cleared); one-sided book structurally valid but two-sided metrics unavailable (never fabricate the missing side); crossed book explicitly represented (`is_crossed`, spread=None) — no silent normal spread from corrupt crossed state | `tests/order_flow/test_order_book_basic.py` | CONFIRMED |
| BL-0212 OFI rank-shift (ARCH-006) | `ofi.py` adds versioned `OFI_METHOD_MULTILEVEL_PRICE_ALIGNED` / `compute_multilevel_ofi_price_aligned`: levels keyed by exact price, signed size deltas (bid positive / ask negative, insertion/removal on appear/disappear) — identical to OFI derivable from the canonical incremental event log; head-insert / middle-delete rank shifts cannot fabricate rank-paired events; legacy rank-sum v1 method retained unchanged; `compute_ofi` routes the new method; formula_ledger entry `of.multilevel_ofi_price_aligned` (count 96→97) | `tests/order_flow/test_order_book_ofi_integration.py` | CONFIRMED |
| BL-0212 store + API truth (ARCH-009) | `market_data/observational_state.py`: per-instrument canonical engines (`canonical_books`); full-book provider pushes enter via `replace_from_snapshot`; stored book payloads now carry derived `book_state_valid` + `book_status`/`book_status_reason`/`sequence_status`/`generation`/`model_version`/timestamps; `ui_api/live_projections.py` `book_state_valid` is derived from the payload (hardcoded `True` removed, structural fallback only when flags absent); `book_engine_for()` exposes the engine | `tests/market_data/test_canonical_book_integration.py` (5) + `git diff` of store/projection | CONFIRMED |
| CVD/order-flow authority | G3 CVD session semantics untouched: `order_flow/cvd.py` session-anchor/reset metadata (BL-0208, `session_anchor`/`session_reset`/`previous_anchor`) preserved with its tests; existing order-flow OFI/liquidity/impact/forecast consumers unchanged in authority — canonical engine projects to the legacy snapshot shape they consume | `tests/trading_correctness/test_cvd_session.py` (8) + `tests/order_flow/` (66) | CONFIRMED |
| G1–G4 safety regression | identity admission, Demo/Paper/Live isolation, preview binding, buying-power enforcement, multi-asset accounting, replace/remainder, late-fill, idempotency/replay, CVD sessions — trading_correctness **122 passed** | `tests/trading_correctness/` per-suite runs | CONFIRMED |
| Affected regressions | order_flow 66 green (incl. existing LOB/OFI/queue/engine/metaorder/gates); CVD session 8 green; market_data store tests green | per-suite `unittest` runs | CONFIRMED |
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** | `tools/imp.py validate fast` | CONFIRMED |
| Changed-validation | **3481 tests, 48 skipped, 0 failures, 0 errors** | `tools/imp.py validate changed` (3.11 venv) | CONFIRMED |
| FULL closure | **4016 tests, 48 skipped, 0 failures, 0 errors** | `tools/imp.py validate full` (3.11 venv) | CONFIRMED |
| Test-count reconciliation | 3929 → 4016 (+87: 82 order_book semantics + 5 canonical-book store integration); no test removed or weakened | diff vs G4 FULL count + per-file counts | CONFIRMED |
| Failure classification | 0 KNOWN_PREEXISTING_FAILURE; 0 NEW_G5_FAILURE; 0 ENVIRONMENTAL; 0 INTENTIONALLY_GATED | FULL + changed logs | CONFIRMED |

## G6 evidence (2026-09-08; execution — IBKR observational L1/L2 provider adapter, BL-0213)

G6 executed on the working tree (branch `hardening/sprint-1-3-honesty`)
uncommitted alongside pre-existing dirty files. Canonical interpreter:
`.venv/Scripts/python.exe` (Python 3.11.15). G6 delivers the canonical IBKR
observational runtime boundary on the G5 green baseline.

| Item | Result | Method | Confidence |
|---|---|---|---|
| BL-0213 runtime package | `providers/ibkr_observational/` (14 modules): adapter, capability, capture, constants, contracts, diagnostics, errors, identity, l1, lifecycle, mapping, pacing, rank; transport protocol injected (fakes in tests); `tools/ibkr` not imported by runtime `src` | package inventory + import grep | CONFIRMED |
| XA-01 identity boundary | IB conId/qualified contract → canonical `instrument_id` via `identity.py`; ambiguous/family/continuous fail closed before subscribe | identity + lifecycle tests | CONFIRMED |
| L1 accumulation | Subscription-local bid/ask/bid_size/ask_size/last/last_size + delayed variants; unknown values remain `None`; delayed/entitlement state explicit and re-published (no real-time PASS after downgrade) | `test_ibkr_observational_l1.py` | CONFIRMED |
| L2 mapping | Verified `operation` 0=INSERT/1=UPDATE/2=DELETE; `side` 0=ASK/1=BID in `constants.py`; `mapping.py` pure decode; zero values use explicit None checks (not `value or -1`) | `test_ibkr_observational_l2.py` + constants evidence | CONFIRMED |
| Rank/position translation | Adapter-local rank state: INSERT resolves rank; same-price UPDATE; price-changing UPDATE leaves no stale level; DELETE resolves price from rank/canonical state; rank disagreement → fail closed/RESET | L2 + lifecycle tests | CONFIRMED |
| Sequence honesty | `DepthUpdate.sequence=None` always; engine reports NO_SEQUENCE; reqId and callback count never fabricated as sequence | L2 tests | CONFIRMED |
| Subscription lifecycle | subscribe_l1/l2, cancel_l1/l2, replay registration, disconnect/reconnect, generation replacement, reqId mapping, late old-reqId rejection, local pacing/caps | `test_ibkr_observational_lifecycle.py` | CONFIRMED |
| Entitlement/pacing/errors | Evidence-backed provider codes only (CONNECTION/ENTITLEMENT/DELAYED_DATA/PACING/CONTRACT/SUBSCRIPTION/UNKNOWN_PROVIDER_ERROR); missing L2 entitlement cannot leave valid depth | lifecycle + L1/L2 tests | CONFIRMED |
| Capture/replay | `capture_path=None` → memory-only; explicit path → journal permitted; replay through adapter normalization reproduces canonical book state/hash | `test_ibkr_observational_capture_replay.py` | CONFIRMED |
| Safety boundary | No `placeOrder`/`cancelOrder`/`modifyOrder`/`exerciseOptions`; no execution capability registration (`IBKR_FORBIDDEN_CAPABILITIES`); offline mode makes no provider request | `test_ibkr_observational_safety.py` + grep | CONFIRMED |
| Store integration | `ObservationalStateStore` remains sole canonical state owner; L2 events feed G5 `IncrementalOrderBook` | canonical-book integration + adapter tests | CONFIRMED |
| Performance | L1 callback aggregation ~33.9k/s; L2 callback→DepthUpdate ~29.4k/s; L2→canonical book apply ~18.6k/s — **ADAPTER_PERFORMANCE_MEASURED** (dev machine, not production IBKR) | `test_ibkr_observational_performance.py` | CONFIRMED |
| Live provider | **LIVE_PROVIDER_UNVERIFIED** — no real IBKR session collected in this closure | offline-only validation | CONFIRMED |
| G5 L2 regression | order_book 82 + canonical-book integration 5 = **87** green | unittest discover | CONFIRMED |
| trading_correctness | **122** green | unittest discover | CONFIRMED |
| providers suite | **216** green (includes 91 ibkr_observational) | unittest discover | CONFIRMED |
| market_data suite | **49** green | unittest discover | CONFIRMED |
| FAST | **21 passed, 0 skipped, 0 failures, 0 errors** in 6.3s | `tools/imp.py validate fast` | CONFIRMED |
| Changed-validation | **3572 tests, 48 skipped, 0 failures, 0 errors** in 619.967s | `tools/imp.py validate changed` | CONFIRMED |
| FULL closure | **4107 tests, 48 skipped, 0 failures, 0 errors** in 588.906s | `tools/imp.py validate full` | CONFIRMED |
| Test-count reconciliation | 4016 → 4107 (+91: `test_ibkr_observational_{l1,l2,lifecycle,safety,capture_replay,performance}.py` + `ibkr_observational_support.py`); CHANGED 3481 → 3572 (+91 same); no test removed or weakened | diff vs G5 FULL + per-file counts | CONFIRMED |
| Failure classification | 0 KNOWN_PREEXISTING_FAILURE; 0 NEW_G6_FAILURE; 0 ENVIRONMENTAL; 0 INTENTIONALLY_GATED | FULL + changed logs | CONFIRMED |

## G7 evidence (2026-09-08; execution — runtime wiring / provider capability convergence)

G7 executed on the working tree uncommitted alongside pre-existing dirty files.
Canonical interpreter: `.venv/Scripts/python.exe` (Python 3.11.15). G7 converges
provider capability truth and wires canonical observational state into existing
research/order-flow/options/futures analytics without formula redesign or
execution authority.

| Item | Result | Method | Confidence |
|---|---|---|---|
| Runtime capability facade | `RuntimeCapabilityRegistry` — multi-axis state (implemented, runtime, entitlement, timeliness, health, observational authority); execution capabilities forbidden | `test_g7_runtime_capability.py` | CONFIRMED |
| Provider selection | `ObservationalProviderSelector` — deterministic, fail-closed; no silent fallback; replay-only for LIVE_PROVIDER_UNVERIFIED | `test_g7_runtime_capability.py` | CONFIRMED |
| Lane requirements | `lane_requirements.py` — explicit lane→capability graph with readiness evaluation | `test_g7_observational_lanes.py` | CONFIRMED |
| Observational lane runtime | `ObservationalLaneRuntime` — canonical store → L1/CVD/price-aligned OFI/book-features/options/futures with provenance | `test_g7_observational_lanes.py` | CONFIRMED |
| Runtime composition | `ObservationalRuntimeComposition` — transport injection into G6 adapter; no src→tools/ibkr import | `test_g7_runtime_composition.py` | CONFIRMED |
| Cross-lane bridge | `cross_lane/runtime_inputs.py` — canonical evidence snapshots for fusion inputs; fusion formulas unchanged | `test_g7_runtime_inputs.py` | CONFIRMED |
| Replay determinism | Same store state → same `evidence_hash` | lane + composition tests | CONFIRMED |
| Safety boundary | No execution methods on adapter; options/futures analytics NON_AUTHORITATIVE | composition + capability tests | CONFIRMED |
| Performance | Capability resolution 1000 iterations < 1s — **RUNTIME_PERFORMANCE_MEASURED** (dev machine) | `test_g7_runtime_composition.py` | CONFIRMED |
| Live provider | **LIVE_PROVIDER_UNVERIFIED** retained | offline validation only | CONFIRMED |
| G7 focused suite | **39** tests green (per-file inventory below) | unittest discover on four `test_g7_*.py` modules | CONFIRMED |
| G7 per-file test inventory | `test_g7_runtime_capability.py` **14** · `test_g7_observational_lanes.py` **14** · `test_g7_runtime_composition.py` **9** · `test_g7_runtime_inputs.py` **2** → **39** total | `def test_` enumeration + unittest discover (2026-09-08 reconciliation) | CONFIRMED |
| G7 count reconciliation | Prior informal per-file listing summed **41** because `test_g7_runtime_composition.py` was recorded as **11**; authoritative count is **9** (8 `RuntimeCompositionTests` + 1 `RuntimePerformanceTests`). FULL/CHANGED delta **+39** matches the inventory exactly; no G6→G7 test removals | diff vs G6 FULL + per-file counts | CONFIRMED |
| Capability authority hierarchy | **`ProviderRegistry`** = implemented-capability metadata authority · **`RuntimeCapabilityRegistry`** = runtime-state/readiness facade over that authority (not a competing metadata source) · **`VerifiedCapabilityRegistry`** = bounded Moomoo probe/verification evidence only (`market_data/capability_registry.py`; legacy `live_runtime` path). G7 selection/convergence uses `RuntimeCapabilityRegistry` + `ObservationalProviderSelector`; no duplicate runtime-capability authorities | read `providers/runtime_capability.py`, `providers/registry.py`, `market_data/capability_registry.py` | CONFIRMED |
| providers suite | **232** green (+16 net from G6 216) | unittest discover | CONFIRMED |
| market_data suite | **74** green (+25 net from G6 49) | unittest discover | CONFIRMED |
| trading_correctness | **122** green | unittest discover | CONFIRMED |
| FAST | **21/0/0/0** | `tools/imp.py validate fast` | CONFIRMED |
| CHANGED | **3611/48/0/0** in ~558s | `tools/imp.py validate changed` | CONFIRMED |
| FULL closure | **4146/48/0/0** | `tools/imp.py validate full` | CONFIRMED |
| Test-count reconciliation | 4107 → 4146 (+39 G7); CHANGED 3572 → 3611 (+39); no test removed or weakened | diff vs G6 | CONFIRMED |
| BL-0301 status | **NOT CLOSED** — broader IBKR adapter (account/secdef/bars) remains separate scope | backlog wording review | CONFIRMED |

## G8 evidence (2026-09-08; IBKR runtime convergence + dependency-direction correction)

G8 executed on the working tree uncommitted alongside pre-existing dirty files.
Canonical interpreter: `.venv/Scripts/python.exe` (Python 3.11.15). First G8
pass wired outer TWS transport and live_runtime composition (focused 63,
CHANGED 3674/48/0, FULL 4209/48/0) but `live_runtime.py` still constructed
`tools.ibkr.observational_transport`. Correction moved construction to
`tools/ibkr/runtime_bootstrap.py` and injected the transport through
`IbkrObservationalTransportProvider` / `IbkrTransport`.

| Item | Result | Method | Confidence |
|---|---|---|---|
| Dependency direction | Zero AST implementation imports of `tools.ibkr` under `src/market_platform_foundation/` | `test_g8_src_tools_boundary.py` | CONFIRMED |
| Concrete transport owner | `tools/ibkr/runtime_bootstrap.py` constructs `IbkrObservationalTransport` | bootstrap tests | CONFIRMED |
| Protocol injection | `IbkrObservationalAdapter.__init__(*, transport: IbkrTransport)` keyword-only | boundary test `get_type_hints` | CONFIRMED |
| Moomoo compatibility | `LiveObservationalRuntime` Moomoo `push_feed` path unchanged | G8 composition test + source read | CONFIRMED |
| G6 mappings | operation 0 / side 0 preserved on callback bridge | observational transport tests | CONFIRMED |
| Safety | no execution methods on transport/adapter; no portfolio mutation | G6 safety + G8 boundary | CONFIRMED |
| Performance | **LIVE_RUNTIME_PERFORMANCE_MEASURED** (dev machine; not provider-network; not SLA) — see artifacts/g8-runtime-performance.json | `test_g8_runtime_performance.py` | CONFIRMED |
| Live provider | **LIVE_PROVIDER_UNVERIFIED** — L1/L2 NOT_ATTEMPTED/offline verified; contract resolution offline; entitlement environment unavailable; IBKR CVD FAILED_SAFE | env inspection + G8 CVD tests | CONFIRMED |
| Focused G8 | **74** green (63 retained + 11 correction tests) | unittest on G8 modules | CONFIRMED |
| ibkr suite | **63 / 0 / 0 / 0** | `validation_worker.py --suite-id ibkr` | CONFIRMED |
| providers suite | **257 / 0 / 0 / 0** | validation worker | CONFIRMED |
| market_data suite | **104 / 0 / 0 / 0** | validation worker | CONFIRMED |
| order_flow suite | **148 / 0 / 0 / 0** | validation worker | CONFIRMED |
| xa01 suite | **72 / 0 / 0 / 0** | validation worker | CONFIRMED |
| trading_correctness | **122 / 0 / 0 / 0** | validation worker | CONFIRMED |
| G5 order_book regression | **82** green | `tests/order_flow/test_order_book_*.py` | CONFIRMED |
| G6 ibkr_observational regression | **91** green | `tests/providers/test_ibkr_observational_*.py` | CONFIRMED |
| G7 runtime regression | **39** green | four `test_g7_*.py` modules | CONFIRMED |
| FAST | **21 / 0 / 0 / 0** | `tools/imp.py validate fast` | CONFIRMED |
| CHANGED | **3686 / 48 / 0 / 0** in 541.758s (`core_checkpoint_required=true`; new tests covered here) | `tools/imp.py validate changed --json artifacts/g8-correction-changed.json` | CONFIRMED |
| FULL | Prior G8 FULL **4209 / 48 / 0 / 0** reused; expected FULL if rerun ≈ **4221** (+12 correction tests). Not rerun: Python/test blast radius covered by CHANGED; untouched suites unchanged from 4209 | prior G8 FULL + this CHANGED | CONFIRMED |
| BL-0301 | **PARTIAL** | backlog wording vs observational L1/L2 only | CONFIRMED |
| BL-0304 | **PARTIAL** | no fabricated IBKR trades | CONFIRMED |
| BL-0305 | **PARTIAL / BLOCKED_BY_LIVE_EVIDENCE** | offline lifecycle proven; live canary absent | CONFIRMED |

## G10 evidence (2026-09-08; IBKR depth TTL + provider surface convergence)

G10 executed on the working tree. Canonical interpreter: `.venv/Scripts/python.exe` (Python 3.11.15). G10 closure bookkeeping verified in `14g-g10-current-state-matrix.md` and `WORK_LOG.md`; no reopen required for G11.

| Item | Result | Method | Confidence |
|---|---|---|---|
| Depth TTL admission | `depth_admission.py` + live admission DEPTH branch; stale depth blocks authoritative OFI/book features | `test_g10_depth_freshness.py` | CONFIRMED |
| Historical/account contracts | `historical_bars.py`, `account_observation.py` normalization (no portfolio mutation) | G10 provider tests | CONFIRMED |
| Shutdown | Idempotent adapter/composition shutdown | `test_g10_runtime_lifecycle.py` | CONFIRMED |
| G9 CVD preserved | tick-by-tick → classified tape path unchanged | G9 regression | CONFIRMED |
| Focused G10 | **30 / 0 / 0 / 0** | unittest on `test_g10_*.py` | CONFIRMED |
| Starting FULL (G10 entry) | **4250 / 48 / 0 / 0** | prior G10 WORK_LOG | CONFIRMED |
| Live provider | **LIVE_PROVIDER_UNVERIFIED** | env inspection | CONFIRMED |
| BL-0301 | **PARTIAL** at G10 exit — query runtime wiring deferred to G11 | backlog | CONFIRMED |
| BL-0303 | **IMPLEMENTATION_COMPLETE** | depth TTL regression green | CONFIRMED |

## G11 evidence (2026-09-09; IBKR read-only query surface convergence)

G11 executed on the G10 working tree. Canonical interpreter: `.venv/Scripts/python.exe` (Python 3.11.15).

| Item | Result | Method | Confidence |
|---|---|---|---|
| Query protocol boundary | `IbkrReadOnlyQueryProvider` (src) + `IbkrOuterReadOnlyQueryProvider` (outer); no src→tools import | `test_g11_query_convergence.py`, `test_g8_src_tools_boundary.py`, ibkr safety tests | CONFIRMED |
| Contract/secdef | XA-01 admission subordinate; 12 fail-closed contract tests | `test_g11_query_convergence.py` | CONFIRMED |
| Historical bars | Outer fetch → normalization → canonical bar vocabulary; PIT cutoff | `test_g11_historical_runtime.py` | CONFIRMED |
| Account read | `READ_ONLY_OBSERVATIONAL`; no portfolio/ledger mutation | `test_g11_account_observation.py` | CONFIRMED |
| Runtime composition | Query attach on `ObservationalRuntimeComposition`; startup/shutdown matrix | `test_g11_runtime_composition.py` | CONFIRMED |
| Capability readiness | `IBKR_CONTRACT_RESOLUTION`, `IBKR_HISTORICAL_BARS`, `IBKR_ACCOUNT_READ` axes separate | `test_g11_capability_readiness.py` | CONFIRMED |
| Capture/replay | Deterministic query normalization; account ID redaction in capture | `test_g11_replay.py` | CONFIRMED |
| Live canary harness | `tools/ibkr/canary.py` fail-closed; bounded requests; no execution surface | `test_g11_canary_safety.py` | CONFIRMED |
| G10 depth TTL regression | Preserved | `test_g10_depth_freshness.py` + G11 perf depth path | CONFIRMED |
| G9 CVD regression | Preserved | `test_g9_ibkr_cvd.py` | CONFIRMED |
| Performance | **G11_RUNTIME_PERFORMANCE_MEASURED** — contract 36.38 ms; hist bar 10.48 ms; account 9.41 ms; query round-trip 15.71 ms/1k; depth TTL 12.07 ms; capability 25.36 ms (5000 iter unless noted) | `test_g11_performance.py` | CONFIRMED |
| Live provider | **LIVE_PROVIDER_UNVERIFIED** — canary not executed (`IMP_IBKR_LIVE` off / no gateway) | env inspection | CONFIRMED |
| Starting FAST | **21 / 0 / 0 / 0** | `tools/imp.py validate fast` | CONFIRMED |
| Starting FULL (pre-fix) | **4326 / 48 / 2 / 0** (ibkr safety: `query_provider.py` foundation import) | `tools/imp.py validate full` | CONFIRMED |
| Focused G11 | **46 / 0 / 0 / 0** | nine `test_g11_*.py` modules | CONFIRMED |
| ibkr suite | **72 / 0 / 0 / 0** | validation worker | CONFIRMED |
| providers suite | **322 / 0 / 0 / 0** | unittest discover | CONFIRMED |
| market_data suite | **127 / 0 / 0 / 0** | unittest discover | CONFIRMED |
| trading_correctness | **122 / 0 / 0 / 0** | unittest discover | CONFIRMED |
| G5 order_book regression | **82** green | `tests/order_flow/test_order_book_*.py` | CONFIRMED |
| G6/G8/G9/G10 regressions | green | explicit regression pass | CONFIRMED |
| FAST (final) | **21 / 0 / 0 / 0** | `tools/imp.py validate fast` | CONFIRMED |
| CHANGED (final) | **3791 / 48 / 0 / 0** in 490.876s | `tools/imp.py validate changed` | CONFIRMED |
| FULL (final) | **4326 / 48 / 0 / 0** in 576.589s | `tools/imp.py validate full` | CONFIRMED |
| Test-count reconciliation | G10 FULL **4280** (reported) → G11 FULL **4326** (+46 G11 tests); no removals/weakening | diff | CONFIRMED |
| BL-0301 | **IMPLEMENTATION_COMPLETE / LIVE_VERIFICATION_PENDING** | per-capability matrix in 14h | CONFIRMED |
| BL-0303 | **IMPLEMENTATION_COMPLETE** | G10 depth TTL preserved | CONFIRMED |
| BL-0304 | **COMPLETE (offline/replay)** | G9 path preserved | CONFIRMED |
| BL-0305 | **IMPLEMENTATION_COMPLETE / BLOCKED_BY_LIVE_EVIDENCE** | canary harness present; not executed | CONFIRMED |

## G11.1 evidence (2026-09-09; bounded live canary)

| Item | Result | Method | Confidence |
|---|---|---|---|
| Gateway | 127.0.0.1:4001 LIVE_CONNECTED readonly=true | bounded canary | CONFIRMED |
| L1 | LIVE_PROVIDER_VERIFIED; **DELAYED** data (not realtime entitled) | canary + evidence JSON | CONFIRMED |
| L2 | LIVE_CONNECTED_NOT_ENTITLED (10092) | canary | CONFIRMED |
| TRADES | LIVE_CONNECTED_NOT_ENTITLED (10189) | canary | CONFIRMED |
| False blocker corrected | `IMP_IBKR_LIVE` gate ≠ environment unavailable | 14i matrix | CONFIRMED |
| FULL (G11.1) | **4330 / 48 / 0 / 0** (+4 tests) | validate full | CONFIRMED |

## G12 evidence (2026-09-09; post-IBKR multi-asset runtime completion)

| Item | Result | Method | Confidence |
|---|---|---|---|
| L1 wording | freshness DELAYED; entitlement ENTITLED_DELAYED; live path verified separate from realtime entitlement | evidence JSON + canary fix | CONFIRMED |
| External isolation | L2/TRADES NOT_ENTITLED — not on software critical path | 14j matrix | CONFIRMED |
| Runtime projection | `cross_lane/multi_asset_runtime.py` + `runtime_status.py` | code + tests | CONFIRMED |
| Focused G12 | **25 / 0 / 0 / 0** | `test_g12_multi_asset_runtime.py` | CONFIRMED |
| Starting FAST | **21 / 0 / 0 / 0** | validate fast | CONFIRMED |
| Starting FULL | **4330 / 48 / 0 / 0** | validate full | CONFIRMED |
| CHANGED (final) | **3820 / 48 / 0 / 0** | validate changed | CONFIRMED |
| FULL (final) | **4355 / 48 / 0 / 0** (+25) | validate full | CONFIRMED |
| Performance | G12 runtime projection <5s / 5000 iter (dev machine) | test_g12_runtime_performance_measured | CONFIRMED |
| BL-0301 | **IMPLEMENTATION_COMPLETE**; live verified for entitled capabilities | 14j | CONFIRMED |
| BL-0305 | **IMPLEMENTATION_COMPLETE**; L2/TRADES external entitlement only | 14j | CONFIRMED |

## G13 evidence (2026-09-09; canonical multi-asset Paper execution)

| Item | Result | Method | Confidence |
|---|---|---|---|
| Margin facts contract | `risk/margin_facts.py` — admission, no invented formulas | code + tests | CONFIRMED |
| Canonical fill path | `portfolio/paper_fill.py` → `CanonicalPortfolio` for options/futures | `test_g13_paper_derivatives.py` | CONFIRMED |
| Futures lifecycle | partial / replace / cancel through Paper submit path | G13 lifecycle tests | CONFIRMED |
| Margin preview binding | `margin_facts_revision` + `PREVIEW_MARGIN_STALE` | preview binding tests | CONFIRMED |
| UI margin resolution | `paper/margin_resolution.py` + `paper_projections.py` | code inspection | CONFIRMED |
| Settlement currency | EUR bucket missing → `INSUFFICIENT_SETTLEMENT_CURRENCY` | G13 settlement tests | CONFIRMED |
| Paper adapter | derivative positions carry `OPTION_CONTRACT` / `CONTRACTS` metadata | G13 adapter test | CONFIRMED |
| Focused G13 | **25 / 0 / 0 / 0** | `test_g13_paper_derivatives.py` | CONFIRMED |
| Equity parity | **7 / 0 / 0 / 0** | `tests/portfolio/test_paper_parity.py` | CONFIRMED |
| Preview binding | **10 / 0 / 0 / 0** | `tests/trading_correctness/test_preview_binding.py` | CONFIRMED |
| Affected suites (closure) | portfolio **136**; trading_correctness **147**; futures **65**; xa01 **72**; platform **474/2**; options domain **783/11** | validation_worker / domain | CONFIRMED |
| FAST (closure) | **21 / 0 / 0 / 0** | validate fast | CONFIRMED |
| CHANGED (closure) | **3845 / 48 / 0 / 0** | validate changed | CONFIRMED |
| FULL (closure) | **4380 / 48 / 0 / 0** (+25 from G12 baseline 4355) | validate full | CONFIRMED |
| Performance | option_pretrade **1.23ms**/200-iter; future_pretrade **1.57ms**/200-iter; fill→portfolio **1.89ms**/50-iter (dev machine) | `g13-runtime-performance.json` | CONFIRMED |
| Wave 7 readiness | **READY** — Paper derivative E2E canonical; margin fail-closed; portfolio authority unified; FULL green | 14k matrix + closure criteria §14 | CONFIRMED |
| Live broker execution | **NOT_ENABLED** — boundary unchanged | G11/G12 evidence | CONFIRMED |

## G14 evidence (2026-09-09; unified selector + query keys + Options/Futures product surfaces)

| Item | Result | Method | Confidence |
|---|---|---|---|
| Instrument selector API | `/instruments/search` returns canonical DTOs with actionability | `test_g14_product_convergence.py` selector tests | CONFIRMED |
| Route codec | encode/decode round-trip for canonical ids | `G14InstrumentRouteCodecTests` | CONFIRMED |
| Options product projection | G12 runtime + G13 portfolio in G14 envelope | `test_options_payload_carries_canonical_identity` | CONFIRMED |
| Futures product projection | family non-actionable; contract margin explicit | futures projection tests | CONFIRMED |
| Query-key isolation | mode/account/instrument/provider isolation for product keys | `queryKeyFactory.test.ts`, `queryKeys.test.ts` | CONFIRMED |
| Derivative Paper preview UI | inline preview panel on product surfaces (submit on order ticket) | component tests + build | CONFIRMED |
| Focused G14 backend | **11 / 0 / 0 / 0** | `imp.py test focused` (11 selectors) | CONFIRMED |
| CHANGED (closure pass) | **3856 / 48 / 0 / 0** | validate changed | CONFIRMED |
| UI typecheck | pass | `npm run typecheck` | CONFIRMED |
| UI build budget | **202.92 KiB gzip** (≤ 203.00) | `npm run build` | CONFIRMED |
| FULL (closure) | **4391 / 48 / 0 / 0** | validate full | CONFIRMED |
| Live broker execution | **NOT_ENABLED** | G11/G12/G13 boundary | CONFIRMED |

## G15 evidence (2026-09-09; product acceptance E2E + validation performance + archive-first deprecation)

| Item | Result | Method | Confidence |
|---|---|---|---|
| Playwright E2E | **10 / 10** browser scenarios | `tests/product_acceptance/test_browser_acceptance.py` | CONFIRMED |
| E2E validation gate | **6 / 0 / 0 / 0** in 68.8s | `imp.py validate e2e` | CONFIRMED |
| FAST | **21 / 0 / 0 / 0** in 4.1s (E2E excluded) | `imp.py validate fast` | CONFIRMED |
| CHANGED | **3857 / 48 / 0 / 0** in 453.6s | `imp.py validate changed` | CONFIRMED |
| FULL (closure) | **4392 / 48 / 0 / 0** in 539.0s | `imp.py validate full` | CONFIRMED |
| UI Vitest | **454** passed | `npm test -- --run` | CONFIRMED |
| UI build budget | **202.94 KiB gzip** (≤ 203.00) | `npm run build` | CONFIRMED |
| Validation performance | `G15_VALIDATION_PERFORMANCE_MEASURED` | `artifacts/g15-validation-performance.json` | CONFIRMED |
| Dead-route census | BL-0803 artifact + deprecation headers | `artifacts/g15-dead-route-census.json` | CONFIRMED |
| BL-0701 | **OPEN** (deferred) | `artifacts/g15-query-key-debt.json` | CONFIRMED |
| Live broker execution | **NOT_ENABLED** | live-safety E2E | CONFIRMED |

## Workstream evidence log (append-only)

| Date | Workstream | Claim | Evidence | Confidence |