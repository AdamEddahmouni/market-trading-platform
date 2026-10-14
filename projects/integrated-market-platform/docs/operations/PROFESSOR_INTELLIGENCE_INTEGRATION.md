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

## Operator evidence review (read-only)

Portfolio → Outcome evaluation carries an **Evidence review** section. It calls five GET routes, all `audit.read` with the Paper ledger account scope, composed in `ui_api/evidence_review.py`:

| Route | Shows | Source |
|---|---|---|
| `/evaluation/evidence/status` | Current New York inference window, the schedule, the four collection gate states, stored-news count, the saved engine and model | `inference_session`, existing collection status functions, synthesis settings |
| `/evaluation/evidence/knowledge?as_of=&symbol=&source=&provider=&limit=&revisions=` | Stored news as it was known at a cutoff, with source, link, rights note and correction linkage | `StoredNewsRepository.retrieve` on the application's own open local state |
| `/evaluation/evidence/plan?at=&max_requests=&max_tokens=&max_backlog=&request_allowance=&assume_available=` | What a catch-up would plan from evidence stored now: planned and deferred records with reasons, bounds, recorded budget | `plan_local_inference_dry_run` |
| `/evaluation/evidence/journal?day=&as_of=&decision_id=` | Action Decision receipts of one New York day as frozen journal entries, with the later Paper execution and next-session observations at the same cutoff | `capture_decision_snapshot`, `build_daily_journal`, the prospective evaluation projection |
| `/evaluation/evidence/replay?date=&as_of=` | The curated fixture day rebuilt as of a clock and given to the three registered policies | `EvaluationReplayHarness.snapshot_at` |

Every response carries an `authority` block with zero provider calls, zero inference calls, no budget reservation, no state write and no execution authority. A cutoff later than the server clock is refused. The routes open no store of their own, start no collector and create no budget file.

What the plan reports honestly: model availability is never probed, so without `assume_available=1` every record defers with `MODEL_AVAILABILITY_NOT_VERIFIED`; the flag is an operator assumption for a preview and is labelled `OPERATOR_ASSUMPTION_FOR_PREVIEW`. Stored bytes are not a request budget, so without `request_allowance` (the operator's token bound for the prompt and answer of one request) every record defers with `TOKEN_ESTIMATE_NOT_VERIFIED`. Operator bounds only tighten the recorded daily budget. `at` may name the present or a later instant, for example tomorrow 03:30 New York; evidence is always read as of the present. No catch-up worker exists, so `processed_state` is `NO_COMPLETED_ANALYSIS_RECORDED`.

What the journal reports honestly: a receipt the journal contract refuses is listed under `unjournaled` with its reason and is never repaired. Operator action is null unless a decision trace records one. Paper execution appears only where the ledger holds the linked episode. Realised P&L is not computed here. A receipt that froze and names an operator-selected Opportunity is accepted on identity and clock, matching the action service; an unnamed or separately supplied Opportunity still needs shared evidence.

The replay view is `SOFTWARE_FIXTURE_ONLY`, states `NOT_A_PERFORMANCE_RANKING`, and offers only the days and clocks present in the fixture pack.

## Operational status and remaining work

The implementation is tested source and is undeployed. The evidence review section above is its only operator surface; there is no new dashboard, worker or scheduler. The catch-up plan is a projection: nothing dispatches it, and no unattended service exists. Stored news is empty until collection has been deployed, migrated to schema 13 and separately enabled. The demo invokes existing analysis policies directly; it does not prove live Screener/Opportunity Engine candidate generation. Fundamental/company/social document ingestion and general semantic search remain with their existing infrastructures; this increment adds the durable-news retrieval bridge only.

Production requires explicit deployment/migration approval, real source rights/targets/capacity, model/provider availability evidence and any separately authorized operating window. Paid inference, Paper automation, Live trading and unattended registration remain independently prohibited by the sprint request.
