# Professor intelligence integration — offline operator reference

**Scope:** Owner-selected October 13, 2026 sprint. This reference describes source functionality, not deployment, entitlement, trading authority or empirical strategy evidence.

## Reused flow

PF-01 `NewsCollector` → existing schema-13 `news_collection_records` → `StoredNewsRepository.retrieve` → existing inference policy dry-run → existing news strategy feature/policy contracts → immutable journal projection → later measurement → existing replay harness.

No parallel evidence database or new collector exists. Canonical schema-11 stores must not be opened with `LocalStateConnection` by this implementation before approved migration/deployment. New records in the demonstration are synthetic and belong only to a fresh explicit fixture directory.

## Collection and grounded knowledge

`news.knowledge.StoredNewsRepository(connection).retrieve(as_of=..., symbol=..., source_id=..., provider_id=..., published_after=..., published_before=..., include_revisions=False, limit=100, max_scan_records=10000)` reads existing records. Availability is the latest of saved observation, ingestion and supplied provenance availability clocks. Publication time is a filter, not the availability clock. Missing clocks withhold a record.

Unchanged observations deduplicate; changed content/provenance append a predecessor-linked revision. A→B→A reversions remain distinct. Original rows are never rewritten. Latest committed visible version is selected before symbol/publication filtering. Original URLs, source IDs, provider provenance and supplied rights metadata remain attached. The reader does not establish archival/display rights or recover corrections discarded by old code.

Output limit is 1–1000 records. Configurable scan cap refuses with `NEWS_KNOWLEDGE_SCAN_BOUND` rather than returning incomplete latest evidence. Existing primary-key indexing serves identity/revision lookup; retrieval remains a bounded scan, not a full-text semantic index. Stored content byte estimates are explicitly `STORED_CONTENT_BYTES_ONLY`, insufficient for a request/output budget.

## Inference policy and catch-up

`intelligence.inference.paper_automation.plan_local_inference_dry_run(records, **facts)` reuses the existing adaptive policy and model request registry. New York clock windows are 20:00–03:30 pause; 03:30–04:00 catch-up; 04:00–09:30 premarket; 09:30–16:00 regular; 16:00–20:00 after-hours. Calendar eligibility is a supplied verified fact; unknown calendar and provider facts defer. DST conversion uses `zoneinfo`; malformed local clocks fail closed.

Collection independence means only that the inference policy never stops a collector. It does not grant collection/subscription approval. No worker/service, reservation, inference call or processing acknowledgement is performed by planning. Only a separately completed analysis may advance the caller's processed revision IDs. Plans carry bounded request/token/backlog counts and truthful deferred/unscanned reasons.

Caller-supplied workload bounds only tighten the existing daily budget. `provider_gate` carries existing spending/provider refusals, including a dollar cap where one exists; this extension adds no dollar allowance. Records require `token_estimate_scope=REQUEST_AND_OUTPUT_BOUND` and a conservative bound including prompt, schema, output and applicable reasoning. Content-only/unknown estimates defer. Haiku 5.5 request-shape support is separate from actual provider availability. Local identifiers without catalog evidence are unsupported. Real model access was not probed.

## Daily evidence

`news_strategy_evaluation.journal.capture_decision_snapshot` consumes existing strategy decisions or Action Decision receipts and their exact source snapshot. Frozen nested evidence is canonical JSON; every read returns a detached value. Embedded Action Decision evidence is authoritative; an override must match. Detached action snapshots must match the existing digest and instrument/selection lineage.

`observe_outcome` and `observe_review` produce separate immutable observations with explicit observation clocks. A journal cutoff never includes a later observation. `build_daily_journal` groups by America/New_York by default (UTC opt-in). Research bias never becomes an operator action; explicit rejection/defer reviews remain distinct. Proposed order, actual order reference and fill reference are separate. This projection does not compute realized P&L; fill-backed accounting remains with existing execution/portfolio components.

## Replay and later measurement

`EvaluationReplayHarness.snapshot_at(replay_date=..., as_of=..., pack=...)` extends the existing harness with an Eastern selected-day clock. It supplies the same snapshot to deterministic baseline, enhanced and neutral/no-trade reference policies. Forward outcomes are absent from the decision view. Later news/inference is withheld; inference needs consistent input/result/instrument/source lineage, visible article content and aware clocks.

Fixture market bars can carry `received_time`, `provider_id`, `revision_id`. Decisions use only receipt-visible versions. Revisions group by event instant, including equivalent timezone formats. Legacy bars without receipt clocks remain usable with `LEGACY_MARKET_RECEIPT_TIME_UNKNOWN`; they cannot establish fully observed historical availability.

`measure_outcome(..., observation_as_of=...)` separates forward horizon from measurement receipt cutoff while retaining the original decision-time start anchor. `RealizedOutcome.measured_as_of` prevents later measurements being journaled earlier. Truncated horizons are `PARTIAL_HORIZON`. This measures hypothetical subsequent movement/MFE/MAE, not fills, causal attribution or realized profit. Research, calibration, frozen Item 9 methodology and promotion policies are unchanged.

## Working offline demonstration

From the IMP root with its Python environment and `PYTHONPATH=src`:

```powershell
python tools/research/professor_integration_demo.py --output-dir <fresh-disposable-directory>
```

The CLI installs the existing offline network/process guard and refuses a pre-existing fixture database. Output `demonstration.json` labels synthetic news and curated price data, simulated model/budget facts, exact source references, overnight pause, 03:30 catch-up, budget/provider refusals, immutable earlier/later journals, restart preservation and deterministic three-policy replay. No actual trading session is claimed.

## Operational status and remaining work

The implementation is a tested library/tool integration and is undeployed. Existing UI surfaces are retained; there is no new dashboard or endpoint. Daily journal/catch-up projections are not yet wired into the serving UI/controller or an unattended service. The demo invokes existing analysis policies directly; it does not prove live Screener/Opportunity Engine candidate generation. Fundamental/company/social document ingestion and general semantic search remain with their existing infrastructures; this increment adds the durable-news retrieval bridge only.

Production requires explicit deployment/migration approval, real source rights/targets/capacity, model/provider availability evidence and any separately authorized operating window. Paid inference, Paper automation, Live trading and unattended registration remain independently prohibited by the sprint request.
