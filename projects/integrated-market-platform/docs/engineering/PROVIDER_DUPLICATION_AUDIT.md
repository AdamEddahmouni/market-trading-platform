# Provider Duplication Audit

This audit records the simplification decision for provider and replay paths. The governing rule is that apparent structural duplication is not sufficient evidence for extraction when availability clocks, source authority, outage semantics, or fail-closed behavior differ.

| Area | Repeated shape observed | Semantic differences / risk | Decision |
|---|---|---|---|
| Replay store construction | Provider, donor, integration, assistant, GridIQ, and UI tests repeatedly construct `ReplayStore` over the same pinned 8 MB donor JSONL | Each store must own independent bars, sessions, evaluation results, and strategy state | Cache only verified immutable source bytes in `ui_api/store.py`; decode fresh objects for every store |
| Default transition stream | Donor bridge consumers repeatedly read the same pinned transition JSON fixture | Callers may mutate decoded mappings | Cache only immutable bytes for the canonical fixture; JSON-decode a fresh value per call; custom paths remain uncached |
| Provider envelopes | Fixture adapters repeat event/receive/available clock fields and envelope admission shapes | Option chains, disclosures, futures, order flow, and market data have deliberately different PIT clocks and authority rules | Retain capability-local implementations and the shared canonical envelope boundary; no clock-building extraction |
| Fixture adapter filtering | Several adapters accept `as_of_time_ns` and filter before projection | The eligibility clock is source-specific; substituting envelope availability for event time would create lookahead or false exclusion | Retain explicit adapter filters; cover through domain tests and mutation verification |
| Unconfigured providers | Eleven `Unconfigured*` capabilities plus disabled execution return similar fail-closed results | Capability names and contracts must remain independently diagnosable | Retain explicit stubs; strengthen one conformance selector to exercise every default composition capability |
| Live provider plumbing | Live adapters repeat request, retrieval, and normalization scaffolding | Credentials, gates, rate behavior, publication schedules, and source authority differ by provider | No extraction; LIVE isolation remains manifest/gate controlled |
| Test fixture setup | Several provider test classes build a `ReplayStore` in `setUpClass` | Cross-module sharing would couple test mutation and lifetime | Keep suite-process-local setup; rely on immutable byte caching inside each process |

Measured evidence supported only the two immutable fixture-read optimizations. The provider suite improved from 71.43 seconds in the historical run to 55.79 seconds in optimized FULL run #2, while its 92 tests continued to pass. No provider normalization, availability-clock, source-routing, or live-network code was consolidated.

Rejected extractions are intentional. A larger generic provider base or universal clock helper would shorten files while obscuring the source-specific decisions that the PIT and authority regressions are designed to protect.
