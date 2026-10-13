# PF-01F integration, deployment and overnight acceptance

Prepared 2026-10-13. All live actions below are pending operator authorization. The completed offline evidence belongs to REPORT.md; no command in this document has been used to deploy or activate collection.

## Protected identities and source integration

SSD volume: Samsung SSD, NTFS, `\\?\Volume{87bca5a6-b412-463f-a0fb-40878c6a932f}\`, currently E:. Resolve this volume at deployment time; refuse absent/ambiguous identity. Preserve the sibling `IMP-MIGRATION-BACKUP-20261009-191132-da825e16`; do not recopy its approximately 134 GB contents.

PF-01E starting source is `3578d5b08a809af6d957e6aa74a4c880b674564a`. Integration base is current remote main `b4743f68c4f213358dacb6207572a12079602b00`, verified through GitHub on this date. The PF-01F exact final commit and file hashes are in final-state.json. The PF-01 branch includes earlier PF-01 source, tests and documentation; it does not integrate other isolated branches.

The serving tree is not a Git checkout. A full comparison of 2,848 source files against `w-auto` commit `12ad00ee5c940618b69609484f08c7dbd5f87264` matched 2,845 files. Three extra serving files have no counterpart in that reference: `src/market_platform_foundation/market_data/delayed_futures_bridge.py`, `tools/ibkr/futures_delayed.py`, and `ui/src/components/screener/localZone.ts`. Their hashes are preserved in protected-inventory.json. This does not prove the whole deployed app has one commit identity. Build outputs, all extra files, private files and state require their own deployment preimages. Preserve these extra files; do not infer permission to remove them.

The transition from 12ad00ee to main also includes previously accepted non-PF-01 changes (notably adaptive scheduling). A release derived from current main would include those pre-existing differences. The source integration manifest distinguishes the PF-only PR diff from the larger serving release delta. A clean PR is not evidence that an arbitrary file replacement is safe. Unfinished `w-auto` Paper work and its untracked files remain isolated and unchanged.

## Release prerequisites and procedure

1. Review final source, tests, hashes, dependency inventory, provider matrix and outstanding review findings. Approve the exact serving release delta and preserve every unmatched serving file. Use Git objects from a pinned commit to stage a separate release; do not copy arbitrary working files. The source package excludes credentials, canonical databases, generated research artifacts and migration backup data.
2. Confirm the mounted volume by identity, available space, state namespace and current process IDs/creation times. Confirm no trading or paid-AI authorization changes. The existing normal launcher enables internal Paper gates; the PF-01 collector needs a separate clean environment with every execution gate off. Do not reuse `RUN_IMP.py normal_environment()` for a collector: it configures internal Paper and writes cache manifests.
3. With approval for a serving restart, stop only the recorded serving processes and all writers to each database being migrated. Use a consistent SQLite backup (SQLite backup API or verified copy after all writers and WAL are closed), retain the original DB/WAL/SHM and source preimages, record checksums/schema/counts, and validate backup integrity before changing a canonical store. Never copy a live main DB alone while its WAL has outstanding commits.
4. Validate the staged source entrypoints and dependencies using the offline wrapper and disposable schema-11 fixtures. Migrate only the explicitly approved canonical database(s), using the existing `LocalStateConnection` migration authority with `require_existing=True` and verified file identity. The collection supervisor and collection-only entrypoint refuse schema mismatch; neither is a deployment migrator. Stop if the store differs from the approved preimage or a migration fails. Version 12 may commit before a version-13 failure; inspect actual schema before retry.
5. Verify schema 13, additive collection tables/indexes, legacy Paper rows/identity, foreign-key/integrity checks and no unwanted writer. Start the approved serving source with its existing operator configuration; collection remains off. Verify the expected API/service identity and Paper/Live authority. Only then consider a separate collector activation decision.

Dependencies are reused: bundled Python 3.11, existing read-only package layer including tzdata, moomoo SDK for actual OpenD access, existing stdlib WebSocket implementation for Kraken, existing HTTP adapters for news. No dependency was installed by this sprint. Do not confuse a Python package's presence with an account entitlement.

## Rollback

Before migration, stop the staged release and restore verified source preimages without touching databases. After migration, schema-11 code refuses a schema-13 database. A code-only rollback is not sufficient and there is no product downgrade API.

For rollback after migration: stop every writer; preserve the entire upgraded DB plus WAL/SHM and newly collected evidence as a separate immutable incident snapshot; validate the pre-migration backup and its exact identity; restore the approved source and its corresponding consistent schema-11 backup. Never silently discard collection records generated after the backup. State written after the backup remains in the preserved upgraded store and needs reconciliation; a rollback does not magically replay it. Revalidate Paper state, provider/session gates and serving health before restart. No retention expiry, deletion or production compaction is part of this procedure.

## Acceptance configuration and owner choices

`PF01F_ACCEPTANCE.env.example` is an inert template: all supply/collection/live/provider/execution gates are off, targets and entitled sources are empty, no state path is selected. It contains no credentials. The source remains default-off. Offline plan/configuration tests exercise this template and synthetic enabled profiles; the template itself cannot start a real run.

Choose a capture profile only after inspecting the expanded provider/feed list:

- News metadata only: lower modeled volume, event-driven supply; review each catalog publisher's storage/use terms. No raw trade capture claim.
- Selected L1 snapshots: existing per-stream coalescing/TTL semantics; this is snapshot capture, not complete quote-event history. Capacity estimates must use the actual enforced snapshot interval.
- Selected raw trades: every observed admitted trade is targeted for durable persistence; estimated rate and payload size vary greatly by symbol/venue. No silent sampling or conversion to bars.
- Depth/book updates: larger and burstier payloads; use the measured depth profile and conservative rate. No full-universe or unlimited-retention guarantee.
- Current bars: existing persistence records changed bar updates/revisions, rather than promising completed-bar-only capture. PF-01 headless supply currently supports only listed L1/ticks/depth and Kraken trades/book. A one-revision-per-minute bar model is hypothetical, excludes extra revisions, and cannot activate a PF-01 bar-only collection path.

The owner must provide sources, existing supported symbols/canonical IDs, capabilities/granularity, account rights and permitted archival use, maximum resource budget, retention policy (preserve-all and stop is the safe default), exact start/end timestamps, deployment/migration authorization, and unattended host/mount/power prerequisites. No source, target universe, deletion policy or new paid plan has been chosen here.

## Real acceptance run

Proposed bounded window: one owner-approved 8-hour period, with explicit date and ET/UTC start/end recorded before activation. This is a proposal, not a scheduled job. Forecast the selected profile for that interval plus headroom; refuse insufficient database/free-disk budget. The shipped combined DB+WAL limit remains 512 MiB with the existing 8 MiB reserve. A large raw-trade profile may require an approved different architecture or shorter window; free SSD capacity alone does not lift the application ceiling.

Start only the verified collection supervisor (`tools/platform/pf01_supervisor.py --run`) in a dedicated operator terminal after every prerequisite passes and current schema is verified. It starts the collection-only child, not the serving API or trading controller. Use a clean, explicit environment and approved credentials only. A default CLI invocation produces a read-only plan; `--status` reads status. Never arm Paper or Live, enable paid AI, or open an IBKR session as part of this run.

Emergency stop: press Ctrl+C in the dedicated supervisor terminal. Its finally path calls supervisor.stop(), sends `stop` to its child, waits up to 15 seconds, then terminates the owned child if needed. This does not liquidate or trade. **The current supervisor CLI has no `--stop` option**; the earlier report's `pf01_supervisor.py --stop` command was invalid. Abruptly ending the supervisor is a fallback, with child lease expiry and unclean-run uncertainty; record that interruption rather than reporting a graceful drain.

Record before/during/after:

- Source commit, volume identity, DB identity/schema, effective sanitized config, capability-report age, selected source/session coverage and exact observation window.
- Supervisor/child PID+creation time, writer owner/run/lease, subscription status/refusals, received/admitted/committed/duplicate/rejected/pending counts, gaps and uncertainty, queue high-water marks.
- DB/WAL/free-space growth, capacity warnings, CPU/memory, provider reconnects/quota events, latest source event/receipt/commit timestamps and news per-feed poll outcomes.
- Zero trading activity and zero paid AI/provider purchases. Existing prepaid/provider usage is still counted against its approved quota; zero new spend does not prove unlimited licensed use.

Pass criteria: current admitted observations reconcile to committed + duplicates + explicit known drops + pending/uncertainty; graceful stop drains accepted work within its bound or reports incomplete; no corrupt DB, invalid checkpoint or duplicate native identity; no uncontrolled restart loop; no unauthorized source/target/session or execution; capacity remains within the approved bound; source silence is interpreted using actual session/provider state. Any unexplained received/admitted loss, wrong owner, stale rights, capacity stop, quota violation or unexpected spend/execution fails acceptance and stops the run.

Kraken expects continuous connection activity; individual trades can legitimately be absent for a quiet pair. Equities may be closed, thinly traded, in a halt or outside this transport's session coverage. Provider connected + successful polling/no events is different from disconnected/reconnecting, and both differ from a dead consumer or stalled writer. Calendar coverage beyond 2026 is unavailable in the current source; it cannot certify future holiday/session expectations. Never backfill an unobserved interval as if it were known at the time.

After the window, stop and preserve source/config hashes, stage counters, final health, SQLite integrity/checkpoints, growth and provider evidence. Review actual overnight results before permitting recurrence. Accelerated synthetic evidence alone cannot pass this operational acceptance.
