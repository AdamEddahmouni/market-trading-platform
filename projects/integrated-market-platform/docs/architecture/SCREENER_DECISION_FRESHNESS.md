# Screener decision freshness

Classification: CURRENT_CANONICAL_TRUTH, software contract. Version: decision-freshness/1.0.0.
Owner milestone: OCT1-03. No empirical provider or trading authority is established here.

## Authority and intended use

`market_data/freshness_contract.py` evaluates source facts at an explicit UTC decision cutoff. `ui_api/screener_freshness.py` composes existing acquired payloads; it performs no provider I/O. Successful Screener responses carry `decision_inputs`, row/quote vectors or individual `decision_evidence`. Existing domain state and timestamps remain available.

Delivery mode (REALTIME, DELAYED, SNAPSHOT, PUBLICATION_BASED, HISTORICAL, REPLAY, UNKNOWN) is independent of freshness (CURRENT, STALE, UNKNOWN, UNAVAILABLE, SESSION_CLOSED). ADMISSIBLE, DEGRADED and BLOCKED describe intended use, not entitlement or execution permission. A current Options snapshot is reference context; a current delayed quote is blocked for current-market synthesis. Provider health never establishes symbol currentness.

Each status retains capability, source, timestamp basis, observation/publication `as_of`, receive/fetch clocks when available, evaluation cutoff, age, threshold, policy/version, deadline, reasons, source state, intended role and separate current/reference eligibility. Row groups contain `covered_fields`; distinct source/state/clock groups are never collapsed. Contract/term dates remain identity facts.

## Domain policies

| Capability | Clock and existing authority | Decision use |
|---|---|---|
| Equity/ETF L1 | Provider event, 60 seconds; legacy 5-second receipt/feed authority retained | Current only with valid source event and source state; delayed is explicit and excluded |
| Finviz rows / fundamentals | Export retrieval is not observation proof; report cadence often unknown | UNKNOWN/BLOCKED without observation proof; dated publication can be DEGRADED reference |
| Bars / charts | Latest completed end, selected timeframe plus existing 3-minute tolerance; domain session policy retained | Current bars separate from quote clock; cached bars re-evaluate at read time |
| Order Flow / CVD | Latest selected-symbol event, existing 30-second feed-silence policy also applied per symbol | Stale or future events excluded even with healthy feed |
| Level 2 | Provider-specific supplied receive TTL and source validity; event retained separately | Expired/invalid/unavailable depth blocked |
| Options | Existing snapshot-fetch cadence/threshold; provider as-of, latest contract trade and underlying quote remain separate | Snapshot reference only; recent fetch cannot rescue source STALE |
| Futures | Existing 15-second quote authority, separate dated-contract validity | Current dated contract required; reference context, no execution authority |
| Bonds / rates | Auction, operation, observation or publication dates; retrieval separate | Publication reference; unknown cadence stays UNKNOWN/DEGRADED; stale source blocked |
| Cross-Asset | Independent node clocks; stock return 60 seconds and Futures return 15 seconds, exact compatible windows | Stale/delayed/invalid dependencies yield UNKNOWN comparison |
| Short Squeeze | Existing metric clock kind and source publication authority | Explicit source PUBLICATION_CURRENT may admit reference; unknown realtime policy fails closed |
| News / movement | Publication time, existing relevance windows (1h/4h/24h/72h), first retrieval separate | Reference only; derived movement inherits quote/bar eligibility |

`valid_until` comes from server policy. React can withdraw an expired assertion; it cannot invent a threshold or grant eligibility. Native expandable details show source, basis, clocks, policy, use and reason text. Rows, panel headers, graph nodes and previews also withdraw expired CURRENT labels. Hidden panels retain existing demand/polling behavior.

## Mechanical consumer gate

Future synthesis must call `eligible_evidence(inputs, now=decision_cutoff, reference=False)` immediately before using current-market evidence. The helper recomputes source status and age, ignores cached eligibility booleans, rejects an earlier-than-evaluation cutoff, and excludes stale, unavailable, unknown-policy, delayed, historical/replay and reference-only inputs from current use. Reference use requires a separate `reference=True` call and explicit reference-role inputs; stale sources are still excluded. Join row values through `covered_fields` and instrument identity, not a table-wide boolean. Required capabilities must each be present in the admitted vector; absence blocks that reasoning mode rather than being filled with unrelated reference evidence.

This gate is the required OCT1-04 handoff. The AI Screener invokes it on the
bounded packet immediately before candidate reduction; see [Screener AI
candidate reduction](SCREENER_AI_CANDIDATE_REDUCTION.md). The AI Screener adds
an explicit, read-only synthesis endpoint and reuses the existing News
provider boundary, but introduces no execution path, provider, subscription or
autonomous action loop.

## Equity/ETF price convergence

Screener page and selected-row reads join the already-owned, per-symbol OpenD
L1 cache after snapshot filtering and ordering. Last price, volume and supplied
bid/ask/spread retain their own provider/event/receive provenance; reference
caches are immutable. Finviz fundamentals and discovery fields remain Finviz
reference data. Missing L1 values do not erase reference values, and a stale
L1 price remains visibly stale instead of reverting to a timeless export.
The existing 32-symbol expiring window serves the selection and the visible
rows. Historical: it also warmed the first 20 equity/ETF rows when an AI run
read only the head of the sorted result. An AI run now takes its own bounded
vendor snapshot of every row it assesses; AI reads do not acquire
subscriptions or issue per-symbol provider calls.

A book carried through a newer last-price push has only a retained book receipt
clock in the existing cache. Its provider event clock is therefore unknown,
not copied from the newer price. It stays visible but cannot establish current
bid/ask evidence. Unknown price clocks, delayed quotes, disconnects, future
observations and aged quotes still fail the existing OCT1-03 gate.
See the [controlled convergence receipt](../superpowers/plans/2026-10-07-screener-live-price-evidence.md).

## Bond dates

Maturity, issue, expiry and settlement terms describe the security. Auction and operation dates describe the corresponding source event. Observation/publication dates accompany reported market values. Retrieved/fetched dates describe acquisition. Bond preview labels Maturity explicitly and Observed beside the observed-price date; the decision vector excludes identity/terms/date-unit values from freshness. A future maturity cannot make old observations current.

## Limits

Unknown Finviz report/publication cadence is deliberately not guessed. Publication references with a known source date but no verified cadence remain DEGRADED and cannot establish current-market truth. Source publication authority is supplied by the existing source-specific service; the shared evaluator does not independently verify publication schedules. The contract governs Screener read models and future consumers that invoke its gate, not every unrelated platform or trading path. Client expiry relies on the workstation clock and conservative server deadlines; source event precision and provider availability remain external dependencies.
