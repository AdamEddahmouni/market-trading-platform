# Mixed Live Screener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/discover` open on a deduplicated mixed Finviz queue whose top quota-safe candidates receive read-only Moomoo L1 enrichment with explicit freshness, provenance, and failure states.

**Architecture:** A pure discovery-domain aggregator owns lane assignment, merging, and deterministic attention ranking. A provider-neutral enrichment boundary wraps the existing Moomoo runtime and reconciles only the screener consumer's `BASIC_QUOTE` references. A stateful projection service coordinates single-flight Finviz refreshes and read-only live polls, while the React page renders the stable provider-neutral payload and retains the existing single-screen diagnostics.

**Tech Stack:** CPython 3.11 standard library, `unittest`, stdlib threaded HTTP API, React 18, TypeScript 5.6, Vitest/Testing Library, existing IMP CSS tokens.

## Global Constraints

- `candidate_role` is always `INVESTIGATE`; no discovery path creates an order intent, paper order, or broker order.
- Mixed auto-subscription uses only `BASIC_QUOTE`, consumer `discover-live-screener`, priority `BACKGROUND_RESEARCH`, and default cap `12` from `IMP_DISCOVERY_LIVE_CANDIDATES`.
- `GET /discover/mixed` never calls Finviz, creates a runtime, or changes subscriptions.
- Missing observations remain `null`; status is one of `LIVE`, `DELAYED`, `SNAPSHOT`, `STALE`, or `UNAVAILABLE`.
- Browser polling is 3 seconds while visible; Finviz refresh is 120 seconds; both pause while hidden.
- Preserve `/discover/screens`, `/discover/run`, and `/discover/promote-to-live-analysis` behavior.
- Use the repository-local CPython 3.11 environment and the manifest validation ladder.

## File map

- Create `src/market_platform_foundation/discovery/mixed.py`: lane mapping, aggregate model, merge gates, scoring, and deterministic ordering.
- Create `src/market_platform_foundation/discovery/live_enrichment.py`: normalized market record, enricher protocol, Moomoo quote adapter, and screener-only subscription reconciliation.
- Create `src/market_platform_foundation/ui_api/mixed_discovery_projections.py`: latest-snapshot state, Finviz/capture fallback orchestration, single-flight refresh, and read-only projection.
- Modify `src/market_platform_foundation/market_data/subscription_manager.py`: name the existing background priority `BACKGROUND_RESEARCH` while retaining `BACKGROUND_EXPLORE` as an alias.
- Modify `src/market_platform_foundation/ui_api/server.py`: add mixed GET and POST routes.
- Modify `src/market_platform_foundation/discovery/__init__.py`: export the mixed-domain contract.
- Create `tests/platform/test_mixed_discovery.py`: offline domain, adapter, fallback, single-flight, and API invariants.
- Create `ui/src/components/DiscoverPage.test.tsx`: default mode, filters, statuses, polling visibility, and promotion behavior.
- Modify `ui/src/components/DiscoverPage.tsx`: Mixed Live and Single Screen modes.
- Modify `ui/src/styles/layout.css`: operator-board layout, market-status rail, evidence disclosure, and responsive rows.
- Modify `ui/vite.config.ts`: proxy `/discover` during local development.

---

### Task 1: Mixed candidate domain and deterministic attention ranking

**Files:**
- Create: `tests/platform/test_mixed_discovery.py`
- Create: `src/market_platform_foundation/discovery/mixed.py`
- Modify: `src/market_platform_foundation/discovery/__init__.py`

**Interfaces:**
- Consumes: `CandidateSet.to_dict()` payloads from the existing Finviz discovery engine or capture loader.
- Produces: `LANES_BY_SCREEN`, `MixedCandidate`, and `aggregate_candidate_sets(candidate_sets, *, now_ns, market_by_symbol=None) -> list[MixedCandidate]`.

- [x] **Step 1: Write failing aggregate tests**

Add fixtures that build two candidate-set dictionaries for the same symbol from `SHORT_SQUEEZE_DISCOVERY` and `UNUSUAL_VOLUME_DISCOVERY`, then assert:

```python
mixed = aggregate_candidate_sets([older, newer], now_ns=2_000_000_000)
self.assertEqual(len(mixed), 1)
self.assertEqual(mixed[0].instrument_id, "AAPL")
self.assertEqual(mixed[0].lanes, ["MOMENTUM", "SQUEEZE"])
self.assertEqual(mixed[0].metrics["rel_volume"], 4.0)  # newest observation wins
self.assertEqual(len(mixed[0].provenance), 2)
self.assertEqual(mixed[0].candidate_role, "INVESTIGATE")
```

Add separate tests for invalid/non-US symbols, non-finite/negative prices, candidates without reasons, `None` metrics not becoming zero, component caps (`45/20/20/15`), quality penalties, and tie-breaking by newest observation then screen count then symbol.

- [x] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m unittest tests.platform.test_mixed_discovery.MixedDomainTests -v`

Expected: import failure for `market_platform_foundation.discovery.mixed`.

- [x] **Step 3: Implement the pure domain model**

Define the exact lane map from the approved spec and these serializable models:

```python
@dataclass(slots=True)
class MixedCandidate:
    instrument_id: str
    lanes: list[str]
    screen_matches: list[str]
    matched_reasons: list[str]
    metrics: dict[str, Any]
    discovery_as_of: str
    available_time_ns: int
    quality: str
    provenance: list[dict[str, Any]]
    attention_score: float = 0.0
    attention_components: dict[str, float] = field(default_factory=dict)
    ranking_reasons: list[str] = field(default_factory=list)
    market: dict[str, Any] | None = None
    queue_rank: int | None = None
    candidate_role: str = "INVESTIGATE"

    def to_dict(self) -> dict[str, Any]: ...
```

Implement finite-number helpers; merge only canonical symbols matching `^[A-Z][A-Z0-9.-]{0,9}$`; union sorted lanes/screens/reasons; select each metric from the contributing candidate with greatest `available_time_ns`; keep all provenance. Compute capped setup/freshness/liquidity/live components and explicit penalties, then sort by `(-attention_score, -available_time_ns, -len(screen_matches), instrument_id)` and assign one-based `queue_rank`.

- [x] **Step 4: Verify GREEN and changed validation**

Run the Task 1 unittest command, then `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py changed`.

Expected: all Task 1 tests pass and changed validation is green.

- [x] **Step 5: Commit the domain slice**

```powershell
git add src/market_platform_foundation/discovery/mixed.py src/market_platform_foundation/discovery/__init__.py tests/platform/test_mixed_discovery.py
git commit -m "feat(discovery): aggregate mixed screener candidates"
```

### Task 2: Provider-neutral Moomoo enrichment and quota-safe reconciliation

**Files:**
- Modify: `tests/platform/test_mixed_discovery.py`
- Create: `src/market_platform_foundation/discovery/live_enrichment.py`
- Modify: `src/market_platform_foundation/market_data/subscription_manager.py`

**Interfaces:**
- Consumes: ranked `MixedCandidate` instances and optional `LiveObservationalRuntime` compatible objects.
- Produces: `MarketCandidateEnricher` protocol and `MoomooCandidateEnricher(runtime, *, cap=12, stale_after_ms=5000)` with `reconcile(candidates)`, `enrich(candidates)`, and `health()`.

- [x] **Step 1: Write failing adapter tests**

Use a real `LiveSubscriptionManager(max_quota=...)` inside a lightweight fake runtime and real `ObservationalStateStore` quotes. Assert that reconciliation:

```python
enricher.reconcile(ranked_candidates)
self.assertEqual(fake_runtime.subscribe_calls[0]["capabilities"], ["BASIC_QUOTE"])
self.assertEqual(fake_runtime.subscribe_calls[0]["consumer_id"], "discover-live-screener")
self.assertEqual(fake_runtime.subscribe_calls[0]["priority"], int(SubscriptionPriority.BACKGROUND_RESEARCH))
```

Also assert cap/quota bounding; incumbent retention within three ranks; release removes only `discover-live-screener`; no runtime returns `UNAVAILABLE`; no quote returns `SNAPSHOT/AWAITING_FIRST_EVENT`; fresh quote returns `LIVE`; >5-second quote returns `STALE`; crossed bid/ask yields `spread_pct=None`, `DEGRADED`, `CROSSED_MARKET`; and configuration parses a positive integer cap with invalid values falling back to `12`.

- [x] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m unittest tests.platform.test_mixed_discovery.MoomooEnrichmentTests -v`

Expected: import failure for `discovery.live_enrichment` or missing `BACKGROUND_RESEARCH`.

- [x] **Step 3: Implement the contract and adapter**

Add the priority alias without renumbering existing priorities:

```python
class SubscriptionPriority(IntEnum):
    ACTIVE_EXECUTION_CONTEXT = 0
    ACTIVE_WORKSPACE = 1
    PINNED_WATCHLIST = 2
    BACKGROUND_RESEARCH = 3
    BACKGROUND_EXPLORE = BACKGROUND_RESEARCH
```

Define:

```python
class MarketCandidateEnricher(Protocol):
    def reconcile(self, candidates: Sequence[MixedCandidate]) -> list[dict[str, Any]]: ...
    def enrich(self, candidates: Sequence[MixedCandidate]) -> dict[str, dict[str, Any]]: ...
    def health(self) -> dict[str, Any]: ...
```

Track only symbols successfully acquired by this instance. Choose the top `cap`, retaining incumbents whose new rank is at most `cap + 3`; ask the existing manager for remaining quota; call runtime `subscribe`/`unsubscribe` only during `reconcile`. `enrich` reads `runtime.state.quote_for` and `freshness_ms`, validates finite/non-crossed fields, and emits the provider-neutral keys from the spec without zeros for missing fields.

- [x] **Step 4: Verify GREEN and live-boundary offline validation**

Run the Task 2 unittest command, then `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py changed`.

Expected: adapter tests pass; offline validation remains green. Do not run the opt-in live suite without configured provider authority.

- [x] **Step 5: Commit the enrichment slice**

```powershell
git add src/market_platform_foundation/discovery/live_enrichment.py src/market_platform_foundation/market_data/subscription_manager.py tests/platform/test_mixed_discovery.py
git commit -m "feat(discovery): enrich candidates with moomoo quotes"
```

### Task 3: Single-flight mixed projection, capture fallback, and HTTP routes

**Files:**
- Modify: `tests/platform/test_mixed_discovery.py`
- Create: `src/market_platform_foundation/ui_api/mixed_discovery_projections.py`
- Modify: `src/market_platform_foundation/ui_api/server.py`

**Interfaces:**
- Consumes: injectable `engine_factory`, `capture_loader`, `runtime_getter`, and `MoomooCandidateEnricher`.
- Produces: singleton `MixedDiscoveryService`; `build_mixed_discover_payload() -> dict[str, Any]`; `refresh_mixed_discovery(screen_ids=None) -> dict[str, Any]`.

- [x] **Step 1: Write failing service and route tests**

Assert an eight-screen refresh deduplicates symbols, records per-screen `PASS/FALLBACK/UNAVAILABLE`, uses the latest capture after a screen exception, preserves successful screens when one fails, returns `available=False` only when every screen lacks live/captured candidates, and never changes `candidate_role`.

For read-only behavior, inject spies and assert:

```python
payload = service.read()
self.assertEqual(engine.calls, [])
self.assertEqual(runtime_getter.calls, [{"create": False}])
self.assertEqual(fake_runtime.subscribe_calls, [])
self.assertEqual(fake_runtime.unsubscribe_calls, [])
```

Use a blocking fake engine from two threads to assert the second refresh returns the current result with `refresh_in_progress=True`. Start `ThreadingHTTPServer` with `UiApiHandler` and assert `GET /discover/mixed` and `POST /discover/mixed/refresh` return the schema while existing routes still respond.

- [x] **Step 2: Verify RED**

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m unittest tests.platform.test_mixed_discovery.MixedProjectionTests tests.platform.test_mixed_discovery.MixedRouteTests -v`

Expected: missing projection functions and 404 mixed routes.

- [x] **Step 3: Implement service and routes**

Use a non-blocking `threading.Lock` around refresh. On success, cache raw candidate-set dictionaries, reconcile subscriptions once, then return a projection. On per-screen exception, load its latest capture and record the failure reason. On process start/read with no memory snapshot, reconstruct from all latest captures. `read()` calls `get_live_runtime(create=False)`, never `DiscoveryEngine`, then attaches current enrichment and reruns attention ranking.

Return the stable envelope:

```python
{
    "available": bool(candidates),
    "mode": "SEMI_LIVE",
    "candidate_role": "INVESTIGATE",
    "generated_at": utc_iso,
    "discovery_as_of": newest_received_at,
    "refresh_in_progress": bool,
    "refresh_interval_seconds": 120,
    "poll_interval_seconds": 3,
    "provider_health": [...],
    "lane_counts": {...},
    "screen_outcomes": [...],
    "candidates": [...],
}
```

Validate optional POST `screen_ids` as a list of known screen ids; reject unknown ids through the existing `ValueError -> 400` path. Add the mixed routes before the generic not-found responses.

- [x] **Step 4: Verify GREEN and UI-domain validation**

Run the Task 3 unittest command, then `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py changed` and `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py domain ui`.

Expected: service/routes pass; changed and UI-domain validators pass.

- [x] **Step 5: Commit the API slice**

```powershell
git add src/market_platform_foundation/ui_api/mixed_discovery_projections.py src/market_platform_foundation/ui_api/server.py tests/platform/test_mixed_discovery.py
git commit -m "feat(api): expose mixed live discovery queue"
```

### Task 4: Mixed Live operator board and polling lifecycle

**Files:**
- Create: `ui/src/components/DiscoverPage.test.tsx`
- Modify: `ui/src/components/DiscoverPage.tsx`
- Modify: `ui/src/styles/layout.css`
- Modify: `ui/vite.config.ts`

**Interfaces:**
- Consumes: the mixed envelope from Task 3 plus unchanged single-screen endpoints and promotion endpoint.
- Produces: `/discover` UI defaulting to Mixed Live with lane filters, evidence disclosure, explicit market status, and visibility-aware cadence.

- [x] **Step 1: Write failing component tests**

Mock `fetch` with a representative mixed payload and render inside `MemoryRouter`. Assert the page defaults to a `Mixed Live` selected control, includes the exact disclosure “Candidates are INVESTIGATE, not trade signals.”, renders `MOOMOO LIVE` and `FINVIZ SNAPSHOT` text, filters a squeeze-only candidate after clicking `SQUEEZE`, reveals components/screens/provenance from a details element, and POSTs promotion before navigating to the workspace.

With Vitest fake timers, assert one initial POST, GET polls every 3000 ms, the next POST occurs at 120000 ms, `document.hidden=true` plus `visibilitychange` stops both, and becoming visible triggers a read/refresh cycle without duplicate intervals.

- [x] **Step 2: Verify RED**

Run: `npm run test -- DiscoverPage.test.tsx` from `ui`.

Expected: tests fail because the current page only exposes Single Screen cards.

- [x] **Step 3: Implement the component and intentional styling**

Add typed `MixedEnvelope`, `MixedCandidate`, and `MarketEnrichment` interfaces. Keep modes `MIXED` and `SINGLE`, default `MIXED`; issue immediate POST refresh and GET read; use one visibility-aware effect that owns and cleans both intervals. Preserve existing `refresh()` and inspector behavior for Single Screen.

Render wide rows with columns `Symbol / Setup / Attention / Price / Change / RVOL / Volume / Spread / Age / Why`, collapsing to labelled grid cells below 760px. Use existing typography and surface tokens. The page-specific signature is a 4px left market-status rail plus an adjacent uppercase text label; color supplements `LIVE/DELAYED/SNAPSHOT/STALE/UNAVAILABLE` and never replaces it. Add visible `:focus-visible`, motion-free refresh treatment under `prefers-reduced-motion`, lane chips with `aria-pressed`, and actionable degraded/empty copy.

Add `"/discover": "http://127.0.0.1:8766"` to Vite proxy configuration.

- [x] **Step 4: Verify GREEN and build**

Run `npm run test -- DiscoverPage.test.tsx`, `npm run test`, and `npm run build` from `ui`, then run `$env:PYTHONPATH='src'; .venv\Scripts\python.exe tools\validate.py changed` from the repository root.

Expected: component suite, UI suite, production build, and changed validation pass.

- [x] **Step 5: Commit the UI slice**

```powershell
git add ui/src/components/DiscoverPage.test.tsx ui/src/components/DiscoverPage.tsx ui/src/styles/layout.css ui/vite.config.ts
git commit -m "feat(ui): add mixed live discovery board"
```

### Task 5: End-to-end invariants, documentation, and final validation

**Files:**
- Modify: `tests/platform/test_mixed_discovery.py`
- Modify: `docs/superpowers/specs/2026-08-24-mixed-live-screener-design.md`
- Modify: `docs/superpowers/plans/2026-08-24-mixed-live-screener.md`

**Interfaces:**
- Consumes: the completed vertical slice.
- Produces: executable safety regression coverage and an implementation record.

- [x] **Step 1: Add the final failing safety regression**

Traverse refresh and read payloads and assert every candidate has `candidate_role == "INVESTIGATE"`, no payload contains `buy_score`, `sell_score`, `order_intent`, `paper_order`, or `broker_order`, and mixed refresh subscription calls contain only `BASIC_QUOTE`.

- [x] **Step 2: Verify RED for the broad invariant**

Run: `$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m unittest tests.platform.test_mixed_discovery.MixedSafetyInvariantTests -v`

Expected: fail on any incomplete invariant reporting or pass only after the assertion is first made stricter than the current payload; if it passes immediately, revise the fixture with forbidden nested keys to prove the walker catches them before exercising production output.

- [x] **Step 3: Make the minimum correction and record completion**

Remove or rename only the offending field/path, if any. Check off completed plan steps and append an `Implementation outcome` section to the spec listing the shipped routes, Moomoo-first boundary, configuration variable, and validation commands—without credentials or claims that opt-in live checks ran.

- [x] **Step 4: Run final verification once**

Run:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.platform.test_mixed_discovery -v
.venv\Scripts\python.exe tools\validate.py full
Set-Location ui
npm run test
npm run build
```

Expected: every command exits 0 with no failed tests. Run `.venv\Scripts\python.exe tools\validate.py live moomoo` only if the local Moomoo provider is already configured and explicitly safe to probe.

- [x] **Step 5: Review diff and commit the completed slice**

Confirm `git diff --check` is clean and `git status --short` contains only intended feature files plus the two pre-existing user-owned audit JSON edits. Stage exact paths only, then commit:

```powershell
git add tests/platform/test_mixed_discovery.py docs/superpowers/specs/2026-08-24-mixed-live-screener-design.md docs/superpowers/plans/2026-08-24-mixed-live-screener.md
git commit -m "test(discovery): lock mixed screener safety invariants"
```

Do not stage `evidence/ui1/assistant-audit/conversations.json` or `evidence/ui1/assistant-audit/messages.json`.
