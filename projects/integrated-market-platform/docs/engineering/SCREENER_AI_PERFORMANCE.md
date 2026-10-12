# Screener / AI pipeline performance

**Status:** Corrected source and controlled local measurements validated; protected integration and portable acceptance remain separate gates.

This document governs measurements of the existing Screener and bounded AI
evidence path. It does not change roadmap priorities, inference authorization,
Paper admission, provider entitlement, or broker execution authority.

## Evidence and provenance

The five original records in `evidence/performance/screener-ai-20261012/`
are preserved byte-for-byte. Their timings are **provisional historical
measurements**, not final acceptance: they preceded the security corrections,
had incomplete fixture/environment attribution, and included an invalid UI
memoization comparison. The previous 147.87 → 58.13 ms response claim and
0.387 → 0.0005 ms UI claim must not be reused as accepted results.

`tools/screener_ai_perf_profile.py` v2 measures production functions on a
deterministic **synthetic** Finviz-shaped export, not captured live provider
traffic. It hashes every provider row and records the actual admitted count,
the requested target, page limit, all admitted row values, filtered row values,
ordering, serialized response bytes, AI observations, and production paging.
The full profile verifies each admitted identity appears exactly once, and
paged rows reproduce the complete ordered value-bearing universe.

Source provenance includes the exact Git SHA and tracked/untracked status in
`src/`, `tools/`, and `ui/`, the measured code scope. Documentation, appended
evidence, and unrelated historical artifacts are outside that scope. Dirty or
unknown measured source cannot support an accepted comparison. Different clean
before/after SHAs are expected for an optimization comparison.

Environment records include the complete Python version, implementation,
operating system, processor, core count, physical memory, and hashed machine
identity. Methodology names the exact harness hash, clock, warmup, GC mode,
separate allocation pass, and stage-specific cache conditions. Samples,
repetitions, median, mean, standard deviation, min/max and p95 are retained.

`tools/screener_ai_perf_compare.py` rejects missing attribution, incompatible
fixture/value/method identities, different environments or repetitions, dirty
source, and nonpositive/nonfinite durations. Incompatible records carry raw
times without ratios or speedup claims. Small/noisy differences receive no
speedup label; the 0.25 ms floor is supplemented by a conservative uncertainty
estimate. This is controlled local evidence, not a universal latency guarantee.

## What the measurements include

The response stage runs freshness projection, engine-lock projection, leak
audit and canonical serialization for a prepared synthetic page. It excludes
HTTP routing/transport, universe fetching, provider requests, inference,
browser frames and trading. Cache-hit and explicit cache-clear reads are
separate stages. Quote inputs and timestamps are controlled fixtures.

AI projection/candidate/planning stages operate on the measured page, not the
whole universe. Full-universe coverage is measured separately through the
production paging service. Synthetic quote-view timings are not freshness
acceptance of an actual provider session.

## Security and correctness dispositions

| Proposal | Final disposition |
|---|---|
| Credential regex mandatory-literal prefilter | Removed. ASCII escaped tokens and dynamic patterns disproved the necessary-condition claim. Original `re.search` evaluation of every current governed rule and sorted result IDs retained. |
| Unicode response protection | JSON audit rendering preserves Unicode characters, so case-insensitive governed rules inspect their actual characters rather than ASCII escape spellings. HTTP response serialization remains separately owned. |
| Structural leak walk | Retained lazy path construction with parity coverage for scalars, containers, public-authority exceptions and finding order/fingerprints. |
| Key classification cache | Bounded, includes marker-policy identity, and bypasses caching for string subclasses. Redaction behavior remains governed by the same classifier. |
| Prepared filters | Removed eager preparation. Direct operator branches retain original field access, missing-value handling, rejection and short-circuit/error timing. |
| AI frozenset projection | Removed; baseline tuple projection and malformed-input behavior restored. No AI projection speedup claimed. |
| Admission classification cache | Bounded normalized-industry memoization retained. |
| Row envelope projection | Reads each field attribute once; field shape/provenance retained. |
| React computations | Shared production hooks memoize catalog projection and screen serialization; real dependency changes invalidate them. |

Regression/differential coverage provides bounded empirical evidence. It is
not a proof over every Python object or regex program. The regex optimization
was removed because its general equivalence was not established.

## UI methodology

`ui/scripts/measure-screener-render-cost.mjs --fixture FILE --out FILE` imports
the same production hooks used by `ScreenerPage`. Export its catalog fixture
from production `filter_catalog(None)`; columns are read from the page's actual
definition array. Both shapes are hashed and counted, not hardcoded. Recovery
observed **62 catalog entries and 73 columns**.

The harness uses actual React `createRoot` and `act` in jsdom, with 40 warmups
and 400 alternating samples per side. It compares independent original
computations with the production memoized hooks, checks stable identities,
and invalidates every catalog/screen dependency. Steady-state and changing
dependency workloads are reported separately. It includes React scheduling
and hook work; it excludes full-page DOM, browser layout/paint, network,
provider traffic and inference. Its results are not browser interaction latency.

## Subsystem ownership

| Responsibility | Source / authority | Regression ownership |
|---|---|---|
| Admission and security category | `ui_api/screener_admission.py` | platform admission/projection tests |
| Row fields, cached reads and quotes | `ui_api/screener_projections.py`, `screener_snapshot.py` | ui1 Screener service/API tests |
| Filter validation/evaluation/order | `ui_api/screener_filters.py`, `screener_query.py` | ui1 filter parity and Screener tests |
| Decision freshness / bounded AI facts | `screener_freshness.py`, `screener_ai.py` | platform AI projection and existing AI boundary tests |
| Full-universe accounting | `screener_ai_universe.py` | platform coverage tests and profiler value parity |
| Credentials and response gates | `platform/security/leak_audit.py`, `redaction.py`, `ui_api/server.py` | platform leak/redaction and actual HTTP handler tests |
| Stage measurements / comparison | `tools/screener_ai_perf_*.py` | validation tooling tests |
| Render state / operator interaction | `ui/.../screener/ScreenerPage.tsx`, `screenerRenderMemo.ts` | real React memo tests and complete UI suite |

All Python tests remain registered through `tools/validation_manifest.json`;
UI tests remain owned by `ui/package.json`. No alternate inventory is created.
Screener limits, refresh/cache policies and quote freshness remain in their
existing source constants and contracts. Historical closure findings are
preserved. The closure JSON is also an executable complete-path inventory:
only the two new tool paths are appended to its existing performance owner,
without changing prior classifications, findings or evidence. This current
document routes the new tools and their regression ownership.

## Validation and acceptance

Use focused security/filter/AI/tool tests, actual response gates, UI tests,
typecheck and bundle-budget build, followed by manifest CHANGED and FULL.
Use independently owned fixture/dependency directories, isolated state and
two-worker bounded validation. Never create a development link into runtime
fixtures, owner Paper history, secrets or model directories.

Final controlled before/after receipts, independent-review disposition,
protected PR/merge identity, bounded deployment hashes, and actual live
runtime acceptance are reported separately. A merged source change does not
itself deploy the SSD. Unmeasured or unavailable observations remain explicit.
This sprint stops after the specifically authorized acceptance work.


## Corrected controlled measurements — 2026-10-12

Before: `d47e3c9ee3bf05d6de663bfaaabbec9681b1fdc4` (accepted PR #494). After:
`c9f4daebddb6c26aebbf7fa332967231198058c5` (the reviewed source). Both measured source scopes
were clean. Same CPython 3.11.15 / Windows / AMD Ryzen 5 3600 host; complete
environment and methodology records are retained. Three alternating process
pairs requested 21 repetitions per stage; actual per-stage repetitions and
warmups are recorded. Main response/filter stages have 21 samples per pair.
The table reports the median of the three per-process medians in milliseconds.

Fixture: **5,085 synthetic provider rows**, **4,622 actually admitted rows**,
200-row response pages, 412 rows matching the three-rule filter. Production
full-universe paging returned all 4,622 unique rows over ten pages with exact
value/order parity. This is a controlled synthetic workload, not a measured
live provider universe.

| Stage | Before ms | After ms | Disposition |
|---|---:|---:|---|
| Prepared response CPU | 148.979 | 99.037 | Improved in all three pairs |
| Complete leak audit | 84.850 | 52.111 | Improved in all three pairs |
| Structural leak walk | 52.049 | 20.168 | Improved in all three pairs |
| Three-rule filtering | 18.666 | 9.546 | Improved in all three pairs |
| Filtered uncached read | 19.746 | 10.206 | Improved in all three pairs |
| AI observations (baseline retained) | 1.469 | 1.479 | No reproducible improvement claim |
| Full-universe service paging | 4.107 | 3.908 | No reproducible improvement claim |
| Universe refresh CPU | 94.132 | 90.200 | No reproducible improvement claim |

All three accepted comparison reports are `COMPARABLE`; none flags a
regression across 42 stages. This does not assert that every small timing
difference is an improvement. Five stages improve beyond the thresholds in
all pairs. The removed regex shortcut and reverted AI optimization are not
credited with performance gains.

Actual React/jsdom hook workloads: steady state
**0.0720 → 0.0128 ms**;
changing dependencies **0.0653 → 0.0438 ms**.
These include React scheduling/hook work and remain small absolute costs;
they are not browser frame or full-page responsiveness measurements.

The initial new collection overlapped a UI timing run and is retained as
provisional evidence, including its two regression flags. Acceptance uses
only the subsequent serial collection; no prior measurement was edited.
Raw distributions, ranges, comparisons, review, security differential,
fixture integrity and validation summary are in
[accepted receipts](../../evidence/performance/screener-ai-20261012/accepted/).

Final local validation: CHANGED **2,901 tests / 9 skipped / 0 failures /
0 errors**; FULL **8,611 / 59 / 0 / 0**; UI **1,427 tests**; typecheck,
production build (100.77 KiB initial gzip bundle), lint and docs links pass.
The three FULL path errors were resolved solely by shortening the disposable
temp root, with focused reproduction followed by a passing full rerun.
Independent final review has no blockers. Protected integration and actual
portable live acceptance are separate remaining receipts.
