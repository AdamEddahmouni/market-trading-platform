# OCT1-02 — Cross-asset connectivity

Status: implementation validated; canonical integration ledger is maintained in
the [OCT1-02 tracker](https://app.notion.com/p/3ed2085cc43c812fb894e45e70247d81). Evidence class:
SOFTWARE_CONTROLLED. This document is not a market-validation or execution claim.

## Isolation and scope

Fetched base and initial merge base:
`d8d8d998c3c35f810edb54f9011124574f6e1127`.
Branch: `codex/oct1-02-cross-asset-connectivity`.
Clean initial worktree:
`C:/Users/adame/.codex/worktrees/oct1-02-cross-asset-connectivity/market-trading-platform`.
The original checkout's unrelated artifact changes and all other branches were preserved.
OCT1-03 and AI Screener are outside this change.

## Audit and reused authorities

| Authority | Reuse and boundary |
|---|---|
| XA-01 | Existing equity, futures-family and dated-contract builders produce graph identities. Existing Screener XA IDs remain selected identities. Options summaries and curve/indicator observations explicitly have no invented instrument ID. All projected nodes withhold execution. |
| XA-02 | Admitted rates reference catalog: US 10Y→ZN, 2Y→ZT, 5Y→ZF, 30Y→ZB. These are reference metadata, never causal claims. |
| XA-04 | Configured `CrossAssetCatalogRepository` target relationship queries and bounded PIT scalar retrieval. No new relationship database; static XA-02 reference definitions remain available when the configured catalog has no stored rows. |
| XA-05 | Audited epistemic/availability and rates-state concepts. No stock-direction inference from macro state; this projection does not run a second strategic-state engine. |
| Options | Existing summary read, normalized chain cache, provider state, fetched clock, provider clock/latest trade clock and summary analytics. No chain duplication or put/call directional inference. |
| Futures | Existing cached Futures Context service and `FUTURES_CONTEXT_MAP_V1`. Matches are independently checked against selected sector/industry/cap metadata; validated contracts remain separate from families. |
| Bonds | Existing selected Rates & Curve maturity-reference rule, nominal/real par curve identity, publication date. A reference tenor is not a security yield. |

## Contract and implementation

Read-only `GET /screener/connectivity?instrument=...&universe=...` uses the
existing request authorization boundary (`state.read`), current-universe row
guard and `screener-connectivity/1.0.0`. Unknown instruments are rejected.
The projection module composes domain services; it does not own domain analytics,
provider symbols, tradability or canonical identity.

Response: selected instrument; up to 20 nodes and 24 deduplicated edges;
four explicitly requested domains with coverage state/reason; missing reference
identifiers and catalog-outage status retained alongside usable rates coverage; generated time;
non-causal research note. Each node preserves canonical identity where applicable,
kind/class, label, role, source state, source/event clock, retrieval clock where
supplied, compact facts, and `executable=false`. Each edge identifies endpoints,
relationship class/type, basis, definition version, explanation, evidence state
and provenance.

Structural relations: options-context→selected underlying and dated future→family.
Contextual mappings: selected equity→relevant future family using existing map.
Reference relations: admitted macro indicator→XA target, or existing selected
bond maturity→published par reference. Unsupported stock→Treasury, options→future,
issuer/company→bond and reverse future→stock mappings are not synthesized.

Equities support options and mapped futures; rates appear only through a supported
XA reference target. ETFs support their own options context, without an equity-sector
futures guess. Futures support contract-family/reference context without fabricated
reverse stock navigation. Bonds support their existing maturity reference.
Crypto is deliberately not admitted by this four-domain panel.

## Evidence assessments

- CONFIRMING / CONFLICTING: separate derived comparison edge to the observed dated
  future, only with explicit finite nonzero returns, provenance, identical basis
  and exact timezone-aware start/end windows, event time equal to the window end,
  CURRENT/LIVE observations and an end no more than 60 seconds before generation.
  Same sign confirms observed direction; opposite sign conflicts. Neither forecasts.
- CONTEXT_ONLY: available structural/reference context; mapping alone never implies
  directional support. Options and yields receive no arbitrary bullish/bearish rule.
- UNKNOWN: stale, zero, missing-window or otherwise incomparable observations.
- UNAVAILABLE: a source/observation is missing, refused or failed. All four requested
  categories remain visible; lack of a justified relationship is explicit.

Existing stock/futures daily-change percentages do not specify compatible return
windows. They therefore do not generate production confirming/conflicting claims.
Controlled test observations demonstrate the comparison contract without replacing
production provider data.

## UI

Cross-Asset is an existing Screener Dockview specialist panel and launcher entry.
It lazy loads with no new graph dependency. The SVG/CSS graph has keyboard buttons
and class-specific edge strokes, with evidence text independent of color.
An equivalent relationship table shows relationship, class, basis, state, source
and each endpoint's own clock. Node inspection exposes why connected, canonical
IDs, compact facts and edge provenance. Existing Options/Futures/Rates specialists
are opened or focused only where the current universe supports them.

The query key contains universe and settled instrument; abort signals, identity
validation and current-row guards prevent stale responses from repainting a prior
instrument. Changing selection remounts the inspector. Hidden tabs stop polling;
visible refresh is 60 seconds and uses existing service caches.

Controlled projection measurement: 20 loopback HTTP reads, 5 nodes/5 edges,
6,571-byte payload, median 2.53 ms and maximum 21.23 ms. These fixture-only
measurements do not estimate live provider latency. No graph library was added.

## Validation evidence

- Backend connectivity: 14 tests passed, including guarded HTTP route, wrong
  underlying/prior instrument/unrelated future, four universes, independent clocks,
  bounded summary, PIT query, reference-only identities and derived comparisons.
  Review regressions cover over 1,000 admitted observations and mixed available/
  missing references in either order. XA04 now exposes latest admitted nonmissing
  scalar as-of; Mongo orders descending before limiting to one. Existing ascending
  history-query semantics remain unchanged.
- Full UI: 165 files, 1,258 tests passed after the new launcher expectation update.
- Focused UI: 18 tests passed; 7 new graph/coverage/selection tests.
- Typecheck passed. Production build and bundle budget passed: initial 99.69 KiB
  gzip against existing 200 KiB limit; Cross-Asset is a lazy chunk.
- Mandatory FAST invariants: 23 passed. First cold run reported SEVERE_REGRESSION;
  retain that timing finding rather than infer performance from passing assertions.
- Changed validation attempts were interrupted. A completed platform slice found
  two old exact capability assertions, now updated and passing focused validation.
  One Windows oversized-body HTTP connection abort passed on focused rerun.
- Canonical `tools/imp.py closure --skip-ui --workers 2` completed in a detached
  Windows process: full 7,786 tests, 7,733 passed, 53 skipped, zero failures/errors.
  UI gates were run separately using the installed Node/npm entry point because
  the shell's npm shim is broken. Docs and whitespace checks passed.
  Full timing telemetry was SEVERE_REGRESSION: 467.313 s vs 198.882 s baseline
  (+134.97%); intelligence/platform/software acceptance were the slowest suites.
  This existing validator metric is observe-only; no timing pass is inferred.
  The earlier console interruptions are superseded by this completed result.

Controlled actual-browser acceptance used the real Screener and this projection
with isolated fixture-only providers and execution/live gates disabled. Passed:
central selected stock; structural options; mapped futures; XA Treasury reference;
publication clock; confirming/conflicting examples; unavailable options; inspector;
source/provenance; existing Futures specialist drilldown; selection replacement;
close/reopen and one panel; 390px viewport rendering.
Late-response isolation is independently tested with a deferred request.
Local results/screenshots are under `.local/oct1-02-*`; no synthetic values enter
production. These checks are SOFTWARE_CONTROLLED, not live empirical evidence.

## Limitations and integration gate

Configured XA catalog observations may be empty or unavailable, even when an
authoritative reference relationship exists. Missing retrieval/source clocks stay
missing. Rates publication observations are not realtime. The projection uses
bounded repository retrieval and retains existing domain cache behavior.

Implementation commit, PR, required-check result, merge SHA and verified remote-main
SHA are maintained in the integration/tracker evidence when those events occur.
Do not mark OCT1-02 Done before verified canonical integration.
