# P13c falsification — live-OE news ingest HEAD `96ede754`

Reviewer: falsify. No merge. No Live enable. Frozen RTH `7aade60` **not edited**. Patch branch **not edited**.

Target: `repair/live-oe-cockpit-state-20260915` HEAD `96ede7548911f384e65014d2d015b7a142675eac`  
This note: `review/live-oe-patch-20260915` only.

Overall: **SAFE-TO-RETAIN-AFTER-REBASE**. The ingest claim holds on the request path. PIT/provenance residuals are caller-asserted retrieve semantics, not a silent fixture-rank or Live-authority leak. **Do not merge mid-session today.**

Tests: 31 ran, OK (`test_news_event_v1_request_path`, `test_finviz_news_event_v1_ingress`, `test_live_observational_state`, `test_opportunity_api`, `test_opportunity_radar_feed`). Adversarial probe (cold bind, clock alias, July-21 retrieve, qualifying mint, no-POST baseline) recorded below. Mixed discovery not re-run this round.

---

## Claim vs attack

| Claim / attack | Verdict |
|---|---|
| `POST /intelligence/ingest/news` on `UiApiHandler` admits already-fetched Finviz rows as EventV1 through `ObservationIngressRouter` | **CONFIRMED.** `server.py` `do_POST` calls `news_ingest.handle_news_ingest_post` after auth + 65k body limit. Handler bind-on-POST works cold (no pre-bind): `admitted_count=1`, router attached. `admit_news_article_event` → `router.dispatch` → store `put_event`. |
| Mint observational `OpportunityV1` on instrument + catalyst match | **CONFIRMED.** Detector `persist_observational_news_opportunity`; probe `reports quarterly earnings` + `AAPL` → `opportunity_count=1`, `feed_status=READY`, `identity_kind=OPPORTUNITY_V1`, `live_authority` metadata false. |
| Zero-qualifying stays EventV1 + `EMPTY` | **CONFIRMED.** `beats estimates` admits event, `opportunity_count=0`, summary `EMPTY` / `items=[]`. |
| ACK/WATCH still `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` | **CONFIRMED.** HTTP 403 in unit test; probe `apply_opportunity_ack` raises the same reason. `_is_live` mutation gate retained. |
| Publication vs receive clocks split | **CONFIRMED when `published_time` is known and ≠ retrieve.** `event_time_ns` / `provider_time_ns` = publication; `available_time_ns` / `received_time_ns` = retrieve. **Not an invariant:** equal clocks or missing publication collapse `event_time` onto `available_time`. |
| No auto-fetch | **CONFIRMED.** No UI caller. Bind does not fetch. Ingest returns `auto_fetch=false`. `run_ui_api` startup bind only attaches empty repo + router. |
| PIT / provenance | **RESIDUAL, not MUST-FIX.** See below. |
| Fixture ranking leak | **FALSIFIED (no leak).** Qualifying book is `AAPL` only. No `BIYA`/`BOXL`/`ES`. Current attention excludes `att-replay-context`. `include_ineligible` still absent. Live `_attention_rows` still `()`. |
| Mutation / Live authority | **FALSIFIED (still blocked).** Payload `live_authority=false`. No Live enable. |
| Clocks alias `available_time` | **CONFIRMED alias.** `received_time_ns` is always `available_time_ns` (both caller `retrieved_time`). `dispatch_time_ns` also aliases retrieve, not POST wall-clock. Does not falsify publication-vs-retrieve when publication is known. |
| Mid-session empirical contamination if merged | **Opt-in only.** No-POST baseline after bind: `as_of=UNAVAILABLE`, `EMPTY`, `items=0` — same as `91b07b4f` ranked book. A POST mutates `last_source_time_ns` / `as_of_time_ns`, labels `as_of_provenance=LIVE_RECEIVE`, and can mint `READY`. Do not merge mid-session. Restart without POST does not change today's book. |

---

## PIT / provenance residuals (follow-on)

1. **`available_time` aliases `received_time`.** Mapper sets both to retrieve. `DATA_CONTRACTS` says never infer one timestamp from another; this path treats them as the same retrieval instant. `IngressDispatchContext.dispatch_time_ns` defaults to that same retrieve ns.
2. **Caller retrieve is labeled live observation.** Provenance is `IngestionMode.LIVE_OBSERVED` + `AvailabilityConfidence.DIRECTLY_OBSERVED` even though the body is operator-posted already-fetched JSON. `HISTORICAL_RECONSTRUCTED` exists and was not used. After ingest, `as_of_provenance=LIVE_RECEIVE`.
3. **Caller can write July 21 as live as_of.** Probe `retrieved_time=2026-07-21T14:00:00Z` (no quote runtime) → display/`store.as_of_time()` = `2026-07-21T14:00:00.000000000Z`, provenance `LIVE_RECEIVE`, feed still `EMPTY`. This is not the silent fixture-cursor leak P13 closed; it requires POST. `PUBLICATION_AFTER_RETRIEVAL` is flagged, not fail-closed.
4. **Ranking as_of hijack.** After ingest, `build_ranked_rows` uses `store.as_of_time_ns` (retrieve) even if a quote receive clock exists for display. Residual if quotes and news retrieve diverge.
5. **Stale comment.** `tools/ui1/run_ui_api.py` still says “unused router bind. Not Finviz request-path EventV1 admission.” That is now false.

None of these reopen fixture cards, unlock ACK/WATCH, auto-fetch Finviz, or change the no-POST empirical book.

---

## Mid-session

Merge + restart **without** `POST /intelligence/ingest/news`: ranked OE unchanged (`UNAVAILABLE`/`EMPTY`).  
Merge + POST (even zero-qualifying): process-local clock + optional `OpportunityV1` mint. In-memory repo only. No frontend auto-caller found.

Same rule as P13b: **do not merge onto today's frozen RTH process.**

---

## Classification

**SAFE-TO-RETAIN-AFTER-REBASE.** Not **MUST-FIX-BEFORE-MERGE**.

Do not merge mid-session. After session close / rebase onto the approved base, this ingest candidate is retainable. No Live enable. Remaining documented gaps (auto-fetch, BUILD 09 `NEWS_EVENT`, Moomoo quotes as EventV1, mixed-discovery EMPTY) stay follow-ons.
