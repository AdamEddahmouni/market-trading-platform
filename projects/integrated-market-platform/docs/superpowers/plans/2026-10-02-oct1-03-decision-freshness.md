# OCT1-03 decision freshness implementation plan

Owner: Codex, serial implementation. Worktree: `.worktrees/oct1-03-decision-freshness`.
Branch: `codex/oct1-03-decision-freshness`. Base: `cb180e148241723e81557228f590b954ed8f8a77`.
Evidence class: SOFTWARE_CONTROLLED. No empirical provider proof or trading authority.

Goal: expose clock-aware, source-aware freshness and enforce per-capability decision eligibility.
Architecture: domain services own facts and thresholds; a pure shared evaluator and Screener projection compose existing payloads without acquisition; React renders structured authority.
Tech: stdlib Python, React, existing Zod/Query contracts.

## Audit before implementation

| Family | Existing semantics / gap | Policy authority |
|---|---|---|
| Equity/ETF L1 | LIVE/DELAYED/STALE; field as_of_ns aliases availability; event/receive differ | screener_projections: event 60s, receipt 5s |
| Rows | Finviz SNAPSHOT fetch clock; OpenD snapshot provider update clock; cache TTL not observation proof | screener_snapshot; unknown cadence for Finviz market observations |
| Fundamentals | Finviz export metadata; report clock absent | UNKNOWN_POLICY; reference only when source clock is known |
| Bars/charts | completed bar end, receipt, session; freshness ignores aggregate timeframe | current_bars: 3m tolerance, closed max 4d |
| Order Flow/CVD | latest event/receive; feed silence 30s rather than symbol silence | screener_specialist FEED_SILENT_SECONDS |
| Depth | FRESH/STALE/INVALID, provider-specific receipt TTL, session | order_book FreshnessPolicy; live_config |
| Options | SNAPSHOT; fetch age; provider as_of null; latest trade and underlying separate | options refresh TTL, stale 2 refresh periods |
| Futures | dated contract validity independent from quote LIVE/STALE | futures_context 15s |
| Cross-Asset | independent node clocks; comparison exact windows and 60s cutoff | connectivity compare_direction; enrich each node |
| Bonds/rates | PUBLICATION_BASED; terms, auction, operation, curve and retrieval clocks; no live price | source-specific dates; cadence unknown, reference only |
| Squeeze | per-metric PUBLICATION_CURRENT/SNAPSHOT, settlement/list/provider clocks; lending absent | squeeze and squeeze_sources publication authorities |
| News/why-moving | publication, first retrieval, relevance window; some fallback retrieval aliases | news and preview movement windows; publication must be explicit |

## Design choices

Keep existing domain state vocabulary. Normalize delivery separately from CURRENT/STALE/UNKNOWN/UNAVAILABLE/SESSION_CLOSED; policy version and basis accompany every evaluation. ADMISSIBLE is capability and intended-use specific. Unknown policy cannot assert current-market eligibility; known publication time may be DEGRADED reference context without an invented TTL. Maturity/expiry/issue/settlement terms are never observation clocks. Stale critical evidence is BLOCKED and excluded by the deterministic consumer helper; reference use remains a separate vector.

## Implementation sequence

- [x] Regression tests for canonical evaluator, clocks, publication/reference, bar timeframe and mixed-lane filtering; observe RED.
- [x] Shared evaluator and pure response projection; preserve independent clocks and known thresholds; server response boundary integration.
- [x] Correct selected-symbol microstructure aging, L1 clock metadata and timeframe-aware bars; freshness in directional comparison.
- [x] Shared accessible indicator and API schema fields, relevant panels, preview, rows and bond date labels; UI tests.
- [x] Focused backend/UI checks, full closure, typecheck/build/budget, controlled browser acceptance, performance measurement.
- [ ] Review complete diff, explicit staging/commit, PR/checks/merge, verify origin/main, documentation and Notion closeout. Stop before OCT1-04.

## Validation / closeout

The [canonical freshness contract](../../architecture/SCREENER_DECISION_FRESHNESS.md) records the implementation and consumer gate. Regression coverage is 18 new backend cases and 10 new UI cases. Original RED runs failed on the missing shared modules/components before implementation.

Final focused results: 44/44 freshness + crypto, 125/125 adjacent S3/S4/connectivity backend, 259/259 Screener UI/API (21 files), and 17/17 indicator/connectivity UI after the final graph-expiry change. Complete UI: 1268/1268, 166 files, one worker, 388.21s. Earlier concurrent UI runs had App timing failures (4 then 5); isolated App 76/76 and complete single-worker rerun closed them. Lint (Python compile + TypeScript) passed. Final production build: 15.62s; budget passed, initial 99.70 KiB gzip (+0.01 KiB versus OCT1-02); largest Vela lazy chunk unchanged at 246.08 KiB gzip. TypeScript passed again after graph expiry.

Controlled real-component browser acceptance uses installed Edge, HTTP fixtures, real ScreenerPage, QueryClient, dock panels and preview. SOFTWARE_CONTROLLED, 15 assertions, zero page errors: current quote source/as-of, stale flow, independent CVD, Options SNAPSHOT with distinct fetch clocks, independent graph nodes, delayed quote, unavailable withdrawal, instrument switch, preview reopen, Maturity identity label, separate publication/observation date, Rates, and late old-symbol response isolation. Screenshots and exact logs are retained in `.local/oct1-03-browser-*`; synthetic fixture text is not empirical evidence.

Bounded existing provider diagnostics: OpenD loopback REACHABLE, observational gate DISABLED and credential state MISSING; IBKR transport UNAVAILABLE/manual session required; Finviz credential MISSING/gate DISABLED. Quote/Options publication empirical verification NOT_EXECUTED. No gates enabled or credentials configured. The FTEP gap report is diagnostic only; no campaign was changed.

Projection benchmark (100 measured iterations after 10 warmups, existing controlled fields): 80 rows p50 1.223ms/p95 2.172ms, JSON 50,361 -> 110,544 bytes; 500 rows p50 7.967ms/p95 9.723ms, JSON 312,861 -> 688,884 bytes. This measures the added pure projection, not live end-to-end HTTP latency. No provider requests or polling added; equal source/state/clock families share a status, with explicit covered_fields. Metadata increases uncompressed payload size; no transport compression claim is made.

Earlier restricted FULL: 7798 tests, 55 skips, 2 failures and 22 errors, 475.342s. Two regressions were corrected (feed-silence reason preservation and connectivity validity); the crypto fixture clock was corrected to precede receive time. Remaining restricted errors included SDK log-directory permission denial and Windows subprocess/file cleanup. Two normal-access console attempts were interrupted at 210 tests without failures. Independent-process-group FULL completed: **7801 tests, 7748 passes, 53 skips, 0 failures, 0 errors, 721.592226s**, two workers. Telemetry **SEVERE_REGRESSION**, baseline median 198.882s, +522.710226s / +262.824%; slowest suites intelligence 224.120s, platform 134.895s, software_fullstack_acceptance 110.326s. Three final missing-price/partial-book/row-event regression cases were added after this FULL loaded Platform and passed in the final 44-test focused run alongside all 125 adjacent backend tests. Earlier interruptions are not passes.

Unknown provider cadence remains an explicit limitation, not an acquisition task. No AI Screener, OCT1-04, provider setup or execution authority was added. Integration/check/SHA and Notion ledger are recorded in the PR and final task closeout.

Documentation links: 285 governance Markdown files checked, pass. Final primary-owner diff review performed; only OCT1-03 source/UI/tests/docs are staged. Generated validation performance/corpus artifacts are excluded.
