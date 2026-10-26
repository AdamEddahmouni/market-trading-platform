# Professor integration implementation plan

**Goal:** Connect locally retained observations to bounded analysis planning, immutable daily decisions and historical replay.
**Spec:** Owner request supplied October 13, 2026, sections 0–16; retained verbatim in the sprint evidence package.
**Architecture:** Extend PF-01 schema-13 collection records, existing inference policies, news strategy evaluation and decision contracts. Integration happens in one isolated tree; serving schema-11 stores and all activation gates stay unchanged.
**Execution:** Owner-selected coordinator with isolated parallel workers. No additional design authorization is needed for the selected offline implementation.
**Technology:** Python 3.11 stdlib, existing SQLite state and manifest-driven validation.

## Global constraints

- No provider session, paid inference, trading, canonical migration, deployment, push or merge.
- No historical evidence edits, frozen methodology changes, calibration or strategy promotion.
- Preserve 512 MiB market-storage bound and existing budgets.
- Synthetic results remain engineering evidence.
- One writer per worktree; coordinator owns shared manifest, integration, docs and final acceptance.

## Work and interfaces

1. **Lane A:** `news/collection.py`, `news/knowledge.py` and focused tests. Read existing append-only records, preserve revisions and expose `StoredNewsRepository.retrieve(as_of=..., symbol=..., source_id=...)`. Test delayed receipt, correction/reversion, unchanged dedup, restart, metadata and limits before integrating.
2. **Lane B:** existing `inference/paper_automation.py` and focused tests. Add pure `plan_local_inference_dry_run(records, now=..., ...)` with Eastern windows, declared calendar facts, bounded budgets, truthful model/provider states and restart evidence. Test every selected boundary, DST, calendar, saturation, outages and budget exhaustion.
3. **Lane C:** `news_strategy_evaluation/journal.py` and tests. Build immutable snapshots from existing decisions; project later outcomes separately and retain no-action/reject/defer states. Test immutability, evidence time, outcome links and no fabricated fills/P&L.
4. **Lane D / coordinator:** `news_strategy_evaluation/replay.py`, `market_data.py`, `features.py` and tests. Extend the existing harness with a selected-day as-of view and existing compatible policies; keep receipt-time filtering on bars and exclude later AI/news. Outcomes remain outside decision input.
5. **Integration:** one fixture demonstration uses committed collector records for retrieval and catch-up, then existing policy decisions, journal and replay. Register focused tests in existing manifest, run changed/full validation and preserve exact logs.
6. **Readiness:** read-only protected-state checks, frontend build, launcher/secret-loading isolation where practical, market-date protocol and consolidated report. Keep four spawn tests explicitly uncertified if ordinary execution remains unavailable.

## Review focus

- Correction A→B→A must preserve every observed version.
- Late receipt of earlier market bars must not affect earlier decisions or returns.
- Dry-run plans must not advance a processed watermark or dispatch inference.
- Outcomes observed after the requested journal cutoff must remain pending.
- Calendar/model/provider unknown facts must not become permission to operate.

## Acceptance tracking

- [ ] Focused red/green test evidence for each lane
- [ ] Combined source reviewed and integration scenarios A–H tested
- [ ] Manifest changed/full validation and lint/docs checks
- [ ] Protected serving/DB/Paper/source state compared before and after
- [ ] Consolidated A–I report and professor demonstration
