# Latency instrumentation v1 — coverage

Evidence class for controlled tests: SOFTWARE_CONTROLLED / FIXTURE.
Never label this lane as prospective, live market, or campaign runtime.

## Clock domains

| Domain | Source | Use |
|---|---|---|
| **Wall** | monotonic_wall_ns() | Absolute processing timestamps; may be compared to EventV1 / eligibility wall clocks when both are wall-domain. |
| **Monotonic** | time.perf_counter_ns() | Software stage *durations* only. Do not subtract from wall or eligibility clocks. |

Units: nanoseconds (*_ns). Missing stage → None / status NOT_OBSERVED. Never estimate or fabricate.

## Information-eligibility clocks (not software latency)

Captured for correlation honesty; **not** processing latency:

- source_publication — provider publication time (article / EventV1.event_time_ns)
- provider_retrieved — client/provider retrieve time (available_time / retrieved_time)
- imp_server_received — server stamp at ingest (received_time_ns)

## Software processing stages (this lane)

| Stage id | Meaning |
|---|---|
| normalization_completed | Finviz export item → NewsArticleEvent finished |
| pit_completed | PIT validate + NewsPipeline accept finished |
| detector_started | observational_news_detector_consumer enter (news article) |
| detector_completed | Detector consumer exit after mint attempt |
| opportunity_persisted | put_opportunity returned for observational news |
| rank_generated | rank_review_rows / ranked book build finished for correlated opportunities |
| api_payload_generated | GET /opportunities/summary payload dict finished |

## Correlation identity

Primary: event_id (EventV1). Secondary: opportunity_id when minted (`newsopp-<event_id>`).
Rank/API stamps attach to traces whose opportunity_id appears in the ranked book.

## Path coverage (implemented)

Finviz news JSON → POST /intelligence/ingest/news → normalize → PIT → EventV1 →
ingress dispatch → observational_news_detector_consumer → OpportunityV1 persist →
rank_review_rows → build_opportunities_summary_payload.

## Out of scope / UNAVAILABLE (other lane)

- ui_received
- ui_first_visible
- operator_interaction

Do not invent ForecastV1 or DetectionFrame. Does not change qualification, Live/Paper authority, Item 9, or
news_event_build09 (INACTIVE).

## Overhead

Instrumentation runs only when a collector is bound (ContextVar or store attribute).
No background threads. Unbound hot path still performs one ContextVar get plus an optional
store-attribute check; it does **not** capture stamps or mark stages. When a collector is
bound, stamp capture and mark_stage do real work on the request path — this lane does not
claim zero overhead.
