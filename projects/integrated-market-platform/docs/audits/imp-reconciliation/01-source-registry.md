# 01 — Source and Donor Provenance Registry

Status: **COMPLETE for WS01** (materially complete; consumed by WS03 for
donor-to-IMP tracing). Audit-only — no dispositions executed.

## WS01 headline findings

1. **Four of five external donor trees are INCOMPLETE LOCAL REMNANTS** — the
   source code is absent; only databases, state files, compiled `__pycache__`,
   venvs, data files, and build artifacts remain. Only `Claude Code News/`
   arrived with full source. Evidence: source-file census 2026-09-06
   (`find` counts, excluding venv/node_modules/caches):
   - `DS-440-CAPSTONE-GridIQ-main/` → 0 source files (5 files total)
   - `tradingCVDBubble-main (1)/` → 1 source file (`finviz/api_keys.py`) + 28.3k cache/venv files
   - `internship-project-main/` → 0 source files (48.3k cache/venv/state files)
   - `Eric_futuresX-main/` → 0 source files (9.9k data/cache files)
   - `Claude Code News/` → 49 JS/TS/MJS source files (complete)
   Consequences: local commit provenance is impossible; the existing donor
   notes/reuse matrix were authored when fuller trees existed; the external
   GitHub repos are now the only source-of-truth for code.
2. **External verification succeeded for all four known donor repos**
   (read_url, 2026-09-06, HTTP 200) — see External verification log.
3. **Git history contains donor-integration commits** (incl. a GridIQ port
   `6adeeec`) — trace anchors for WS03; the GridIQ port predates the professor's
   mistaken-donor correction and must be traced, not presumed valid.
4. **Existing governance records are partly stale** after the Heller
   correction: the donor-code-permissions record cites "Lucas email permission"
   (the wrong Lucas) and the reuse matrix cites donor source files that no
   longer exist locally. Both are preserved as history and flagged superseded.

## Master registry (WS01 schema)

| Source ID | Project | Supplier | Author | Repo owner | Local path | External source | Local git history? | Intended capability | Authorization status | Languages/frameworks | Data providers | Broker/execution | Asset class | Distinctive identifiers | Relationship to IMP | Confidence | Open questions |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SRC-001 | DS-340W Fantasy Football Prediction | Lucas Heller (mistaken transfer) | Lucas Heller (external repo verified) | lucasheller22 | ABSENT locally (gitignored ref only) | https://github.com/lucasheller22/DS-340W-Fantasy-Football-Prediction (VERIFIED public) | n/a (absent) | Time-series (ARIMA/ARIMAX/NN) forecasting research patterns | KNOWN_MISTAKEN_DONOR | R | Fantasy football player-week data (xlsx) | none | Fantasy football (not market) | `DS340_Parent_Code.R`, `ARIMAX_DS340W_Code.R`, `NN_340w_Code.R`, `ARIMA_ARIMAX_NN_340W_Comparison.R`, `forecast_offense_*.csv` | None incorporated (absent); matrix rows all PORT_ADAPT/CONCEPT_ONLY/DO_NOT_USE | CONFIRMED (repo verified; classification confirmed) | Whether any R code was ever locally present (evidence: none found in tree or git history) |
| SRC-002 | DS-440 CAPSTONE GridIQ | Lucas Heller (mistaken transfer) | Lucas Heller (external repo verified) | lucasheller22 | `DS-440-CAPSTONE-GridIQ-main/DS-440-CAPSTONE-GridIQ-main/` — REMNANT (only `gridiq-backend/gridiq.db` + frontend tsbuildinfo + `.vite`) | https://github.com/lucasheller22/DS-440-CAPSTONE-GridIQ (VERIFIED public) | LOCAL_GIT_HISTORY_UNAVAILABLE | AI football coach: chat + NFL dashboards + Playbook (routes/coverages/LOS) | KNOWN_MISTAKEN_DONOR | FastAPI + SQLAlchemy/Alembic + SQLite; React (Vite) frontend; Gemini chat | nflverse (NFL play-by-play/parquet) | none | Football (not market) | Tables `users/games/plays/cache/conversations/messages/alembic_version`; `gridiq.db`; Render deploy `ds-440-capstone-gridiq-1.onrender.com` | **Port commit exists in IMP history: `6adeeec` "port GridIQ dataset projection and cache patterns"** (pre-correction) — WS03 trace anchor | CONFIRMED (repo verified; db schema inspected) | What exactly `6adeeec` ported and whether it remains; whether any other GridIQ-derived code persists |
| SRC-003 | tradingCVDBubble (CVD Bubble) | Prof.-directed supply (Hyuntae Jeong's project) | Hyuntae Jeong (external repo verified) | RumiaKitinari | `tradingCVDBubble-main (1)/tradingCVDBubble-main/` — REMNANT (only `finviz/api_keys.py`, 2 CVD report .md, `logs_app.log`, __pycache__ pyc, venvs) | https://github.com/RumiaKitinari/tradingCVDBubble (VERIFIED public) | LOCAL_GIT_HISTORY_UNAVAILABLE | CVD measurement dashboard: trade classification, CVD curve, L2 depth heatmap | AUTHORIZED_CVD_LEVEL2_DONOR | Python 3.11+; Flask/Dash webapp; MongoDB; IB API | IBKR L1 (tick/quotes) + L2 (depth), Nasdaq TotalView-class subscription, FinViz Elite (consolidated bars) | IBKR (Gateway/TWS; ports 7497/7496/4002/4001 auto-probed; `ibkr.dynamic_collector`) | Equities (9-ticker sessions) | Modules: `tick_collector`, `aggressor`, `calculator`, `session_grid`, `validate_moc`, `bvc`, `rollup`, `store`, `schema`, `serve`, `visualizer`, `data_provider`, `demo_dataset`, `new_finviz`; Mongo `finviz_db.candles`, `trading_cvd.level2_snapshots`; CVD_135 reports | IMP admitted fixture: `ADMITTED-CVD-NVDA-ORDERFLOW-001` (Phase 10 PORT_ADAPT slice) per DONOR_FIXTURE_MAP | CONFIRMED (repo verified; pyc module census; fixture map) | Where the local source went; whether IMP's order-flow lane reimplemented from requirement or adapted donor math |
| SRC-004 | internship-project | Prof.-directed supply (Eric Strzalkowski's project) | Eric Strzalkowski (external repo verified) | Strzalaa | `internship-project-main/internship-project-main/` — REMNANT (state/*.json only; agent/screener/options source absent; venvs + pyc remain) | https://github.com/Strzalaa/internship-project (VERIFIED public) | LOCAL_GIT_HISTORY_UNAVAILABLE | Paper news-momentum agent + options confirmation engine (internship research) | AUTHORIZED_OPTIONS_DONOR | Python; Streamlit dashboard; JSON state; pytest | News RSS, web scraping, FinViz screener, Telegram notifier | Paper trading only (`paper_trader`); `demo.lock` blocks live scheduler | Equities + options (0DTE) | Modules: `odte_screener`, `odte_decision`, `herd_scorer`, `news_decay`, `quadrant`, `risk_manager`, `option_contracts`, `expiry_screener`, `decision_engine`, `paper_trader`, `telegram_notifier`; state files `watchlist/portfolio/trade_log/executions/expiry_watchlist/quadrant_candidates/high_alert/pending_reviews/health`; OCE signals fields `options_score`, `put_call_volume_ratio`, `call_volume_share`, `put_call_oi_ratio`, `net_delta_oi`; README docs incl. `HANDOFF.md`, `MODULE_CATALOG.md` | IMP admitted fixture: `ADMITTED-OPTIONS-BIYA-001` (Phase 11 PORT_ADAPT slice); catalyst bridge `:8766/explore/catalyst` reads `state/trade_log.json`+`watchlist.json` | CONFIRMED (repo verified; state/pyc census; fixture map) | Whether OCE scoring logic was ported into IMP options lane or reimplemented; Unusual Whales / iVolatility usage extent (not visible in remnant) |
| SRC-005 | Eric_futuresX (futuresX) | Prof.-related earlier Future supply (Eric) | Eric (author name not independently verified) | UNKNOWN (no remote found) | `Eric_futuresX-main/futuresX-main/` — REMNANT (data CSVs, `market_depth_rth_before_june9.db`, `ticker_data/`, `src_client/workspace` dirs with pyc only) | UNKNOWN — no URL in tree; do NOT search random repos | LOCAL_GIT_HISTORY_UNAVAILABLE | Futures Level-2 capture + UI + backtests + paper experiments | AUTHORIZED_OR_PREVIOUSLY_AUTHORIZED_FUTURE_CANDIDATE | Python 3.10–3.13; Streamlit (`streamlitapp`); IB API; GUI (tkinter?) | IBKR L2 (reqMktDepth confirmed in bytecode), Topstep, historical ES/SPY/SPXL CSVs, Databento SPY 1m, CME MDP3 `glbx-mdp3-*.csv` | IBKR (reqMktDepth, placeOrder, 127.0.0.1 — bytecode-confirmed); Topstep | Futures (ES; MES implied) + SPY/SPXL | Modules: `ibkr_manager`, `ibkrfeed`, `ibkrdata`, `level2IBKR`, `level2visualize`, `data_collecter`, `live_rr`, `utils`, `gui`; test `test_bracket_orders`; `backtest_trades_*.csv`, `timestamp_mid_prices_*.csv` | Not admitted; smoke ES L2 CSV used for offline smoke; production data BLOCKED (`DF-001/DF-002`, LFS pointers) | CONFIRMED (bytecode census + data files); authorization HIGH_CONFIDENCE | External repo identity; authorship; relationship to SRC-006 (see Future comparison) |
| SRC-006 | Claude Code News ("Morning Brief") | Lucas Bichara (professor-shared: "This is Future Project") | NOT PROVEN — supplier ≠ author; package has no author field; no .git | UNKNOWN | `Claude Code News/` — **FULL SOURCE PRESENT** (49 JS/TS/MJS) | UNKNOWN (no remote) | LOCAL_GIT_HISTORY_UNAVAILABLE | Standalone MES futures trader: 8h news buffer → Claude direction → 1 bracketed MES trade/day with trailing ladder | AUTHORIZED_FUTURE_DONOR | Node 18+ (ESM), `chrome-remote-interface`, `@modelcontextprotocol/sdk`; macOS launchd; iMessage Shortcut (`TradeTexts`) | RSS/Telegram/Reddit/Twitter feeds; TradingView news panel (Reuters/DJ/dpa-AFX) via CDP; Anthropic Claude (sonnet-4-6 brief, haiku-4-5 preflight) | **Tradovate** (order ticket driven through TradingView Desktop UI via CDP `src/live/broker_ui.js`) — NOT IB | Futures (MES, 10 contracts) | `NEWS_QTY`, `NEWS_SL_FIXED_USD`, `NEWS_TP_CAP_USD`, `BRIEF_TP_MULT`, `BRIEF_FOCUSED`, `BRIEF_MIN_CONF`, `BRIEF_HOLD_MIN`, `BRIEF_MAX_TOKENS`; `verify_config.mjs`; ladder rungs (0.5R→BE, 0.75R→+0.5R, 1.5R→+1.0R, 2.0R→trail); `TP CAPPED`; SIGUSR1/SIGUSR2; `shadow_log/shadow_report`; `reconstruct.mjs` | PRIMARY authorized Future reference; NOT incorporated in IMP; must never be (P2-4 donor isolation) | CONFIRMED (full source inspected) | True authorship/origin; whether Tradovate+CDP is intended as the canonical Future execution model or reference-only |
| SRC-007 | L1VolumeBubble | UNKNOWN | UNKNOWN | UNKNOWN | ABSENT locally | Unknown (TradingView Pine community) | n/a (absent) | Volume-bubble / absorption visualization (Pine indicator) | UNVERIFIED_SOURCE | Pine Script | TradingView | none | — | File ref: `L1VolumeBubble-main (1)/L1VolumeBubble-main/Custom volume bubble 1m1s l1.pine` (DONOR_FIXTURE_MAP) | Not admitted; visual reference only | MODERATE (referenced in 2 governance docs; tree absent) | Provenance; professor authorization (none found); whether still relevant |
| SRC-008 | short-squeeze-project | Adam | Adam | AdamEddahmouni | `short-squeeze-project/` (child repo, own `.git`, branch `fix/frozen-followups` @ `9de7b2f`, clean) + snapshot `projects/short-squeeze-project/` (manifest: `main` @ `78b7467`) | https://github.com/AdamEddahmouni/short-squeeze-screener-internship.git | YES (child repo history; LOCAL commit history available) | Evidence/provenance-driven short-squeeze research screener (read-only) | ORIGINAL_PROJECT_SOURCE | Python; `squeeze_core` package; FastAPI/HTTP API `:8787`; pytest | Provider evidence fixtures; IBKR HALTS capability; public sources | none (read-only research) | Equities | `ADAM` pins, `squeeze_core`, FROZEN_DEMO mode, `phase/3e-historical-acquisition` lineage, `Phase 4 NOT_CALIBRATED` fit-report skeleton | Canonical governed child; snapshot tracked; short-squeeze lane in IMP | CONFIRMED | Snapshot lag: manifest `78b7467` vs child `9de7b2f` (316-file diff); hardening plan references re-sync to `41f52bb` — manifest not updated; WS03 reconcile |
| SRC-009 | governed-ticker-metadata-enrichment | Adam | Adam | AdamEddahmouni (IMP lineage) | `governed-ticker-metadata-enrichment/` (own `.git`, branch `feat/governed-ticker-metadata-enrichment` @ `1398da3`) + snapshot | IMP child branch (workspace-manifest.json) | YES | Governed ticker metadata enrichment | ORIGINAL_PROJECT_SOURCE (internal IMP lineage) | Python | SEC/metadata sources | none | Equities | matches manifest `1398da3b…` exactly | Internal lineage; snapshot in sync | CONFIRMED | — |
| SRC-010 | equity-data-v1 | Adam | Adam | AdamEddahmouni (IMP lineage) | `equity-data-v1-worktree/` (own `.git`, branch `feat/equity-data-v1` @ `ad54fb8`) + snapshot | IMP child branch | YES | Equity data V1 | ORIGINAL_PROJECT_SOURCE (internal IMP lineage) | Python | equity data sources | none | Equities | matches manifest `ad54fb8d…` exactly | Internal lineage; snapshot in sync | CONFIRMED | — |
| SRC-011 | integrated-market-platform | Adam | Adam + contributors | AdamEddahmouni | `integrated-market-platform/` (child repo, branch `main` @ `072e62e`, remote → archived `integrated-market-intelligence-platform.git`) + tracked snapshot `projects/integrated-market-platform/` (canonical) | https://github.com/AdamEddahmouni/integrated-market-intelligence-platform.git (archived) | YES (full child history; snapshot history squashed into parent) | Governed market workstation: Demo replay / Paper internal sim / Live observational | ORIGINAL_PROJECT_SOURCE (CANONICAL PRODUCT) | Python 3.11 stdlib-only foundation + research layers; React/TS UI; FastAPI/API `:8766` | Moomoo OpenD (observational), Tradier sandbox (broker-paper), SEC/FRED/COT/EIA/NOAA/CBOE/Finviz Elite; Anthropic (MRA) | None live; Tradier sandbox broker-paper (P4-4A/4B); LIVE-001 blocked | Multi-asset (equities/futures/options research) | MODE_AUTHORITY, `tools/imp.py`, `tools/validation_manifest.json`, lane registry, G1–G6 gates, EVIDENCE-01x | THE integration target | CONFIRMED | — |

## External verification log (2026-09-06, read_url)

| URL | Status | Verified facts |
|---|---|---|
| https://github.com/lucasheller22/DS-440-CAPSTONE-GridIQ | 200 | Public. "AI football coach: chat, NFL dashboards, Playbook. React (Vite) + FastAPI, SQLite, Gemini." Render deploy; LICENSE present; matches local remnant (db, alembic, backend/frontend) |
| https://github.com/lucasheller22/DS-340W-Fantasy-Football-Prediction | 200 | Public. R scripts exactly matching DONOR_REUSE_MATRIX component list; workbook + forecast/backtest CSVs |
| https://github.com/RumiaKitinari/tradingCVDBubble | 200 | Public. CVD dashboard; trade classification from live bid/ask; L2 depth heatmap; MongoDB; IBKR Gateway/TWS port auto-probe; Nasdaq TotalView-class subscription; FinViz Elite token in `finviz/api_keys.py` (matches remnant) |
| https://github.com/Strzalaa/internship-project | 200 | Public. "Paper-trading news momentum agent + options confirmation engine"; README docs incl. `HANDOFF.md` (merge into stocks/futures/multi-asset project), `MODULE_CATALOG.md`; no broker in OCE |
| https://github.com/lucasheller22 (owner) | implied | Two Heller repos verified under one owner; supports "different Lucas" narrative |

Not verified: SRC-005 (no URL), SRC-006 (no URL), SRC-007 (no URL).

## Future source comparison (SRC-005 vs SRC-006) — source level only

| Area | Claude Code News (SRC-006) | Eric futuresX (SRC-005) |
|---|---|---|
| Futures products | MES (10 contracts) | ES (MES implied), SPY/SPXL data |
| Market-data source | TradingView (news panel, chart, 1s MES tape via CDP) | IBKR L2 (reqMktDepth), historical CSVs, Databento, CME MDP3 |
| Broker/execution | Tradovate via TradingView DOM (CDP-driven) | IBKR (placeOrder), Topstep |
| Strategy type | News-driven daily direction call + bracket + trailing ladder | Level-2 capture/visualization + backtests + paper experiments |
| Level 1 | Yes (chart/tape) | Yes (implied) |
| Level 2 | No (no depth use) | Yes — core (level2IBKR, level2visualize) |
| News dependence | Core (8h headline buffer) | None evident |
| UI | None (daemon + iMessage texts) | Streamlit + GUI |
| Backtesting | `reconstruct.mjs` replay + shadow logs | backtest_trades_*.csv artifacts |
| Paper/live | Dry-run default; `BROKER_LIVE=1` for real orders | Paper experiments; IBKR/Topstep |
| Risk controls | Fixed stop/target, ladder, 120min hold, 1 trade/day, honest-limits docs | bracket-order tests (`test_bracket_orders`) |
| Operational env | macOS launchd, Node 18+ | Windows/Python |
| Stated role | "Standalone futures trader" (forward-test, no proven edge) | Level-2 research/experimentation |
| **Relationship verdict** | **SEPARATE_FUTURE_STRATEGIES with complementary roles (execution+strategy vs data+capture); SHARED_LINEAGE NOT EVIDENCED; UNKNOWN external origins for both** — no code overlap observed | same |

Evidence: full source read (SRC-006); bytecode + data census (SRC-005). No
file, module, or identifier overlap observed. Target Future architecture is a
WS05/WS07 decision, NOT decided here.

## Interactive Brokers dependency map (source level)

| Source | ACCOUNT | EXECUTION | PORTFOLIO | LEVEL_1 | LEVEL_2 | FUTURES_DATA | OPTIONS_DATA | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| SRC-003 CVD Bubble | — | — | — | YES (trades+quotes) | YES (depth) | — | — | REQUIRED_BY_DONOR + REQUIRED_BY_SCOPE (professor: "CVD/Level2 requires IB L1 and L2 data") | README (external), pyc census, api_keys remnant |
| SRC-005 futuresX | — | YES (placeOrder) | — | — | YES (reqMktDepth) | YES | — | USED_BY_DONOR (professor-guided for Future) | bytecode grep |
| SRC-004 internship | — | — | — | — | — | — | — | NONE (paper-only; Unusual Whales/iVolatility per author) | external README |
| SRC-006 Claude Code News | — | — | — | — | — | — | — | NONE — Tradovate execution | source inspection |
| SRC-011 IMP | — | — | — | — | — | — | — | PLANNED/BLOCKED (IBKR adapters need ADR authorization per README) | IMP README |

Note: IBKR used by donor ≠ IB mandatory for the capability (except CVD L1/L2,
where professor guidance independently establishes it).

## Other external providers (source level)

| Service | Used by | Classification |
|---|---|---|
| Interactive Brokers | SRC-003 (L1/L2), SRC-005 (L2/execution) | REQUIRED_BY_SCOPE for CVD; DONOR-SPECIFIC for futuresX; PLANNED for IMP |
| Tradovate | SRC-006 | REQUIRED_BY_DONOR (execution); future scope status OPEN |
| TradingView (Desktop CDP + news) | SRC-006 | REQUIRED_BY_DONOR |
| Anthropic (Claude) | SRC-006 (brief), SRC-011 (MRA-002) | REQUIRED_BY_DONOR (SRC-006); OPTIONAL_PROVIDER (IMP MRA) |
| Unusual Whales | SRC-004 (per author) | DONOR_SPECIFIC — not in local remnant; not IMP-required |
| iVolatility | SRC-004 (per author) | DONOR_SPECIFIC — same |
| Topstep | SRC-005 | DONOR_SPECIFIC |
| FinViz / FinViz Elite | SRC-003 (token in remnant), SRC-004 (screener), SRC-011 (Finviz Elite discovery, P3.3) | REQUIRED_BY_DONOR (SRC-003 volume scaling); IMP has own Finviz lane |
| MongoDB | SRC-003 | REQUIRED_BY_DONOR (localhost:27017) |
| Google Gemini | SRC-002 (GridIQ chat) | MISTAKEN-DONOR-SPECIFIC (irrelevant to IMP) |
| nflverse | SRC-002 | MISTAKEN-DONOR-SPECIFIC |
| Databento / CME MDP3 | SRC-005 (historical data) | DONOR_SPECIFIC |

Credentials: none altered, none read beyond public/gitignored token placeholders
(`finviz/api_keys.py` empty token). Tests/mocks: IMP has fixture/mock paths for
its providers; donors have limited tests (internship `test_odte_decision`,
futuresX `test_bracket_orders` pyc evidence only).

## Mistaken donor handling (SRC-001/002 — registry work only)

- Classification CONFIRMED via professor correction (recorded in 00/02).
- No final disposition assigned (WS03/WS07 decide: REMOVE / REPLACE_NATIVE /
  REIMPLEMENT_FROM_SPEC / ISOLATE_PENDING_DECISION / KEEP_INDEPENDENT).
- Trace anchors for WS03: git history commits `6adeeec` (GridIQ port),
  `d169cb8` (donor integration lanes), `3fe0b96` (donor bridge lanes),
  `68d0069`/`64cb64e`/`db3a7fb` (revision-3 donor governance); donor notes
  `GRID_IQ_NOTES.md`, `DS340W_NOTES.md`; reuse-matrix rows.
- GridIQ port `6adeeec` predates the correction → must be traced and classified
  (the port itself is evidence of accidental incorporation, not authorization).

## Provenance conflicts (actual contradictions)

1. **Permissions record vs professor correction** — `2026-08-14-donor-code-permissions.json`
   lists PROTO-DS340W-001 / PROTO-GRIDIQ-001 with `USER_REPORTED_LUCAS_EMAIL_PERMISSION`
   as evidence source. The professor later corrected that the Lucas who
   supplied permission was the WRONG Lucas. The record is preserved as history
   but its permission evidence is superseded for reuse purposes. Confidence:
   CONFIRMED (both statements documented).
2. **Reuse matrix cites files absent locally** — DONOR_REUSE_MATRIX rows cite
   e.g. `gridiq-backend/app/nflverse_parquet.py`, `gridiq-frontend/src/pages/Chat.tsx`,
   `ARIMA_ARIMAX_NN_340W_Comparison.R` — none exist in the local trees today.
   The matrix reflects an earlier, fuller snapshot; its "code scope unverified"
   caveats now apply globally. Confidence: CONFIRMED (file census).
3. **Short-squeeze snapshot lag** — workspace-manifest records `78b7467`
   (`main`); child repo is on `fix/frozen-followups` @ `9de7b2f` (clean, 316
   files newer than snapshot); hardening plan references re-sync `41f52bb`.
   The manifest does not match either current child HEAD or the plan's claimed
   re-sync. Confidence: CONFIRMED (diff + manifest + plan).

## Non-source workspace entries (excluded from registry)

- `pytest-equity-premerge-20260824/`, `pytest-equity-postmerge-20260824c/` —
  empty pytest artifact dirs, not projects.
- `.worktrees/` — imp-forensic-reconciliation (codex/imp-forensic-reconciliation),
  postroot-acceptance-suite (branch @ 2691464, IMP postroot contracts), rt01-paper-tracing-parent — all internal lineage worktrees.
- `docs/`, `tests/`, `tools/` (parent), `.github/` — monorepo governance/tooling.
- `integrated-market-platform/.planning/…` — planning scratch (forensic worktree only).