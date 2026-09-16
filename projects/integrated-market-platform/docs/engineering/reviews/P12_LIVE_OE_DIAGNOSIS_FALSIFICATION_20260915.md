# P12 adversarial review — live OE / Finviz / cockpit diagnosis (2026-09-15)

> **HISTORICAL_TRUTH.** Live OE ranked-read + EventV1 ingest later landed in
> `#205` / `#208`. This note remains the Sep 15 falsification record. Do not
> rewrite it as current architecture.

Reviewer: Lane P12 (falsify, do not confirm).
Target diagnosis: agent `520aeed6` (2026-09-15).
Frozen RTH SHA: `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` (worktree `.rth-operator-20260915`, **not edited**).
This note lives on isolated branch `review/live-oe-diagnosis-20260915` only. No merge. No P1 patch.

Key files on frozen SHA are **identical** to canonical HEAD `d588728` for the OE/Finviz/ingress path (`opportunity_projections.py`, `run_ui_api.py`, `production_wire.py`, `consumers.py`, `projections.py`, `mixed_discovery_projections.py`, `ftep_prospective_catalyst_ingress.py`, `observational_ingress.py`). Reading current IMP source is valid for today's runtime.

Overall: **PARTIALLY_CONFIRMED**. Directionally right about EventV1/OE/FTEP split and July 21 BIYA clock. Overclaims “first broken boundary is ADMISSION” as the cause of ranked-empty. Several attack questions fail to fully kill the diagnosis; one (live quote clock) is disproven. Do not rubber-stamp CONFIRMED.

---

## Claim table

| Claim | Verdict |
|---|---|
| First broken boundary is ADMISSION (live Finviz/Moomoo never EventV1 in UI API process) | **PARTIALLY_CONFIRMED** |
| FTEP is dry-run CLI `NewsArticleEvent`, not EventV1 | **CONFIRMED** |
| ReplayStore pinned BIYA July 21 `as_of` | **CONFIRMED** (with a focus-resolution nuance) |
| `_is_live` fail-closes ranked OE with `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`; tests lock it | **CONFIRMED** for UI API ranked surface; **not** “frontend-only” |
| Deleting the gate would rank fixtures | **CONFIRMED** as ranked `NOT_OPPORTUNITY_V1` attention rows |
| Production ingress not attached to `UiApiHandler` | **CONFIRMED** |
| Detectors SEC/PTR only | **PARTIALLY_CONFIRMED** (true for production ingress consumer; false for BUILD 09 engine) |
| Another EventV1 path ran today in the cockpit process | **DISPROVEN** for UI API EventV1; **NEEDS_MORE_EVIDENCE** for a separate capture-materialize process |
| `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` is only UI | **PARTIALLY_CONFIRMED** (UI API backend, not React; also blocks **reads**, not only mutations) |
| Mixed discovery was the live Opportunity Engine | **DISPROVEN** |
| `as_of_time` was a live quote clock, not BIYA | **DISPROVEN** |
| Finviz news already persisted into EventV1 / ranked repo | **DISPROVEN**; CLI stdout **was** persisted |
| Feature flags on `7aade60` would have wired EventV1 into UI API if set | **DISPROVEN** |

---

## Attack 1 — another EventV1 path that DID run today?

**Verdict: DISPROVEN for the UI API process. NEEDS_MORE_EVIDENCE for a sidecar materialize.**

What actually ran in-process:

- `ReplayStore.load()` always ingests pinned BIYA adapter dicts (`event_type` `BAR_OHLCV_1M`, `SOURCE_OBJECT_ID = ADMITTED-SHORTSQ-BIYA-BARS-001`). Those are **not** `EventV1`.
- Moomoo quotes live in `ObservationalStateStore` / `live_runtime` (`market_data/observational_state.py`). `market_data/` has **zero** `EventV1` / `put_event` / `observation_ingress` references.
- Mixed discovery `refresh()` calls `DiscoveryEngine.run_screen` → `CandidateSet` memory. Not EventV1.
- FTEP `--live-ingress` at 10:01 ET produced 100 in-memory `NewsArticleEvent`s (`normalize_finviz_export_item`). Frozen stdout: `.rth-operator-20260915/projects/integrated-market-platform/.local/rth-session-20260915/lane-a-finviz/finviz-ingress-20260915-1001ET.stdout.txt` — `ingested_events: 100`, `universe_filtered: 19`, `manifest_universe_size: 5`, `accepted_pipeline_events: 0`, `dry_run: true`, `durable_lock: false`. No `put_event`.

Canonical `imp-state.sqlite3` (read-only):

- **No** intelligence `events` table.
- `opportunity_operator_acks = 0`, `trade_reviews = 0`, `enrichment_outbox = 0`, `forward_test_observations = 0`.
- `paper_events = 897` are Paper **ledger** rows (`PaperAccountCreated`, `PaperSessionOpened`, …) per `local_state/schema.py`. Max `event_time` ns is session-open era (~09:38 ET), not EventV1.
- `capture_catalog = 5` Moomoo JSONL files under `evidence/live-captures/p21-*` (BIYA / AAPL+NVDA). `indexed_at` is during today's RTH; envelope `start_time_ns` is **older P21 captures**, not this morning's tape.

`materialize_opend_capture_jsonl` **is** a production EventV1 dispatcher (`opend_capture_ledger.py` → `build_production_observation_ingress_router`). `tools/` never calls it. `hot_path_telemetry/software_wired.py` is fixture proof. No evidence that today's UI API process dispatched those JSONL files. Catalog indexing ≠ ingress dispatch. If P1 claims “zero EventV1 anywhere on the machine today,” that is **not** proven; it is proven that the **cockpit process** did not bind an `IntelligenceRepository` or router.

`run_ui_api._load_store` never sets `strategy_repository`. `ReplayStore.strategy_repository` defaults to `None` (`store.py`). Production assignment of `strategy_repository` exists only in tests.

---

## Attack 2 — is `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` only UI?

**Verdict: PARTIALLY_CONFIRMED.**

Runtime sites (frozen SHA):

- `opportunity_projections.py`: `_feed_status`, `build_opportunities_summary_payload` (read), `build_opportunity_detail_payload` (read), `apply_opportunity_ack` (mutation).
- `ui_api/errors.py` taxonomy → `MODE_BLOCKED`.
- Tests: `tests/ui1/test_opportunity_api.py::test_live_mode_returns_unavailable_empty_queue` (empty **read**); `tests/ui1/test_opportunity_radar_feed.py::test_live_detail_and_ack_fail_closed`.
- Docs: `DATA_CONTRACTS.md` frames it as live observational **mutation**. Code also fail-closes **reads**. That doc/code mismatch is a diagnosis gap, not a falsification of the lock.

Not gated by this string:

- `OpportunityEngine.assess` / `opportunity/bridge.py` `put_opportunity`.
- Mixed discovery (`candidate_role=INVESTIGATE`).
- FTEP `rank_opportunity_summaries` (CLI).
- BUILD 09 `DetectionEngine`.

So: not a React-only banner. It is the **UI API ranked-feed gate**. The engine can still mint in other processes; those mints never reach `/opportunities/summary` while `_is_live` is true.

Critical causal point the diagnosis underweights: `build_opportunities_summary_payload` returns `items=[]` **before** `build_ranked_rows`. Even if EventV1 and `OpportunityV1` had been in `strategy_repository` today, the cockpit ranked book would still be `UNAVAILABLE`. Admission is **not** the proximate cause of the observed reason code.

```199:207:projects/integrated-market-platform/src/market_platform_foundation/ui_api/opportunity_projections.py
    if _is_live(store):
        return {
            "as_of_context": projections.build_as_of_context(store),
            "quality_summary": projections.build_quality_summary(store),
            "feed_status": "UNAVAILABLE",
            "reason": "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE",
            "items": [],
            "next_cursor": None,
        }
```

`_is_live` is `data_mode == "LIVE_OBSERVATIONAL" or mode == "LIVE"`. Today's payload is `data_mode=LIVE_OBSERVATIONAL` and `mode=SIMULATION` (`opportunities-summary-1111.json`). The gate is tripped by observational data mode under `IMP_LIVE_OBSERVATIONAL=1` (`store._bind_local_state` + `resolve_live_operating_modes`), including Paper UI.

---

## Attack 3 — could mixed discovery have been the live OE?

**Verdict: DISPROVEN.**

`MixedDiscoveryService._project` hard-codes `candidate_role: "INVESTIGATE"`, `execution_authority: "NONE"`, `mode: "SEMI_LIVE"`. Ranking is `aggregate_candidate_sets`, not `OpportunityEngine`. It is **not** gated by `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`.

`assemble_opportunity_review_rows` **skips** rows that look like discover candidates (`_DISCOVER_KEYS = {attention_score, screen_ids, matched_reasons}`). Mixed rows cannot become ranked OE via ingest even if the live gate were deleted.

What mixed **did** do today: `POST /discover/mixed/refresh` ran in the UI API process. `discovery_as_of` moved from `null` (09:46, all `NO_SAVED_CAPTURE`) to `2026-09-15T14:01:49Z` then `14:35:31Z`, all eight screens `FINVIZ_SCREEN_UNAVAILABLE`, `candidate_count=0`. That is a live Finviz **screener** loop, not OE. Diagnosis already said screener ran; it should not be restated as “Finviz never entered UI API.”

`FINVIZ_SCREEN_UNAVAILABLE` is assigned whenever `CandidateSet.quality != PASS`. `DiscoveryEngine` sets `quality = quality if candidates else "UNAVAILABLE"`, so a **successful empty export** is indistinguishable from a failed fetch. Empty-vs-failed remains an observability gap (diagnosis correct). Default `data/captures/finviz` does not exist on the canonical tree; that does **not** prove fetch failure (RTH may use another capture dir; `persist` only if `export.success`).

---

## Attack 4 — is `as_of_time` a live quote clock, not BIYA?

**Verdict: DISPROVEN.**

Lane E `/opportunities/summary` from 09:58 through 11:24 ET:

- `as_of_time: "2026-07-21T21:01:09.000000000Z"`
- `quality_summary.affected_symbols: ["BIYA"]`
- `quality_summary.detail: "Admitted equity intraday fixture; bar-only capability"`

Last BIYA fixture bar (`biya_market_bars_intraday.jsonl` line 2838) has `bar_end: "2026-07-21T21:01:09.000000Z"`. Adapter maps `available_time = bar_end_ns`. `ReplayStore.as_of_time()` = `_epoch_ns_to_iso(prediction_cutoff())`.

Live-quote branch in `build_as_of_context` would emit **today's** date from `quote.received_ns`. It never did, across hours of heartbeats.

Nuance (does not revive the live-clock hypothesis): in `LIVE_OBSERVATIONAL`, `resolve_active_operator_instrument` **refuses** `SOURCE_FIXTURE_DEFAULT`. If focus is `None`, `quote_for(focus)` is skipped and code falls back to `store.as_of_time()` anyway. Mixed discovery `0/12` subscriptions are a **different** set (screener candidates). Either “no operator instrument” or “no quote for focus” yields BIYA. Quality copy is unconditional fixture text (`build_quality_summary`); `/opportunities/summary` does **not** overlay `build_live_context_overrides`.

Attention has **no** live-mode filter: `_all_attention_items` always concatenates replay cursor (`att-replay-context`), MC9 catalyst fixtures, ES fixture imbalance.

---

## Attack 5 — is Finviz news already persisted somewhere?

**Verdict: DISPROVEN for EventV1 / ranked repo / ReplayStore. CONFIRMED that CLI stdout receipts exist.**

- FTEP `collect_ftep_catalyst_watch` always `"dry_run": True`. Ingress report `"durable_lock": false`.
- `news/observational_ingress.py`: scaffolding; `wired_to_forward_test_bridge: False`; NewsAPI/Finnhub `NewsArticleEvent`, not Finviz, not EventV1.
- No EventV1 mapper from `NewsArticleEvent` exists in `src/` (grep `NewsArticleEvent.*EventV1` / `to_event_v1`: empty).
- Canonical sqlite: no news/events intelligence tables.
- Screener persist path (`persist_discovery_capture` → `data/captures/finviz`) is absent on canonical IMP; mixed in-process `_candidate_sets` are memory-only unless `export.success`.

Lane A receipts in the **frozen** `.local/rth-session-20260915/lane-a-finviz/` are operator artifacts of the CLI, not a canonical event store. Canonical `.local/rth-empirical-ops/runs/RTHOPS-*.json` used `live_ingress: false` (FIXTURE_SMOKE / SESSION_ACTIVE_CORRELATION). Those runs are **not** the 10:01 live ingress; do not confuse them with Lane A `--live-ingress`.

`universe 19` is `universe_filtered` (19 catalyst-accepted rows outside the 5-name manifest universe), not a 19-name universe. Diagnosis flagged this; the stdout proves it.

---

## Attack 6 — feature flags on frozen SHA `7aade60` that would have wired this?

**Verdict: DISPROVEN.**

Flags that **were** relevant today and still do not attach EventV1 to `UiApiHandler`:

| Flag | Effect on frozen SHA |
|---|---|
| `IMP_LIVE_OBSERVATIONAL=1` | Sets `data_mode=LIVE_OBSERVATIONAL`, starts `live_runtime`. **Causes** the OE read gate. Does not bind `strategy_repository` or production ingress. |
| `IMP_MOOMOO_LIVE=1` | Quote provider in memory. Not EventV1. |
| `IMP_FINVIZ_LIVE=1` | Allows Elite HTTP (screener, overlay, FTEP news). Mixed + FTEP. Not EventV1. |
| `IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS=1` | CLI `ftep_watch_catalysts --live-ingress` only. |
| `IMP_OBSERVATIONAL_NEWS_INGRESS=1` | NewsAPI/Finnhub `NewsArticleEvent` scaffolding. Explicitly not campaign-wired. |
| `use_production_ingress` | Parameter on OpenD **materialize**, default true **there**. No UI API env equivalent. |

`_load_store` on frozen SHA: `ReplayStore(...)`; `store.load()`; if live observational, `get_live_runtime(create=True)`. No router. No repository. No flag in that function reads Finviz/FTEP/news ingress env.

---

## Detectors — “SEC/PTR only”

**Verdict: PARTIALLY_CONFIRMED.**

Production ingress `detector_stub_consumer` (`consumers.py`): congressional PTR vertical, else SEC insider vertical, else `OBSERVED`. That is what would run **if** UI API had a router. `oe_evidence_consumer` appends dicts; it does not `put_opportunity`.

BUILD 09 `DetectionEngine` has **implemented** order-flow reversal, borrow change, liquidity, regime (external context), SEC insider. `NEWS_EVENT` is `INACTIVE_INPUT_UNAVAILABLE`. Those detectors are **not** the production ingress consumer and are not invoked from `UiApiHandler`. Saying “the platform only has SEC/PTR detectors” is false; saying “the unwired production ingress detector lane only runs SEC/PTR verticals” is true.

---

## Deleting the gate would rank fixtures

**Verdict: CONFIRMED**, with identity precision.

If `_is_live` early-return is removed, `build_ranked_rows` → `assemble_opportunity_review_rows(attention_rows=_attention_rows(store), repository=None)`. Repository mint is empty. Attention rows from `_all_attention_items` become `identity_kind="NOT_OPPORTUNITY_V1"` summaries (not `OpportunityV1`). They would still appear on `/opportunities/summary` as ranked review rows sourced from July BIYA/BOXL/ES fixtures. Do not open the gate before quarantining fixture attention and replacing as_of.

---

## First-boundary overclaim (do not let P1 patch the wrong first step)

Two independently sufficient failures:

1. **Ranked symptom (`UNAVAILABLE` / empty items):** `_is_live` projection gate. Fires regardless of EventV1.
2. **Intended production path:** live Finviz/Moomoo never become EventV1 in this process; FTEP news dies at `NewsArticleEvent`; production router not on `UiApiHandler`; fixture attention is the only candidate queue.

Calling (2) “first” is a path-diagram statement, not the request-path cause of today's ranked payload. P1 must not treat “admit Finviz as EventV1” as sufficient: without splitting **read** vs **mutation** on the live gate, a populated repository remains invisible. Unblocking reads without (2) + fixture quarantine would rank July fixtures.

---

## Evidence the diagnosis missed or under-cited

- Frozen Lane A 10:01 stdout (not only Lane E). Canonical `.local` Lane E copy is incomplete for Finviz news.
- `imp-state.sqlite3` `capture_catalog` P21 Moomoo JSONL indexed today — EventV1 **source files**, not UI API dispatch.
- `paper_events` today are Paper ledger, not EventV1. Easy false positive.
- Mixed discovery **did** run Finviz in UI API; do not phrase admission as “Finviz never in UI API.”
- `DATA_CONTRACTS.md` mutation framing vs read fail-closed.

---

## P1 implications (reviewer, not implementer)

Keep mutation block. Do not delete `_is_live` wholesale. Split read vs ack tests. Provenance/as_of/attention quarantine is the only repair that is safe **without** EventV1. EventV1 + router on UI API is the production-path repair; flags on `7aade60` would not have done it.

RTH was not thawed. No gate claimed passed.
