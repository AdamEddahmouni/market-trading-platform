# RTH 2026-09-15 live-integration test-gap matrix

| Field | Value |
|---|---|
| Document ID | `IMP-AUDIT-RTH-20260915-TEST-GAP` |
| Classification | `DIAGNOSIS` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` (coverage only) |
| Base | `origin/main` `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` |
| Lane | Isolated P9 — `diagnosis/test-gap-audit-20260915` |
| Date | `2026-09-15` |

Pre-RTH software validation passed because the pyramid (FAST / focused /
CHANGED / FULL, plus G15 Playwright) largely proves **fixture, unit, and
contract** behavior. Tuesday live integration failed on **composition
surfaces** that those suites either never boot, assert as fail-closed by
design, or lock as intended launcher/dev-server behavior.

This audit does **not** authorize weakening
`LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`, Live execution, or frozen FTEP
RTH artifacts. Existing passing tests that encode fail-closed Live safety
must stay.

## Why the pyramid could not see the live failures

| Pyramid layer | What it actually boots | What 2026-09-15 live used |
|---|---|---|
| Unit / contract | In-process builders, mocked SDK, `MemoryRouter`, injected `kline_rows` | Real OpenD, Vite `npm run dev`, launcher-selected interpreter |
| Integration (Python HTTP) | `run_ui_api` on `:8766` without Vite | Browser hits `:5173`, which proxies some paths to `:8766` |
| G15 Playwright e2e | `page.goto("/")` then **client-side** `history.pushState` (`navigateClient`) | Launcher opens `http://127.0.0.1:5173/discover` as a **hard navigation** |
| Path A / Item 9 CLI | Fixtures or injected rows; hop interpreter **rejects** `moomoo-api-test` on `PYTHONPATH` | Workstation launcher **prefers** `%USERPROFILE%\moomoo-api-test\.venv` for the API process |
| Prospective RTH-only | Software readiness (`SOFTWARE_READY_RTH_REQUIRED`); no live composition gate | Operator RTH session |

Missing test classes across the seven gaps: **full-stack (Vite+API hard
navigation)**, **provider sandbox (real OpenD page semantics)**, and
**prospective RTH-only honesty** (Live as-of and ranked-book labels). Unit
and contract coverage is dense where it encodes fail-closed Live OE, and
**absent** where composition would have failed closed or failed open.

## Gap matrix

| ID | Live failure (2026-09-15) | Why tests passed | Existing tests — do not weaken | Missing classes | Exact missing tests | Owner |
|---|---|---|---|---|---|---|
| G1 | Live provider → Opportunity Engine unwired | OE is tested on replay fixtures; Live HTTP returns empty UNAVAILABLE; Path A hop is a separate CLI | `tests/ui1/test_opportunity_api.py::test_live_mode_returns_unavailable_empty_queue`; Path A live-forbidden tests | integration, full-stack, prospective RTH-only | `tests/ui1/test_live_provider_oe_composition_honesty.py`; optional later wiring suite **after** a dedicated increment | **P2** |
| G2 | `LIVE_OBSERVATIONAL` ranked book empty / UNAVAILABLE | Tests **assert** that fail-closed design | Same Live OE tests + `tests/ui1/test_opportunity_radar_feed.py::test_live_detail_and_ack_fail_closed` | contract (honesty label), prospective RTH-only | `tests/ui1/test_live_ranked_book_unavailable_honesty.py`; UI banner copy test — **must keep empty items** | **P2** (honesty only; do not add a test that requires live ranked rows) |
| G3 | Fixture as_of 2026-07-21 shown as now | Context tests only require a truthy `as_of_time`; Live fallback uses `ReplayStore.as_of_time()` when no quote | `tests/ui1/test_ui_api.py::test_context_replay_mode`; UI schema fixtures dated `2026-07-21` | unit, contract, prospective RTH-only | live as_of tests **P1 is adding** — do not collide | **P1** |
| G4 | Launcher prefers `moomoo-api-test` | Unit test **locks** override → moomoo-test → repo `.venv` | `tests/platform/test_local_launcher.py::test_backend_python_precedence_is_override_then_moomoo_then_repo` | unit (precedence vs hop interpreter), integration | launcher tests **P3 is adding** — do not collide with P3 edits to `test_local_launcher.py` | **P3** |
| G5 | `/discover` advertised into Vite API proxy | Vitest uses `MemoryRouter`; e2e never hard-navigates `/discover`; launcher test **asserts** start URL `/discover` | `tests/platform/test_local_launcher.py` start URL; `ui/src/App.test.tsx` MemoryRouter `/discover`; e2e `navigateClient` | unit (vite config HTML bypass), full-stack, e2e hard navigation | `tests/platform/test_vite_discover_spa_html_bypass.py`; `e2e/tests/discover-hard-navigation.spec.ts` | **P4** |
| G6 | OpenD `request_history_kline` oldest page | Item 9 tests inject `kline_rows=`; transport discards `_page`; no SDK mock of page order | `tests/platform/test_bar_ohlcv_prospective_proof.py` (injected rows); `tests/platform/test_bar_ohlcv_comparator_experiment.py` | unit (transport page_key / newest-first), provider sandbox | **Do not add** `test_opend_history_kline_1m.py` (other lane). Suggested: `tests/providers/test_opend_kline_page_direction.py` | **Item 9 / OpenD kline lane** (not P9) |
| G7 | WATCH / DISMISS unreachable on Discover radar | Paper NOW unit tests mock `useOpportunityAckMutation`; Discover does not pass `onAck`/`paperAccountId`; Live API fail-closes acks | `tests/ui1/test_opportunity_api.py` Paper dismiss round-trip; `ui/src/components/now/OpportunityReviewCard.test.tsx`; Live ack fail-closed | integration (HTTP from UI), full-stack, acceptance | watch-dismiss acceptance **P5 is adding** — do not collide | **P5** |

## Per-gap evidence

### G1 — Live provider → OE unwired

**Observed mechanism.** `ObservationalLaneRuntime` / OpenD capture can feed
quotes, books, and ingress **store** consumers. The operator ranked queue is
`build_opportunities_summary_payload`, which returns immediately when
`_is_live(store)`:

- `feed_status=UNAVAILABLE`
- `reason=LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`
- `items=[]`

Path A prospective hop is a **CLI composer**, not the UI ranked book.
`build_production_observation_ingress_router` attaches an OE **evidence**
sink; PROGRAM_STATUS already records that default OpenD capture still bypasses
ingress unless `ingress_router=` is passed. None of that is a Live ranked-book
wire.

**Why tests passed.** Live tests encode the fail-closed HTTP contract. Replay
OE tests seed `InMemoryIntelligenceRepository` on `FIXTURE_REPLAY`. No suite
requires a live Moomoo quote to become a ranked `OpportunityV1` row.

**Do not weaken.** Keep Live UNAVAILABLE / empty items / fail-closed detail and
ack. A future wiring increment must add tests **in addition to** these gates,
not replace them.

**Missing tests (P2).**

| Class | Suggested name | Assertion |
|---|---|---|
| contract | `tests/ui1/test_live_provider_oe_composition_honesty.py` | Live summary stays UNAVAILABLE even when a fake live quote exists on `get_live_runtime` |
| integration | same file, HTTP `/opportunities/summary` with `IMP_LIVE_OBSERVATIONAL=1` | JSON reason remains `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` |
| prospective RTH-only | operator receipt / honesty check | Ranked book UNAVAILABLE is expected until a **named** wiring increment; not “no opportunities in the market” |

### G2 — LIVE_OBSERVATIONAL ranked book fail-closed by design/test

**This is not a missing fail-closed gate.** It is the same mechanism as G1,
surfaced as an empty “Ranked opportunity queue” on `LiveDiscoverPage`.

`OpportunityRadarCockpit` always queries `/opportunities/summary`. Live mode
returns zero items. Vitest Discover pages mock that query to `{ items: [] }`.
G15 e2e never opens Discover in Live with a live feed.

**Missing tests (P2, honesty only).** UI must show `feed_status` /
`reason` (OpportunityFeedStatusBanner) rather than a silent empty table that
looks like “no setups.” Do **not** add a test that expects ranked live rows
without a product increment that also preserves Live-observational-only
(no execution).

### G3 — Fixture as_of July 21 shown as now — owner P1

**Observed mechanism.** Replay bars are the admitted BIYA JSONL
(`source_timestamp` / capture `2026-07-21T21:00:34Z`; session bars from
`2026-07-16`). `ReplayStore.as_of_time()` is `_epoch_ns_to_iso(prediction_cutoff())`
from the current fixture bar.

`build_as_of_context` switches to live quote `received_ns` only when
`data_mode == LIVE_OBSERVATIONAL` **and** `get_live_runtime(create=False)` is
non-None **and** `quote_for(focus)` is non-None. Otherwise it keeps
`store.as_of_time()`. Launcher defaults `IMP_LIVE_OBSERVATIONAL=1`, so the
API labels LIVE while as_of can remain the July 21 fixture clock.

`test_context_replay_mode` only asserts `as_of_time` is truthy.

**Missing tests (P1 owns — P9 does not add files).**

| Class | Intent |
|---|---|
| unit | `LIVE_OBSERVATIONAL` + no runtime/quote must not present fixture `2026-07-21` as operator “now” (UNAVAILABLE / explicit fixture clock / live receive time — P1 chooses the honest contract **without** fabricating a tick) |
| contract | `/context` as_of under live env without a quote is distinguishable from replay |
| prospective RTH-only | with a real quote, as_of tracks quote receive time, not BIYA fixture |

Collision: do not add “live as_of” tests P1 is adding.

### G4 — Launcher prefers moomoo-api-test — owner P3

**Observed mechanism.** `select_backend_python` order is override env,
then `%USERPROFILE%\moomoo-api-test\.venv\Scripts\python.exe` if that file
exists, then repo `.venv`. `START_PLATFORM.cmd` uses repo `.venv` only to
**invoke** the launcher; the spawned API process uses `select_backend_python`.
`tools/ui1/restart_ui_api.ps1` also prefers the moomoo-test interpreter.

Hop policy is the opposite: `opend_hop_interpreter.py` refuses
`moomoo-api-test` on `PYTHONPATH`; `tests/providers/test_opend_hop_interpreter.py`
asserts that.

**Why tests passed.**
`test_backend_python_precedence_is_override_then_moomoo_then_repo` **requires**
the moomoo-test preference. That is a locked composition bug relative to hop
interpreter policy, not an untested path.

**Missing tests (P3 owns).** Interpreter identity for the API child must match
IMP `.venv` / vendor `moomoo-api` in that venv; mixing `moomoo-api-test` must
fail closed or be non-default. Do not collide with P3’s launcher test files.

**Do not weaken** hop-interpreter rejection of `moomoo-api-test`.

### G5 — `/discover` advertised into Vite API proxy — owner P4

**Observed mechanism.**

- SPA route: `App.tsx` `path="/discover"`.
- API routes: `/discover/screens`, `/discover/run`, `/discover/mixed`, … — **no**
  `GET /discover`.
- `ui/vite.config.ts` proxies `"/discover": apiTarget` (prefix).
- `/workspace` has an HTML `bypass` for `GET` + `Accept: text/html`.
- `/discover` has **no** equivalent bypass.
- `DISCOVER_URL = http://127.0.0.1:5173/discover`; launcher test asserts
  `open_browser` receives that URL.

Hard refresh or first paint of `/discover` is proxied to the API and 404s.
In-app `<Link to="/discover">` and Playwright `navigateClient` stay inside
the SPA and pass.

**Missing tests (P4).**

| Class | Suggested name | Assertion |
|---|---|---|
| unit | `tests/platform/test_vite_discover_spa_html_bypass.py` | Vite proxy for `/discover` either is prefix-safe (`/discover/mixed` still proxied) **or** HTML GET `/discover` bypasses like `/workspace` |
| full-stack / e2e | `e2e/tests/discover-hard-navigation.spec.ts` | `page.goto("http://127.0.0.1:5173/discover")` returns the Opportunity Radar document, not API JSON/404 |
| contract | launcher start URL vs Vite bypass | If launcher keeps `/discover`, Vite must serve the SPA for that URL |

Do not steal P4 production Vite edits; this row only specifies the tests.

### G6 — OpenD history kline oldest page — Item 9 / OpenD lane

**Observed mechanism.** `fetch_history_kline_1m` calls
`ctx.request_history_kline(..., start=None, end=None, max_count=max_count)`
and binds the page token to `_page` (discarded). Moomoo OpenD returns the
**oldest** page first when start/end are omitted; `page_req_key` is required
to walk toward now. Item 9 prospective 1m proof then normalizes whatever
rows came back.

`tools/moomoo/probe.py` records `page_req_key_present` but does not fail the
prospective proof if the page is historical.

**Why tests passed.** `load_moomoo_opend_kline_bars(..., kline_rows=)` never
calls the transport. There is **no** test module for
`fetch_history_kline_1m` page direction on `origin/main`.

**Missing tests (kline owner).**

| Class | Suggested name | Assertion |
|---|---|---|
| unit | `tests/providers/test_opend_kline_page_direction.py` | Fake SDK whose first page is oldest must not be treated as the latest `max_count` bars; `page_req_key` must be consumed or the fetch fail-closed as `HISTORICAL_PAGE_NOT_PROSPECTIVE` |
| provider sandbox | gated OpenD loopback test | During RTH, returned bars’ last `available_time` is within the poll window, not years-old history |

**Collision:** do **not** add `tests/providers/test_opend_history_kline_1m.py`
(or the same basename under `tests/platform/`).

### G7 — WATCH / DISMISS unreachable — owner P5

**Observed mechanism.**

API: `POST /opportunities/{id}/watch|dismiss|review` exists.
`apply_opportunity_ack` requires Paper `INTERNAL_SIMULATION` and fail-closes
Live.

UI client: `postOpportunityAck` / `useOpportunityAckMutation` exist.
Buttons render only if `paperAccountId && onAck && canWatch`.
`canWatch` needs `paperActions && !readOnly`.

`PaperNowPage` wires `paperAccountId` + `onAck`.
`PaperDiscoverPage` sets `paperActions` **without** `paperAccountId` or `onAck`.
`LiveDiscoverPage` is `readOnly` and does not wire acks (correct for Live).

Operator Discover radar therefore never issues watch/dismiss. Paper NOW unit
tests mock the mutation hook (`App.test.tsx`, `PaperNowPage.test.tsx`).
OpportunityReviewCard tests prove the buttons **when props are passed**.

**Missing tests (P5 owns).** Acceptance that Paper Discover (or the intended
operator surface) posts `/opportunities/{id}/watch` and `/dismiss` against the
real API; Live remains fail-closed. Do not collide with P5 acceptance files.

## Test-class coverage vs the seven gaps

| Class | G1 | G2 | G3 | G4 | G5 | G6 | G7 |
|---|---|---|---|---|---|---|---|
| unit | present (fail-closed) | present (fail-closed) | missing (P1) | present but locks wrong default (P3) | missing (P4) | missing (kline lane) | present for card props only |
| contract | present (empty Live feed) | present | missing (P1) | hop vs launcher contradict | missing (P4) | missing | Paper dismiss HTTP in-process |
| integration | missing honesty-with-live-quote | n/a (keep fail-closed) | missing (P1) | missing (P3) | missing | missing | missing Discover wiring |
| full-stack | missing | missing honesty | missing | missing | missing (Vite hard nav) | n/a | missing |
| provider sandbox | missing (optional) | n/a | n/a | n/a | n/a | missing (OpenD page) | n/a |
| prospective RTH-only | missing honesty | missing honesty | missing (P1) | n/a | n/a | missing | P5 acceptance |

## Lane ownership (do not steal production)

| Lane | Owns | P9 must not add |
|---|---|---|
| P1 | Live as_of honesty tests | any live as_of test file |
| P2 | Provider→OE composition honesty; ranked-book UNAVAILABLE labeling | production OE wiring; do not delete Live fail-closed tests |
| P3 | Launcher interpreter selection | launcher test files P3 is adding |
| P4 | Vite `/discover` SPA HTML bypass + hard-navigation e2e | Vite/launcher production patches |
| P5 | Watch/Dismiss acceptance | watch-dismiss acceptance files |
| Item 9 / OpenD kline | History kline page direction | `test_opend_history_kline_1m.py` |
| P9 (this lane) | This audit only | production behavior, frozen RTH, other lanes’ new tests |

## Constraints (unchanged)

- Do not weaken `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` or Live execution blocks.
- Do not edit frozen FTEP RTH manifests or empirical receipts.
- Do not merge this diagnosis into `main` as a product fix.
- Do not copy uncommitted production files from P1–P4 / P2 / P3.
- Fixture success remains fixture success (doctrine evidence ladder).
