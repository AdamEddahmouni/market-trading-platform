# Post-close merge-train queue — 2026-09-15

**Classification:** `ISOLATED_COORDINATOR_QUEUE` (not program-status truth)  
**Branch / worktree:** `diagnosis/merge-train-20260915` at  
`C:/Users/adame/Desktop/market-trading-platform/.worktrees/diagnosis-merge-train-20260915`  
**Queue snapshot SHA:** `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` (`origin/main` at snapshot)  
**Frozen RTH runtime:** `.rth-operator-20260915` at the same SHA — **do not thaw, patch, or merge into it**  
**This document does not update** [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md)

Snapshot time: 2026-09-15 ~12:02 ET (mid-RTH refresh of `989ac2ef`). Parallel isolated lanes are still writing. Re-read worktree porcelain before any post-close merge. **Do not merge anything during the session.**

## Rebase-required flags (vs `origin/main` `7aade60b`)

| Slot | Tip | Merge-base | Must rebase before land |
|---|---|---|---|
| Q1 launcher | `9b0781c9` | `d588728d` | **YES — do not merge as-is** |
| Q2–Q4 live-OE / cockpit | `7aade60b` (no unique commits) | `7aade60b` | **YES if** `origin/main` moves; wait for P1+P4 + P12 live-OE gate |
| Q5 WATCH harness | `7aade60b` (no unique commits) | `7aade60b` | **YES if** `origin/main` moves |
| Q6 Item 9 | `77d448c3` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves |
| Q6 P12 review | `49ae216e` | (review branch) | Gate only — **not merge cargo** |
| Q7 latency | `49529d64` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves |
| Q8 Item 7 notes | `d588728d` + untracked notes | `d588728d` | **YES** onto post-close `origin/main` before committing notes |
| Q9a test-gap | `145fee4f` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves |
| Q9b runbook | `134924c3` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves |
| This queue | `989ac2ef` + this refresh | `7aade60b` | Docs only; **YES if** `origin/main` moves |

## Operating holds

| Hold | Disposition |
|---|---|
| Merge into `main` / frozen RTH | **FORBIDDEN** until post-close reconciliation |
| Grok / enrichment-worker production | **DEFERRED** — worker stays OFF; not a queue member |
| PR [#196](https://github.com/AdamEddahmouni/market-trading-platform/pull/196) capture-context sidecar | **NOT TODAY** — `DIRTY` / `CONFLICTING` vs `main`; not on frozen runtime; rebase **after** session |
| Empirical gates (`FINVIZ_PROSPECTIVE_OBSERVATION_CAPTURED`, `ITEM9_PROSPECTIVE_BAR_RECEIPT_CAPTURED`, `ITEM7_GOVERNED_ROW_CAPTURED`, `PROSPECTIVE_HOT_PATH_LATENCY_CAPTURED`) | **Unearned** — no queue member may flip them |
| Live execution / Paper orders | **OFF** |

`PENDING_OWNER` means the named branch/worktree did not exist, or existed with no payload, at this snapshot. The coordinator should not rediscover the *slot*; it may still need to wait for the owning lane to land commits.

## Proposed order (subject to evidence)

Coordinator brief order:

```text
launcher
  → provider/EventV1 convergence
  → OE observational read
  → cockpit live-state
  → WATCH harness
  → Item 9
  → latency
  → Item 7
  → docs
```

**Evidence-adjusted safety override:** cockpit fixture quarantine (`as_of` / attention) **must** land before enabling observational ranked **reads**. Deleting or weakening `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` mutations **without** stopping July BIYA / MC9 / ES fixture admission would rank replay cards as live opportunities. Item 9 is **independent** of the live-path stack (no shared files with launcher/OE). WATCH harness is fixture-only and may proceed in parallel if it stays in new test modules.

Recommended post-close landing sequence:

1. **Q1 launcher / Vite proxy** (operator can even *see* JSON)  
2. **Q4 cockpit live-state honesty** (stop July-21 `as_of` and fixture attention as “now”)  
3. **Q2 provider → EventV1 admission**  
4. **Q3 OE observational read** (EMPTY live book with live provenance; mutations stay fail-closed)  
5. **Q5 WATCH/DISMISS harness** (fixtures; not empirical)  
6. **Q6 Item 9 session-day kline** (independent; not calibration)  
7. **Q7 latency notes/telemetry**  
8. **Q8 Item 7 upstream wiring** (priority 7; no corpus fabrication)  
9. **Q9 runbook / test-gap docs** (land with corresponding software)

Adversarial review `review/live-oe-diagnosis-20260915` (Lane P12 / `8048d5f7`) remains a **gate** on Q2–Q4, not a merge member. Branch exists at `7aade60b` with uncommitted `docs/engineering/reviews/P12_LIVE_OE_DIAGNOSIS_FALSIFICATION_20260915.md` — treat as **PENDING / IN_FLIGHT**. If that review **DISPROVES** the admission diagnosis, discard or rewrite Q2–Q4. Item 9 P12 (`review/item9-kline-diagnosis-20260915` `49ae216e`) is a separate gate on Q6 only.

---

## Q1 — Launcher / SPA routing

| Field | Value |
|---|---|
| **Status** | `COMMITTED_ISOLATED` — **DO NOT MERGE AS-IS** |
| **Branch / worktree** | `diagnosis/launcher-routing-20260915` at `.worktrees/diagnosis-launcher-routing-20260915` |
| **Source baseline SHA** | `d588728d60b139ae44b5a3667a8e120d1e21ee1c` (**not** frozen `7aade60b`) |
| **HEAD vs origin/main** | Unique commits `a2dd6ced` `fix(platform): select repo venv and open SPA root` then `9b0781c924ad23abc37eb9b51c3249e71d269e73` `chore(platform): record isolated launcher-routing candidate SHA`. Behind `origin/main` by `#195` `3daab7f2`, `#199` `64f1cb42`, `#202` `7aade60b` |
| **Purpose** | One-click IMP Python + SPA URL + Vite proxy so operator JSON is not swallowed by `index.html` |
| **Issue addressed** | Launcher auto-selected `moomoo-api-test` (no sklearn); `START_PLATFORM` opened proxied `/discover` (API 404); `/opportunities` unproxied (Zod parse of HTML); `/discover` HTML not bypassed |
| **Empirical evidence** | 2026-09-15 Lane E: `http://127.0.0.1:5173/` Paper loads; GET `/discover` 404; ranked fetch via UI origin failed; API `:8766` returned `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`. Proxy-only would still show an empty live book |
| **Affected files** | `a2dd6ced` (16 files, +357/−53): `tools/platform/local_launcher.py`, `tools/platform/control_service.py`, `START_PLATFORM.cmd`, `PLATFORM_CONTROL.cmd`, `ui/vite.config.ts`, `src/market_platform_foundation/ui_api/server.py`, `tests/platform/test_local_launcher.py`, `tests/platform/test_operator_control_service.py`, `tests/ui1/test_ui_api.py`, `tools/validation_manifest.json`, `README.md`, `ui/README.md`, `docs/engineering/LOCAL_DEVELOPMENT.md`, `docs/superpowers/specs/2026-08-24-local-platform-launcher-design.md`, `docs/engineering/WORK_LOG.md`, `BRANCH_NOTES.md`. Tip `9b0781c9` is notes-only |
| **Focused tests** | Isolated worktree reported **25 passed**: `tests.platform.test_local_launcher` (incl. `test_open_uses_spa_root_not_discover_proxy`, `test_vite_proxy_covers_operator_json_and_spa_html_bypass`, `test_missing_sklearn_blocks_start`); `tests.platform.test_operator_control_service` (incl. `test_control_status_does_not_http_self_probe`); `tests.ui1.test_ui_api.Ui1ApiTests.test_percent_encoded_explain_ref_round_trips` |
| **Broader validation** | After rebase: `python tools/imp.py test affected`; UI `npm run typecheck` / `npm test` if Vite remains in the diff; **not** FULL until stacked with Q2–Q4 |
| **Dependencies** | None for merge of proxy/Python. Does **not** populate the ranked book |
| **Must rebase** | **YES** onto post-close `origin/main`. **Do not merge `d588728d` as-is** |
| **Safely discarded if diagnosis changes** | **NO** for Vite `/opportunities` + `/discover` HTML bypass and sklearn interpreter — independently observed. Interpreter-precedence details may be rewritten |

---

## Q2 — Provider / EventV1 convergence (admission)

| Field | Value |
|---|---|
| **Status** | `IN_PROGRESS` on shared P1+P4 branch (no unique commits at snapshot) |
| **Branch / worktree** | `repair/live-oe-cockpit-state-20260915` at `.worktrees/repair-live-oe-cockpit-state-20260915` (**locked**; same file set as Q3+Q4) |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` (`origin/main`) |
| **HEAD vs origin/main** | Identical; porcelain empty at snapshot. Owning lane P1+P4 may still commit |
| **Purpose** | Admit live Finviz news (already fetched by FTEP CLI) as `EventV1` + PIT clocks into the **UI API process** via `build_production_observation_ingress_router` + `IntelligenceRepository` on `ReplayStore` |
| **Issue addressed** | First broken boundary is **admission**, not ranked UI. FTEP `--live-ingress` is `dry_run=True` `NewsArticleEvent` (no `put_event`). Cockpit screener is a different Finviz product. Production ingress exists but is **not** attached to `UiApiHandler`. Detectors: SEC/PTR only; `NEWS_EVENT` inactive |
| **Empirical evidence** | Lane A `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS` (~10:01 ET, ~100 ingested, 0 qualifying). Moomoo `CONNECTED_DEGRADED` 0/12 live quotes. Mixed discovery 0 candidates / `FINVIZ_SCREEN_UNAVAILABLE` (empty-vs-failed unlabeled). Diagnosis: [520aeed6](520aeed6-3d55-47a3-85ff-6b314fcdfd9a) |
| **Affected files (planned; P1 owns)** | `news` normalize / EventV1 mapper; `observation_ingress/production_wire.py` attach from `tools/ui1/run_ui_api.py`; `ReplayStore.strategy_repository`; **not** `vite.config.ts` / `local_launcher.py` (Q1); **not** Item 9 kline; **not** Item 7 corpus writers |
| **Focused tests (required by diagnosis)** | FTEP news → EventV1 → ingress (`put_event` once, PIT clocks, no fixture substitute on zero qualifying); detector consumes Finviz EventV1 without claiming `NEWS_EVENT` until canonical lane exists; screener 0-row success ≠ `FINVIZ_SCREEN_UNAVAILABLE` |
| **Broader validation** | `python tools/imp.py test affected` on intelligence/news/ui_api; do not enable Live or enrichment |
| **Dependencies** | Q4 fixture quarantine **before** any ranked read of the new store. Q1 so the UI origin can fetch `/opportunities` |
| **Must rebase** | **YES** if `origin/main` moves after close; currently already on frozen SHA |
| **Safely discarded if diagnosis changes** | **YES** if P12 **DISPROVES** “no EventV1 path ran in the cockpit process.” Keep FTEP dry-run honesty either way |

---

## Q3 — OE observational read

| Field | Value |
|---|---|
| **Status** | `IN_PROGRESS` — stacked on the same branch as Q2/Q4 |
| **Branch / worktree** | Same as Q2: `repair/live-oe-cockpit-state-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Purpose** | Allow `LIVE_OBSERVATIONAL` **reads** of a live (possibly EMPTY) ranked repository; keep WATCH/DISMISS/acks `PermissionError LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` |
| **Issue addressed** | `opportunity_projections.build_opportunities_summary_payload` fail-closes all live ranked reads (`feed_status=UNAVAILABLE`, `items=[]`). Tests lock this. UI never calls `OpportunityEngine.assess`. `oe_evidence_consumer` does not `put_opportunity` |
| **Empirical evidence** | Lane E `opportunities-summary-1050.json`: `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`, ranked items `[]`. `tests/ui1/test_opportunity_api.py::test_live_mode_returns_unavailable_empty_queue` encodes the gate. Paper UI with `IMP_LIVE_OBSERVATIONAL=1` is classified live for OE |
| **Affected files (planned)** | `ui_api/opportunity_projections.py` (split read vs mutation); ranked repository wiring; **do not** delete the mutation gate |
| **Focused tests** | Split the locked test: observational summary may be `EMPTY`/`READY` from repository; acks still fail-closed; zero-qualifying → `EMPTY` + live provenance, **not** fixture attention |
| **Broader validation** | ui1 opportunity API + opportunity ingest; Playwright only if UI ranking chrome changes |
| **Dependencies** | **Hard:** Q4 quarantine + Q2 EventV1/repo, else reads would rank July fixtures. Q1 for UI-origin JSON |
| **Must rebase** | Same as Q2 |
| **Safely discarded if diagnosis changes** | **NO** for keeping live **mutations** fail-closed. The *read* split is discardable if P12 shows ranked OE already had a live path |

---

## Q4 — Cockpit live-state honesty

| Field | Value |
|---|---|
| **Status** | `IN_PROGRESS` (P1+P4; worktree locked; no unique commits at snapshot) |
| **Branch / worktree** | Same as Q2: `repair/live-oe-cockpit-state-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Purpose** | Honest RTH clock and attention: `LIVE_OBSERVATIONAL` without live receive time → `as_of` UNAVAILABLE (never BIYA 2026-07-21 as “now”); quality summary must not claim admitted fixture; replay/MC9/ES cards quarantined or DEMO/REPLAY shelf |
| **Issue addressed** | `ReplayStore` always loads pinned BIYA JSONL; `as_of_time=2026-07-21T21:01:09Z`; live quote fallback skipped then still uses `store.as_of_time()`; attention concatenates `att-replay-context` + MC9 BOXL + ES fixture with no live filter |
| **Empirical evidence** | Lane E cockpit: 7 replay/fixture attention cards; ranked banner “Opportunity ranking unavailable.” WATCH/DISMISS not on those cards (ranked-OE only) |
| **Affected files (planned)** | `ui_api/projections.py` (`build_as_of_context`, `build_quality_summary`); attention admission; **not** Vite/launcher |
| **Focused tests** | Live as_of without quotes: no `2026-07-21`, no fixture quality copy; live attention admission: no `att-replay-context` / MC9 / ES as current RTH cards |
| **Broader validation** | ui1 projection tests; `validate-ui` if chrome copy changes |
| **Dependencies** | **Land before Q3.** Independent of Item 9 / Item 7 |
| **Must rebase** | Same as Q2 |
| **Safely discarded if diagnosis changes** | **NO** if July-21 `as_of` remains empirically observed — honesty is required even if OE stays empty |

---

## Q5 — WATCH / DISMISS acceptance harness

| Field | Value |
|---|---|
| **Status** | `BRANCH_EXISTS_NO_COMMITS` (Lane P5 in flight) |
| **Branch / worktree** | `repair/watch-dismiss-acceptance-20260915` at `.worktrees/repair-watch-dismiss-acceptance-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **HEAD vs origin/main** | Identical at snapshot; no unique commits |
| **Purpose** | Deterministic fixture harness: ranked opportunity → WATCH/DISMISS → operator ack → `ExecutionDecisionTrace` → `TradeReviewV1` → persist → restart → readback |
| **Issue addressed** | RTH could not exercise WATCH/DISMISS (no ranked OE cards). Downstream plumbing unproven |
| **Empirical evidence** | **None — harness, not empirical.** Do not describe as live evidence. Lane E: controls absent on fixture cards; live acks already `PermissionError` |
| **Affected files (planned)** | New tests e.g. `tests/opportunity/test_watch_dismiss_learning_loop_acceptance.py`; tiny production hooks **only** if not owned by P1. **Do not** edit `opportunity_projections` live-gate, `vite.config.ts`, `local_launcher.py`, Item 9 kline, Item 7 corpus |
| **Focused tests** | New acceptance module only; keep live mutations fail-closed |
| **Broader validation** | opportunity + paper_forward / trade-review affected suites |
| **Dependencies** | None to *land the harness*. Live ranking restoration (Q3) is required before the path is operator-visible |
| **Must rebase** | **YES** if `origin/main` moves; currently on frozen SHA |
| **Safely discarded if diagnosis changes** | **YES** if a better existing loop test already covers the chain — the gap is process proof, not a frozen-runtime defect |

---

## Q6 — Item 9 session-day 1m kline window

| Field | Value |
|---|---|
| **Status** | `COMMITTED_ISOLATED` + P12 `PARTIALLY_CONFIRMED` |
| **Branch / worktree** | `diagnosis/item9-prospective-bar-20260915` at `.worktrees/diagnosis-item9-prospective-bar-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Unique commits** | `e2d89348` `fix(item9): request session-day OpenD 1m kline window`; tip `77d448c3c062ba70fad1d14cd1b4d405b5066354` `fix(item9): log kline fetch diagnostics without loosening PIT` (past `e2d89348`) |
| **P12 review** | `review/item9-kline-diagnosis-20260915` `49ae216e682ea506dcb3c5ec6bc9fc0ee592ee0b` — overall **PARTIALLY_CONFIRMED**. `K_1M` oldest-first **NEEDS_MORE_EVIDENCE**. Unique-security `historyKLQuota` as hour-2 cause **DISPROVEN**. Do not land session-day with `max_count=120` |
| **Purpose** | Bind OpenD `request_history_kline` to the observation `America/New_York` session date (`max_count>=1000`); log `raw_row_count` / first-last `time_key` / vendor `retMsg`; prove `max_count=120` still misses RTH after 330 premarket minutes **if** paging is oldest-first |
| **Issue addressed** | Vendor `start=None,end=None` expands to `[today-365d, today]`. Poll #1 `PROSPECTIVE_NO_POST_SIGNAL_BAR` — timeout reason is **not** uniquely a post-signal PIT reject (collapsed codes). PIT (`available_time > signal_time`, incomplete-bar hide) **unchanged** |
| **Empirical evidence** | Poll #1 2026-09-15: `PROSPECTIVE_NO_POST_SIGNAL_BAR`, `receipt=null`. Capability-report `time_key` `2025-09-15` is mechanism inference, not a captured 1m page. **Not calibration. Independent of the live-OE stack** |
| **Affected files** | `e2d89348` + `77d448c3`: `tools/moomoo/opend_quote_transport.py`, `src/market_platform_foundation/paper/calibration/bar_ohlcv_sources.py`, `src/market_platform_foundation/paper/calibration/bar_ohlcv_prospective_proof.py`, `tests/providers/test_opend_history_kline_1m.py`, `docs/engineering/ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md`, `docs/engineering/WORK_LOG.md`. Review doc: `docs/engineering/ITEM9_KLINE_WINDOW_DIAGNOSIS_P12_REVIEW.md` |
| **Focused tests** | Prior **41/41** plus `77d448c3` logging / `max_count=120` premarket miss test in `tests.providers.test_opend_history_kline_1m`. Keep PIT. No `get_cur_kline`. No live OpenD in tests |
| **Broader validation** | `python tools/imp.py test affected`; do **not** claim `ITEM9_PROSPECTIVE_BAR_RECEIPT_CAPTURED` or `CALIBRATED` |
| **Dependencies** | **Independent** of Q1–Q5 / live-OE file sets. May land in parallel after P12 caveats |
| **Must rebase** | **NO vs current `origin/main`.** **YES if** post-close `origin/main` ≠ `7aade60b` |
| **Safely discarded if diagnosis changes** | **NO** for PIT. **YES** for unique-security `historyKLQuota` story (DISPROVEN). Session-day window stays **necessary if** oldest-first; `K_1M` paging still **NEEDS_MORE_EVIDENCE** |

---

## Q7 — Observability / latency

| Field | Value |
|---|---|
| **Status** | `COMMITTED_ISOLATED` |
| **Branch / worktree** | `diagnosis/observability-latency-20260915` at `.worktrees/diagnosis-observability-latency-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Unique commit** | `49529d64ed2d84cb55ab6afd7bcdbba4642bd774` `docs(imp): audit next-RTH source-to-operator hop clocks` |
| **Purpose** | Classify source→operator hop clocks and add a **wiring-only** helper — not an invasive telemetry platform. EventV1 / API / UI schema changes remain a **P1 plan**, not this commit |
| **Issue addressed** | `PROSPECTIVE_HOT_PATH_LATENCY_CAPTURED` unearned; next-RTH needs honest deltas: source→receive, receive→normalization, …, source→operator |
| **Empirical evidence** | Software audit only. Phase 5: `HOT_PATH_TELEMETRY_SOFTWARE_WIRED` ≠ `LIVE_HOT_PATH_LATENCY_VALIDATED` |
| **Affected files** | `src/market_platform_foundation/hot_path_telemetry/next_rth_latency_audit.py`, `tests/hot_path_telemetry/test_next_rth_latency_audit.py`, audit README (+622). **Did not** edit `opportunity_projections.py`, news EventV1 mapper, Item 9 kline, launcher, Vite |
| **Focused tests** | `test_next_rth_latency_audit` (helper classification only) |
| **Broader validation** | hot_path_telemetry affected; do not claim live latency validated |
| **Dependencies** | Notes/helper can land independently; useful **after** Q2 clocks exist for real hops |
| **Must rebase** | **NO vs current `origin/main`.** **YES if** `origin/main` moves |
| **Safely discarded if diagnosis changes** | **YES** — wiring helper is disposable; do not invent a second telemetry architecture |

---

## Q8 — Item 7 upstream (notes only; priority 7)

| Field | Value |
|---|---|
| **Status** | `NOTES_UNCOMMITTED` + refined copy on Q9b |
| **Branch / worktree** | `diagnosis/item7-upstream-20260915` at `.worktrees/diagnosis-item7-upstream-20260915` |
| **Source baseline SHA** | `d588728d60b139ae44b5a3667a8e120d1e21ee1c` (behind `origin/main` by `#195`/`#199`/`#202`) |
| **HEAD vs origin/main** | No unique commits. Untracked: `docs/engineering/ITEM7_UPSTREAM_GAP_DIAGNOSIS_20260915.md` |
| **Refined copy** | Q9b `134924c3` includes `docs/engineering/drafts/20260915-rth-runbook-item7-provider/ITEM7_UPSTREAM_GAP_DIAGNOSIS.md` — do not fight that branch; notes stay notes |
| **Purpose** | Record the missing generating loop. Collector is a **reader**. **No corpus fabrication. No fake rows** |
| **Issue addressed** | Lane C collector `governed_candidate_rows=0` is honest empty-corpus evidence, not software success of the gate |
| **Empirical evidence** | Cutoff `2026-09-15T09:34:05-04:00`; status `ITEM7_REAL_CORPUS_COLLECTION_SOFTWARE_READY`; `pit_valid_governed_rows=0`; blockers `NO_GOVERNED_PATH_A_TRAINING_CORPUS`, `RTH_OR_FUTURE_OUTCOMES_REQUIRED`. Prior-day capture: 3540 envelopes, **0 grid** (`NOT_TAPE_ELIGIBLE_QUOTE_MISSING_VALID_BID_ASK`). Cockpit: `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` is **upstream**, not a collector bug. `CAPTURE_CONTEXT_ABSENT` (PR #196) is **not** today’s row blocker |
| **Affected files** | Notes only on Q8. Later software: append-only `intelligence_records.jsonl` writers; admit **vendor** bid/ask into grid (**never** derive BBO from `last_price`); bind pre-existing PRODUCTION `ForecastV1` → ledger → 5m settle |
| **Focused tests** | None for the notes. Do not add tests that mint forecasts |
| **Broader validation** | `tests.intelligence.test_item7_corpus_collector` already on frozen SHA via `#199`. Must remain empty-corpus honest |
| **Dependencies** | **After** live OE loop (Q2–Q3). Priority **7** (after live path) |
| **Must rebase** | **YES** onto post-close `origin/main` before committing notes (currently on `d588728d`) |
| **Safely discarded if diagnosis changes** | **NO** for “0 governed rows + no generating loop.” **YES** for any later writer design if a lawful PRODUCTION ForecastV1 path already exists |

---

## Q9 — Runbook / test-gap docs

### Q9a — Test-gap audit (Lane P9)

| Field | Value |
|---|---|
| **Status** | `COMMITTED_ISOLATED` |
| **Branch / worktree** | `diagnosis/test-gap-audit-20260915` at `.worktrees/diagnosis-test-gap-audit-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Unique commit** | `145fee4f` `docs(imp): record 2026-09-15 live-integration test-gap matrix` (ahead of `origin/main` by 1) |
| **Purpose** | Explain how pre-RTH validation passed while live integration failed; list missing test classes; **do not weaken** existing gates |
| **Issue addressed** | Live provider→OE unwired; live ranked book fail-closed **by design/test**; fixture `as_of` as now; launcher `moomoo-api-test`; `/discover` advertised into Vite API; oldest-page kline; WATCH unreachable |
| **Empirical evidence** | Same RTH observations as Q1–Q6. This slot is the **matrix**, not a product patch |
| **Affected files** | `docs/audits/rth-live-integration-20260915/{README.md,TEST_GAP_MATRIX.md,TEST_GAP_MATRIX.json}`, `docs/README.md`, `docs/engineering/WORK_LOG.md` (+443). Follow-on tests must not collide with `test_opend_history_kline_1m.py` (Q6), launcher tests (Q1), live as_of tests (Q4), watch-dismiss acceptance (Q5) |
| **Focused tests** | Docs/audit only on `145fee4f`; no production gates weakened |
| **Broader validation** | Docs link check if committed under `docs/` |
| **Dependencies** | Last among product patches. May cite Q1–Q8 tests |
| **Must rebase** | **YES** if `origin/main` moves |
| **Safely discarded if diagnosis changes** | **YES** as a standalone merge if the owning lanes already added the missing tests |

### Q9b — RTH runbook + Item 7 stage matrix + Sept 16 PREP (Lanes P7/P8/P10)

| Field | Value |
|---|---|
| **Status** | `COMMITTED_ISOLATED` — experimental drafts |
| **Branch / worktree** | `diagnosis/rth-runbook-item7-provider-20260915` at `.worktrees/diagnosis-rth-runbook-item7-provider-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Unique commit** | `134924c3887aa2fbb3e77512718b7c72928f3a08` `docs(imp): isolate P7/P8/P10 RTH diagnosis drafts from 2026-09-15 evidence` |
| **Purpose** | Experimental drafts only: provider/session reliability from **today’s** evidence; Item 7 stage classification; operator runbook (`START_PLATFORM.cmd`, SPA `/`, IMP `.venv`, FTEP ≠ cockpit, enrichment OFF, Item 9 expected outcomes, CallClose, UTF-8 receipts); Sept 16 08:30 ET macro **checklist — not executed** |
| **Issue addressed** | Operator docs still describe wrong start URL/interpreter; FTEP ingress confused with live discovery; Item 7 vs collector honesty |
| **Empirical evidence** | Same session as Q1/Q6/Q8. Drafts must not become canonical program-status ahead of software |
| **Affected files** | `docs/engineering/drafts/20260915-rth-runbook-item7-provider/{README.md,P7_PROVIDER_SESSION_RELIABILITY.md,ITEM7_UPSTREAM_GAP_DIAGNOSIS.md,P10_OPERATOR_RUNBOOK_DRAFT.md,SEPT16_0830_ET_MACRO_WINDOW_CHECKLIST.md}`, `docs/engineering/WORK_LOG.md` (+680). Land **with** corresponding software |
| **Focused tests** | Docs-only |
| **Broader validation** | Land with Q1/Q6/Q8 software; Sept 16 checklist is PREP only |
| **Dependencies** | After or with Q1/Q6/Q8 |
| **Must rebase** | **NO vs current `origin/main`.** **YES if** `origin/main` moves |
| **Safely discarded if diagnosis changes** | **YES** as drafts; rewrite from Q8 + operator evidence |

---

## Non-members (do not treat as merge-train cargo)

| Slot | Branch / worktree | Notes |
|---|---|---|
| P12 live-OE review (`8048d5f7`) | `review/live-oe-diagnosis-20260915` at `.review-live-oe-diagnosis-20260915` | **PENDING / IN_FLIGHT.** Branch on `7aade60b`; uncommitted `docs/engineering/reviews/P12_LIVE_OE_DIAGNOSIS_FALSIFICATION_20260915.md`. **Gate on Q2–Q4.** Read-only; do not implement |
| P12 Item 9 review | `review/item9-kline-diagnosis-20260915` `49ae216e` | Gate on Q6 only. `PARTIALLY_CONFIRMED` |
| Finviz 11:49 ET HTTP 429 | n/a | **Empirical PROVIDER evidence**, not merge cargo. Do not open a software PR to “fix” rate-limit as if it were an IMP defect |
| PR #196 | `work/phase55b-lane-b-evidence-capture-context` `ec93809e` | Sidecar SOFTWARE only. **Rebase after session, not today.** `CAPTURE_CONTEXT_ABSENT` ≠ Item 7 row blocker |
| Grok / durable enrichment worker | n/a | **DEFERRED.** `#189` wiring remains OFF by default; not `GROK_AUTOMATION_PRODUCTION_ACTIVE` |
| Frozen RTH | `.rth-operator-20260915` @ `7aade60b` | Observational collection only through 16:00 ET |

---

## File-ownership collision map

| Path / concern | Owner |
|---|---|
| `ui/vite.config.ts`, `tools/platform/local_launcher.py` | Q1 (P3) |
| Item 9 kline fetch / `opend_quote_transport.py` history window | Q6 (P2) |
| `opportunity_projections.py` live-gate, projections as_of/attention, news EventV1, UI API ingress | Q2–Q4 (P1+P4) |
| Item 7 corpus **writers** / fabricated rows | **Nobody today.** Q8 notes only |
| New watch-dismiss tests | Q5 (P5) |
| New latency audit doc | Q7 (P6) |
| Canonical `PROGRAM_STATUS.md` | **Not this queue.** Coordinator updates after software lands |

## Coordinator checklist (post-close, not now)

1. Re-fetch `origin/main`. If SHA ≠ `7aade60b`, every candidate **must rebase** except already-rebased tips.
2. Re-read porcelain/SHAs: Q1 tip `9b0781c9` still on `d588728d` (**MUST rebase**); Q2–Q4 wait P1+P4 + P12 live-OE gate; Q5; Q6 tip `77d448c3` + P12 `49ae216e`; Q7 `49529d64`; Q8 untracked notes on `d588728d` (**MUST rebase** before commit); Q9a `145fee4f`; Q9b `134924c3`.
3. Wait for P12 live-OE (`8048d5f7`) classification before merging Q2–Q4.
4. Honor Item 9 P12: do not land `max_count=120`; do not treat unique-security `historyKLQuota` as proven.
5. Merge **nothing** into frozen RTH. Do not land this queue as product software.
6. Do not flip empirical gates from these software/docs commits. Finviz 429 is provider evidence, not a queue member.
7. Update canonical PROGRAM_STATUS only after accepted landings — not from this isolated document.
