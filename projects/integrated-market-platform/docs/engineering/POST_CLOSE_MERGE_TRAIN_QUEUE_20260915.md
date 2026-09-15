# Post-close merge-train queue — 2026-09-15

**Classification:** `ISOLATED_COORDINATOR_QUEUE` (not program-status truth)  
**Branch / worktree:** `diagnosis/merge-train-20260915` at  
`C:/Users/adame/Desktop/market-trading-platform/.worktrees/diagnosis-merge-train-20260915`  
**Queue snapshot SHA:** `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` (`origin/main` at snapshot)  
**Frozen RTH runtime:** `.rth-operator-20260915` at the same SHA — **do not thaw, patch, or merge into it**  
**This document does not update** [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md)

Snapshot time: 2026-09-15 ~15:12 ET (refresh of `49c4f618`). P8 stacked tip is now `64764c29` (local; was `aa826110`; **not** a second PR). Draft [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) remains the main-based `P1_HANDLER_ADMIT_MISSING` gate. On live-OE, ingest+PIT+detector work; next hard fail `P4_RANKED_SUMMARY_BLOCKED` (`UI_SECRET_LEAK_BLOCKED`). **Do not delete the leak audit.** **Not empirical.**

## Rebase-required flags (vs `origin/main` `7aade60b`)

| Slot | Tip | Merge-base | Must rebase before land |
|---|---|---|---|
| Q1 / TRAIN 1 launcher | `80792ea7` | `7aade60b` | Draft [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206). All six claims **SAFE-TO-RETAIN-AFTER-REBASE**. No MUST-FIX. Reconstruct `f1aaacaa` on `7aade60b` — **not** a merge of `diagnosis/launcher-routing-20260915`. **Do not merge during RTH.** Rebase if `main` moved |
| Q2–Q4 live-OE / cockpit | `96ede754` | `7aade60b` | Draft [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) **SAFE-TO-RETAIN-AFTER-REBASE** (ingest review). **Do not merge during RTH.** Residuals: `received=available`; POST can rewrite `as_of`. **ACK/WATCH fail-closed.** **rebase-required=yes** |
| Q5 WATCH harness | `7a5cbe48` | `7aade60b` | **YES if** `origin/main` moves after close. Independent of Item 9. Paper fixture path; acks stay blocked in `LIVE_OBSERVATIONAL`. Draft [#204](https://github.com/AdamEddahmouni/market-trading-platform/pull/204) opened at `f8c03183`, being updated |
| P8 fullstack acceptance | `b0836b90` (PR) / `64764c29` (stacked local) | `7aade60b` / `96ede754` | [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) main-base `P1_HANDLER_ADMIT_MISSING`. Stacked next fail `P4_RANKED_SUMMARY_BLOCKED`. **Do not delete leak audit.** **Not pushed** as a second PR. **Not empirical** |
| Q6 Item 9 | `fe8cac6d` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves. Draft [#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203). Local tip 1 ahead of remote `77d448c3` |
| Q6 P12 review | `49ae216e` | (review branch) | Gate only — **not merge cargo** |
| Finviz reliability | `f696f00d` | (draft [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207)) | Receipts only. **NOT FOR MERGE** until RTH reconciliation. Not a “fix HTTP 429” product patch |
| Q7 latency | `49529d64` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves |
| Q8 Item 7 notes | `d588728d` + untracked notes | `d588728d` | **YES** onto post-close `origin/main` before committing notes |
| Q9a test-gap | `145fee4f` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves |
| Q9b runbook | `134924c3` | `7aade60b` | **NO vs current main**; **YES if** `origin/main` moves |
| This queue | `49c4f618` + this refresh | `7aade60b` | Docs only; **YES if** `origin/main` moves |

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

1. **Q1 / TRAIN 1** `80792ea7` / [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206) — **SAFE-TO-RETAIN-AFTER-REBASE**. Wait for 2026-09-15 RTH reconciliation → rebase if `main` moved → **do not merge** `diagnosis/launcher-routing-20260915` → coordinate P1 before any `server.py` unquote
2. **Q4** `8189af4c` + honesty `91b07b4f` + ingest `96ede754` / [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) — **SAFE-TO-RETAIN-AFTER-REBASE**; **do not merge during RTH**
3. **Q3** `c43688ed` + `91b07b4f` + `96ede754` ranked READ — same hold; **ACK/WATCH fail-closed**
4. **Q2** `c4d88ef7` + `91b07b4f` + `POST /intelligence/ingest/news` `96ede754` / [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) — same hold; residuals `received=available`, POST can rewrite `as_of`
5. **P8 fullstack** [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) `b0836b90` after TRAIN 3/4 [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205); stacked local `64764c29` — **NOT FOR MERGE** until RTH reconciliation; do **not** delete leak audit
6. **Q5** `7a5cbe48` WATCH harness (Paper `INTERNAL_SIMULATION` fixtures; **not** empirical; failure cases 6/6; draft [#204](https://github.com/AdamEddahmouni/market-trading-platform/pull/204) being updated from `f8c03183`)
7. **Q6 Item 9 session-day kline** `fe8cac6d` / draft [#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203) (independent; not calibration)  
8. **Q7 latency notes/telemetry**  
9. **Q8 Item 7 upstream wiring** (priority 7; no corpus fabrication)  
10. **Q9 runbook / test-gap docs** (land with corresponding software)

P12 diagnosis review **FINISHED** `PARTIALLY_CONFIRMED` (`5f965f32`). P13 flagged `c43688ed` **MUST-FIX-BEFORE-MERGE**. P1 closed those leaks at `91b07b4f342f8a73dcaa237dc4de1e5c69c86593` `Close live OE honesty leaks flagged by P13`. P13B `4176d0b6` classifies **honesty** **SAFE-TO-RETAIN-AFTER-REBASE**. Tip is now `96ede7548911f384e65014d2d015b7a142675eac` `Admit already-fetched Finviz news on the UI API request path` (`POST /intelligence/ingest/news` `put_event`s EventV1 through `ObservationIngressRouter`; already-fetched only, no auto-fetch). Stack: `8189af4c` → `c4d88ef7` → `c43688ed` → `91b07b4f` → `96ede754`. Ingest review classifies tip **SAFE-TO-RETAIN-AFTER-REBASE**. Draft [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) — **do not merge during RTH.** **ACK/WATCH fail-closed.** **rebase-required=yes**. Finviz reliability draft [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) (`repair/finviz-ingress-reliability-20260915` `f696f00d`). TRAIN 1 [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206) `80792ea7` / `f1aaacaa`: all six claims **SAFE-TO-RETAIN-AFTER-REBASE**; no MUST-FIX; reconstruct on `7aade60b`, **not** a merge of stale `d588728d`.

Prior must-fix list (**closed** on honesty `91b07b4f` + ingest review of `96ede754`): live `INELIGIBLE` not on current book; no `READY` when `as_of` UNAVAILABLE; `inspect` / `store.as_of_time()` UNAVAILABLE without live receive; `replay_shelf` is `DEMO_REPLAY` and out of current items. Request-path admit is **SAFE-TO-RETAIN-AFTER-REBASE**.

**Residuals (do not block retain):** `received=available`; POST can rewrite `as_of`. Also: no Finviz auto-fetch; mixed-discovery EMPTY vs UNAVAILABLE; residual `store.as_of_time_ns` footgun if someone assigns fixture `prediction_cutoff()`. **ACK/WATCH stay fail-closed.** Vite `/opportunities` is TRAIN 1 / [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206). P8 fullstack [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) `b0836b90` / stacked local `64764c29` depends on [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205); next fail `P4_RANKED_SUMMARY_BLOCKED`. Q5 `7a5cbe48` / [#204](https://github.com/AdamEddahmouni/market-trading-platform/pull/204). Q6 `fe8cac6d` / [#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203).

---

## Q1 — Launcher / SPA routing (TRAIN 1)

| Field | Value |
|---|---|
| **Status** | All six TRAIN 1 claims **SAFE-TO-RETAIN-AFTER-REBASE**. No MUST-FIX-BEFORE-MERGE. Draft [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206). **Do not merge during RTH** |
| **Branch / worktree** | `repair/launcher-routing-from-main-20260915` HEAD `80792ea75b0e49ddff35603964e22dd92460c316` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **HEAD vs origin/main** | Unique repair `f1aaacaa` `fix(platform): reconstruct launcher routing on origin/main` then tip `80792ea7` (notes SHA). Reconstruction on `7aade60b` — **not** a merge of `diagnosis/launcher-routing-20260915` / `d588728d` |
| **Superseded / do not land** | `diagnosis/launcher-routing-20260915` (`9b0781c9` on stale `d588728d`) — **DO NOT LAND** |
| **Purpose** | One-click IMP Python + SPA URL + Vite proxy so operator JSON is not swallowed by `index.html` |
| **Issue addressed** | Launcher auto-selected `moomoo-api-test` (no sklearn); `START_PLATFORM` opened proxied `/discover` (API 404); `/opportunities` unproxied (Zod parse of HTML); `/discover` HTML not bypassed. `server.py` percent-decode/unquote **OMITTED / OUT OF SCOPE** — P1/tiny follow-on, not TRAIN 1 |
| **Empirical evidence** | 2026-09-15 Lane E: `http://127.0.0.1:5173/` Paper loads; GET `/discover` 404; ranked fetch via UI origin failed; API `:8766` returned `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`. Proxy-only would still show an empty live book |
| **Affected files** | `f1aaacaa` (14 files, +357/−48): `tools/platform/local_launcher.py`, `tools/platform/control_service.py`, `START_PLATFORM.cmd`, `PLATFORM_CONTROL.cmd`, `ui/vite.config.ts`, `tests/platform/test_local_launcher.py`, `tests/platform/test_operator_control_service.py`, `tools/validation_manifest.json`, `README.md`, `ui/README.md`, `docs/engineering/LOCAL_DEVELOPMENT.md`, launcher design spec, `WORK_LOG.md`, `BRANCH_NOTES.md`. **No** `ui_api/server.py`. Tip `80792ea7` is notes-only |
| **Focused tests** | Review re-ran `tests.platform.test_local_launcher` + `tests.platform.test_operator_control_service`: **24 passed** |
| **Broader validation** | After RTH reconciliation: rebase if `main` moved; `python tools/imp.py test affected`; UI typecheck/test if Vite remains; **not** FULL until stacked with Q2–Q4 |
| **Dependencies** | Does **not** populate the ranked book. Coordinate P1 before any `server.py` unquote |
| **Must rebase** | **NO vs current `origin/main`.** **YES if** `origin/main` moves after close. Land only after 2026-09-15 RTH reconciliation |
| **Residuals (not blockers)** | sklearn-only probe; Mixed Live menu copy vs SPA root `/`; `BRANCH_NOTES` HEAD field `f1aaacaa` vs git HEAD `80792ea7`; Vite/control proofs are token greps |
| **Safely discarded if diagnosis changes** | **NO** for Vite `/opportunities` + `/discover` HTML bypass and sklearn interpreter. Stale `d588728d` diagnosis branch **must not** land |

---

## Q2 — Provider / EventV1 convergence (admission)

| Field | Value |
|---|---|
| **Status** | Tip `96ede754` / draft [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) **SAFE-TO-RETAIN-AFTER-REBASE** (ingest review). **Do not merge during RTH** |
| **Branch / worktree** | `repair/live-oe-cockpit-state-20260915` at `.worktrees/repair-live-oe-cockpit-state-20260915` (same file set as Q3+Q4) |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **HEAD vs origin/main** | Tip `96ede7548911f384e65014d2d015b7a142675eac`. Stack: `8189af4c` → `c4d88ef7` → `c43688ed` → `91b07b4f` → `96ede754` |
| **Purpose** | Admit **already-fetched** Finviz news as `EventV1` on the UI API request path via `POST /intelligence/ingest/news` (`put_event` through `ObservationIngressRouter`) so observational ranked reads can see qualifying `OpportunityV1` |
| **Issue addressed** | Honesty `91b07b4f` stopped claiming handler admit. `96ede754` adds explicit ingest: already-fetched only, **no auto-fetch**. Ingest review **SAFE-TO-RETAIN-AFTER-REBASE**. Residuals: `received=available`; POST can rewrite `as_of` |
| **Empirical evidence** | Lane A `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS`. Moomoo `CONNECTED_DEGRADED` 0/12. Diagnosis [520aeed6](520aeed6-3d55-47a3-85ff-6b314fcdfd9a); P12 `5f965f32`; P13B honesty 62/62. Ingest not empirically proven on RTH |
| **Affected files** | Prior stack plus `96ede754` (+497/−19): `ui_api/news_ingest.py`, `ui_api/server.py`, `news/observational_opportunity.py`, `news/event_v1_ingress.py`, `ui_api/live_intelligence.py`, `ui_api/opportunity_projections.py`, `observation_ingress/consumers.py`, `tests/ui1/test_news_event_v1_request_path.py`, docs. **Not** Vite/launcher (Q1/P3) |
| **Focused tests** | Honesty **62/62** (P13B). Ingest adds `tests.ui1.test_news_event_v1_request_path`. **ACK/WATCH stay fail-closed** |
| **Broader validation** | After close rebase: `python tools/imp.py test affected` on intelligence/news/ui_api; do not enable Live or enrichment |
| **Dependencies** | Lands **after** `8189af4c` / `91b07b4f`. Does not replace Q3. Vite `/opportunities` is P3/Q1. No auto-fetch |
| **Must rebase** | **YES** (`rebase-required`). **Do not merge during RTH** |
| **Safely discarded if diagnosis changes** | EventV1-as-today's-UNAVAILABLE-cause is **weakened** (P12). Keep FTEP dry-run honesty. Do not treat EventV1 as sufficient for Q3 |

---

## Q3 — OE observational read

| Field | Value |
|---|---|
| **Status** | Tip `96ede754` / draft [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) **SAFE-TO-RETAIN-AFTER-REBASE**. **Do not merge during RTH** |
| **Branch / worktree** | Same as Q2: `repair/live-oe-cockpit-state-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Purpose** | Allow `LIVE_OBSERVATIONAL` **reads** of a live (possibly EMPTY) ranked repository; ACK/WATCH still blocked |
| **Issue addressed** | P13B **CONFIRMED** on `91b07b4f`: `include_ineligible` gone; live INELIGIBLE not on current book; `READY` never when `as_of` UNAVAILABLE. `96ede754` lets ranked reads see qualifying `OpportunityV1` after ingest. **ACK/WATCH stay fail-closed** (`WATCH_BLOCKED` / `DISMISS_BLOCKED` `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`) |
| **Empirical evidence** | Lane E `opportunities-summary-1050.json` UNAVAILABLE / `items=[]`. P13B software tests lock ACK/WATCH fail-closed |
| **Affected files** | `c43688ed` + `91b07b4f` + `96ede754` (`opportunity_projections.py`, ingest path). Shared with Q2 |
| **Focused tests** | Honesty **62/62**. Ingest request-path tests added. Ranked READ allowed; **ACK/WATCH still blocked** |
| **Broader validation** | After close rebase: ui1 opportunity API + discovery; Vite `/opportunities` still P3/Q1 |
| **Dependencies** | **Hard:** do **not** land without first-stack `8189af4c` (Q4) and honesty `91b07b4f`. EventV1 helpers (`c4d88ef7`) alone are **not sufficient** |
| **Must rebase** | **YES** (`rebase-required`). **Do not merge during RTH** |
| **Safely discarded if diagnosis changes** | **NO** for keeping live **mutations** fail-closed |

---

## Q4 — Cockpit live-state honesty

| Field | Value |
|---|---|
| **Status** | Tip `96ede754` / draft [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) **SAFE-TO-RETAIN-AFTER-REBASE**. **Do not merge during RTH** |
| **Branch / worktree** | Same as Q2: `repair/live-oe-cockpit-state-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Purpose** | Honest RTH clock and attention: `LIVE_OBSERVATIONAL` without live receive time → `as_of` UNAVAILABLE (never BIYA 2026-07-21 as “now”); quarantine replay/MC9/ES as current RTH cards |
| **Issue addressed** | P13B **CONFIRMED**: default live `store.as_of_time()` and inspect EVIDENCE `as_of` are UNAVAILABLE without live receive. `replay_shelf` count 8, label `DEMO_REPLAY`, no id overlap with current `items=[]`. Residual **follow-on** (does not block): if `as_of_time_ns` is set to `prediction_cutoff()`, `store.as_of_time()` becomes July 21 while `display_as_of_time` stays UNAVAILABLE — production `run_ui_api` does not assign `as_of_time_ns` |
| **Empirical evidence** | Lane E: 7 replay/fixture attention cards; ranked banner unavailable. P13B software: current items empty; shelf locked out |
| **Affected files** | `8189af4c` (+177/−22) plus `91b07b4f`: `ui_api/projections.py`, `ui_api/store.py`, `tests/ui1/test_live_observational_state.py`, `docs/architecture/MODE_AUTHORITY.md` |
| **Focused tests** | Shared stack **62/62**. Includes `tests.ui1.test_live_observational_state` |
| **Broader validation** | After close rebase: ui1 projection tests |
| **Dependencies** | **Already first** on this branch. Must remain first |
| **Must rebase** | **YES** (`rebase-required`). **Do not merge during RTH** |
| **Safely discarded if diagnosis changes** | **NO** if July-21 `as_of` remains empirically observed |

---

## Q5 — WATCH / DISMISS acceptance harness

| Field | Value |
|---|---|
| **Status** | `COMMITTED_ISOLATED` — draft [#204](https://github.com/AdamEddahmouni/market-trading-platform/pull/204) opened at `f8c03183`, being updated |
| **Branch / worktree** | `repair/watch-dismiss-acceptance-20260915` at `.worktrees/repair-watch-dismiss-acceptance-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Unique commits** | `f8c0318352bd5edc1c3400c80777f67defd67b91` happy-path acceptance; tip `7a5cbe48032f88dd55b3e91cdb76211358aa4bc7` `test(imp): add WATCH/DISMISS fixture failure cases` |
| **Purpose** | Fixture-only: ranked `OpportunityV1` → operator ack → `ExecutionDecisionTrace` → `TradeReviewV1` → SQLite persist → restart readback. Paper `INTERNAL_SIMULATION` path |
| **Issue addressed** | Downstream WATCH/DISMISS plumbing unproven on RTH (no ranked OE cards). This harness does **not** unblock live acks. `7a5cbe48` adds fail-closed cases: stale, missing evidence, duplicate ack, invalid opportunity, `LIVE_OBSERVATIONAL` |
| **Empirical evidence** | **None — harness, not empirical.** Do not describe as live evidence. Live mutations still fail-closed on this SHA (P1 live-gate **not** edited) |
| **Affected files** | `f8c03183`: `tests/opportunity/test_watch_dismiss_learning_loop_acceptance.py`, `tests/opportunity/__init__.py`, `tools/validation_manifest.json` (`core_checkpoint_required=true`), `tests/validation/test_validation_manifest.py`, `docs/engineering/WORK_LOG.md`. Tip `7a5cbe48` (+270): `tests/opportunity/test_watch_dismiss_learning_loop_failure_cases.py`, `docs/engineering/WORK_LOG.md` |
| **Focused tests** | Happy path **5/5** in `tests.opportunity.test_watch_dismiss_learning_loop_acceptance`. Failure cases **6/6** in `tests.opportunity.test_watch_dismiss_learning_loop_failure_cases`. **Not empirical** |
| **Broader validation** | Manifest change sets `core_checkpoint_required=true` — run `python tools/imp.py validate changed` / FULL before land, not focused-only |
| **Dependencies** | **Independent of Item 9.** Acks stay blocked in `LIVE_OBSERVATIONAL` even after P1 ranked-read (`c43688ed`). Do **not** require landing after P1 for this Paper fixture path. Correlation is `opportunity_id`+`action` — `review_id` is **not** on the trace; `WATCHED`/`REJECTED` forbid `execution_decision_trace_id` |
| **Must rebase** | **YES if** post-close `origin/main` ≠ `7aade60b` |
| **Safely discarded if diagnosis changes** | **YES** if a better existing loop test already covers the chain |

---

## P8 — Software-only fullstack acceptance

| Field | Value |
|---|---|
| **Status** | Draft [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) — **NOT FOR MERGE UNTIL 2026-09-15 RTH RECONCILIATION COMPLETE**. Auto-merge **off**. Software-only. **Not empirical** |
| **Branch / worktree (PR)** | `repair/live-fullstack-acceptance-20260915` @ `b0836b908938a48f76b160c9c0adf63349d4567f` on `origin/main` `7aade60b` |
| **Stacked local branch** | `repair/live-fullstack-on-oe-20260915` @ `64764c29f09f971c748568796b9218c899f62477` (was `aa826110`; **not pushed** as a second PR). Base live-OE `96ede754` / [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) |
| **Source baseline SHA** | PR: `7aade60b`. Stacked: `96ede754` |
| **Purpose** | Honest next-RTH software gate. Do not pass via ReplayStore, library ingress, Live, Grok, or a broker order |
| **Issue addressed** | Draft [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) on **main** still **FAILS** `P1_HANDLER_ADMIT_MISSING` (honest). On live-OE stack with current clocks: `POST /intelligence/ingest/news` admits EventV1, PIT (publication ≠ retrieval), detector minted `OpportunityV1`, persist/readback, in-process ranked assembly `READY` `items=1`. Next hard fail: **`P4_RANKED_SUMMARY_BLOCKED`** — `GET /opportunities/summary` status 500 reason `UI_SECRET_LEAK_BLOCKED` (`items[0].decision_support.authority` / `instrument_key` → `SECRET_SHAPED_KEY_WITH_LIVE_VALUE`). WATCH not reached. Frozen-runtime mutation/read gate remains `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`, **not** this HTTP 500. **Do not treat this as license to delete the leak audit** |
| **Empirical evidence** | **None.** Software-only. Do not describe as live evidence |
| **Affected files** | `tests/acceptance/test_software_fullstack_acceptance.py` only so far (`64764c29` +241/−14). **Not** in `validation_manifest.json` |
| **Focused tests** | Stacked tip exercises POST ingest then fail-closed HTTP ranked read. Supporting tests still pass on both bases |
| **Broader validation** | Depends on TRAIN 3/4 [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205). Do not enable Live or enrichment |
| **Dependencies** | **Hard:** land / rebase after [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205). Independent of Item 9 |
| **Must rebase** | PR vs `7aade60b`: **YES if** `origin/main` moves. Stacked branch must stay on post-rebase [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) |
| **Safely discarded if diagnosis changes** | **YES** if a better request-path fullstack contract already exists after [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) |

---

## Q6 — Item 9 session-day 1m kline window

| Field | Value |
|---|---|
| **Status** | `COMMITTED_ISOLATED` + P12 `PARTIALLY_CONFIRMED` — draft [#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203) (GitHub head at snapshot still `77d448c3`; queue tip `fe8cac6d`) |
| **Branch / worktree** | `diagnosis/item9-prospective-bar-20260915` at `.worktrees/diagnosis-item9-prospective-bar-20260915` |
| **Source baseline SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| **Unique commits** | `e2d89348` session-day window; `77d448c3` kline diagnostics; tip `fe8cac6dc82725318d0f3557517f5284e3042a32` `test(item9): cover empty RET_OK, RET_ERROR, year-old, and incomplete-bar fail-closed paths`. **Not pushed** (local 1 ahead of `origin/diagnosis/item9-prospective-bar-20260915` `77d448c3`) |
| **P12 review** | `review/item9-kline-diagnosis-20260915` `49ae216e682ea506dcb3c5ec6bc9fc0ee592ee0b` — overall **PARTIALLY_CONFIRMED**. `K_1M` oldest-first **NEEDS_MORE_EVIDENCE**. Unique-security `historyKLQuota` as hour-2 cause **DISPROVEN**. Do not land session-day with `max_count=120` |
| **Purpose** | Bind OpenD `request_history_kline` to the observation `America/New_York` session date (`max_count>=1000`); log `raw_row_count` / first-last `time_key` / vendor `retMsg`; prove `max_count=120` still misses RTH after 330 premarket minutes **if** paging is oldest-first |
| **Issue addressed** | Vendor `start=None,end=None` expands to `[today-365d, today]`. Poll #1 `PROSPECTIVE_NO_POST_SIGNAL_BAR` — timeout reason is **not** uniquely a post-signal PIT reject (collapsed codes). PIT (`available_time > signal_time`, incomplete-bar hide) **unchanged**. `fe8cac6d` adds fail-closed coverage for empty `RET_OK`, `RET_ERROR` protocol, year-old PIT reject, and incomplete bar — no `get_cur_kline` |
| **Empirical evidence** | Poll #1 2026-09-15: `PROSPECTIVE_NO_POST_SIGNAL_BAR`, `receipt=null`. Capability-report `time_key` `2025-09-15` is mechanism inference, not a captured 1m page. **Not calibration. Independent of the live-OE stack** |
| **Affected files** | `e2d89348` + `77d448c3` + `fe8cac6d` (+183 tests/log only on the tip): `tools/moomoo/opend_quote_transport.py`, `src/market_platform_foundation/paper/calibration/bar_ohlcv_sources.py`, `src/market_platform_foundation/paper/calibration/bar_ohlcv_prospective_proof.py`, `tests/providers/test_opend_history_kline_1m.py`, `docs/engineering/ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md`, `docs/engineering/WORK_LOG.md`. Review doc: `docs/engineering/ITEM9_KLINE_WINDOW_DIAGNOSIS_P12_REVIEW.md`. Tip does **not** edit live-OE / cockpit |
| **Focused tests** | **48/48** in `tests.providers.test_opend_history_kline_1m` covering empty `RET_OK`, `RET_ERROR` protocol, year-old PIT reject, and incomplete-bar fail-closed. PIT preserved. No `get_cur_kline`. No live OpenD in tests. **Not calibrated** |
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
| P12 live-OE diagnosis | `review/live-oe-diagnosis-20260915` `5f965f32` | **FINISHED** `PARTIALLY_CONFIRMED`. **Not merge cargo** |
| Live-OE **patch** re-probe | `review/live-oe-patch-20260915` note `P13B_LIVE_OE_PATCH_REPROBE_20260915.md` (P13B `4176d0b6`) vs honesty `91b07b4f` | Honesty **SAFE-TO-RETAIN-AFTER-REBASE.** **Not merge cargo** |
| Live-OE ingest draft PR | [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) `96ede754` | **SAFE-TO-RETAIN-AFTER-REBASE.** **Do not merge during RTH.** Residuals: `received=available`; POST can rewrite `as_of` |
| P12 Item 9 review | `review/item9-kline-diagnosis-20260915` `49ae216e` | Gate on Q6 only. `PARTIALLY_CONFIRMED` |
| Finviz 11:49 ET HTTP 429 | n/a | **Empirical PROVIDER evidence**, not a defect-fix cargo |
| Finviz reliability draft | [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) `repair/finviz-ingress-reliability-20260915` `f696f00d` | Receipts. **NOT FOR MERGE** until RTH reconciliation. Do not treat as a 429 “fix” |
| PR #196 | `work/phase55b-lane-b-evidence-capture-context` `ec93809e` | Sidecar SOFTWARE only. **Rebase after session, not today.** `CAPTURE_CONTEXT_ABSENT` ≠ Item 7 row blocker |
| Grok / durable enrichment worker | n/a | **DEFERRED.** `#189` wiring remains OFF by default; not `GROK_AUTOMATION_PRODUCTION_ACTIVE` |
| Stale launcher | `diagnosis/launcher-routing-20260915` `9b0781c9` on `d588728d` | **DO NOT LAND.** Superseded by TRAIN 1 `80792ea7` / [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206) |
| Launcher reconstruct review | `c39ab0af` vs [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206) `80792ea7` / `f1aaacaa` | **FINISHED.** All six TRAIN 1 claims **SAFE-TO-RETAIN-AFTER-REBASE**. No MUST-FIX. **Not merge cargo** |
| P8 fullstack draft | [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) `b0836b90` | Main-base `P1_HANDLER_ADMIT_MISSING`. Stacked local `64764c29` next fail `P4_RANKED_SUMMARY_BLOCKED`. **Do not delete leak audit.** **Not** a second PR |
| Frozen RTH | `.rth-operator-20260915` @ `7aade60b` | Observational collection only through 16:00 ET |

---

## File-ownership collision map

| Path / concern | Owner |
|---|---|
| `ui/vite.config.ts`, `tools/platform/local_launcher.py` | Q1 / TRAIN 1 ([#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206)) |
| `ui_api/server.py` percent-decode/unquote | **P1** — omitted from TRAIN 1; coordinate before adding |
| Item 9 kline fetch / `opend_quote_transport.py` history window | Q6 (P2) |
| `opportunity_projections.py` live-gate, projections as_of/attention, news EventV1, UI API ingress | Q2–Q4 (P1+P4) |
| Item 7 corpus **writers** / fabricated rows | **Nobody today.** Q8 notes only |
| New watch-dismiss tests | Q5 (P5) |
| Software fullstack acceptance probe | P8 ([#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208); stacked local `64764c29`; `tests/acceptance/test_software_fullstack_acceptance.py` only) |
| New latency audit doc | Q7 (P6) |
| Canonical `PROGRAM_STATUS.md` | **Not this queue.** Coordinator updates after software lands |

## Coordinator checklist (post-close, not now)

1. Re-fetch `origin/main`. If SHA ≠ `7aade60b`, every candidate **must rebase** except already-rebased tips.
2. Re-read porcelain/SHAs: Q1 / TRAIN 1 `80792ea7` / [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206); Q2–Q4 `96ede754` / [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205); P8 fullstack [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) `b0836b90` (main-base `P1_HANDLER_ADMIT_MISSING`) + stacked local `64764c29` on [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205) next fail `P4_RANKED_SUMMARY_BLOCKED` (`UI_SECRET_LEAK_BLOCKED`) — **do not delete leak audit**; **not pushed** as a second PR; **not empirical**; Q5 `7a5cbe48` / [#204](https://github.com/AdamEddahmouni/market-trading-platform/pull/204); Q6 `fe8cac6d` / [#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203); Finviz [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207); Q7 `49529d64`; Q8 notes on `d588728d`; Q9a `145fee4f`; Q9b `134924c3`.
3. Honesty + ingest **SAFE-TO-RETAIN-AFTER-REBASE**. Residuals: `received=available`; POST can rewrite `as_of`. **ACK/WATCH stay fail-closed.** **Do not merge during RTH.**
4. Honor Item 9 P12: do not land `max_count=120`; do not treat unique-security `historyKLQuota` as proven.
5. Merge **nothing** into frozen RTH. Do not land this queue as product software.
6. Do not flip empirical gates from these software/docs commits. Finviz 429 is provider evidence, not a queue member.
7. Update canonical PROGRAM_STATUS only after accepted landings — not from this isolated document.
