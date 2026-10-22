# AUTO-01 — Notion sync manifest (repo, pending)

**Purpose:** the exact update that must be applied to the Notion AUTO-01 task/page once Notion
access is available. Repo authority remains [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md)
and the architecture contract [PAPER_AUTOMATION.md](../architecture/PAPER_AUTOMATION.md).

**Sync status:** `NOTION_SYNC_BLOCKED` — Notion is not reachable from the development machine
in this session. No Notion write was attempted or claimed. This manifest is the intended
update, now carrying the accepted SHA and PR from the merged integration; the operational
runbook is
[AUTONOMOUS_PAPER_OPERATIONS_RUNBOOK.md](../operations/AUTONOMOUS_PAPER_OPERATIONS_RUNBOOK.md).

## Fields to set

| Field | Value |
| --- | --- |
| **Initiative** | `AUTO-01` — Autonomous market intelligence and internal Paper trading operations (existing initiative; **no new initiative is created and no unrelated priority is reordered**) |
| **Implementation state** | `IMPLEMENTED` — one server-owned controller over the existing Screener, AI, Action Decision, risk, Paper and ledger authorities |
| **Accepted Git SHA** | `bb46e716ad5d0b2367322954cc05cc540ed88ca3` — merge commit of the integration PR on `origin/main`; its tree equals the accepted head tree `52bf88ad` (verified `063b7840…`) |
| **Integration PR** | [#496](https://github.com/AdamEddahmouni/market-trading-platform/pull/496), merged normally (merge commit, no administrative bypass); all protected CI checks green before merge |
| **Pre-integration base** | `39ca4b5a1301b61adf0a91ddb1efafba3a84456d` (`origin/main` at the recovery checkpoint; PR #495 merged) |
| **Software acceptance evidence** | Focused AUTO-01 suites: 117 backend (66 trading-correctness, 35 policy, 8 universe-run, 8 route-policy) and 12 UI. `validate changed` 6,565 tests / 36 skipped / 0 failures / 0 errors; **`validate full` 8,728 tests / 59 skipped / 0 failures / 0 errors**; `imp.py closure` exit 0 (`artifacts/developer-workflow/closure-report.json`). Full UI suite 1,440 tests across 183 files, typecheck and production build clean; formatting, lint, diff-whitespace and the 301-file documentation-link check pass. The one FULL error seen before closure was a sparse-checkout gap (`short-squeeze-core/apps` absent), reproduced identically at the base commit and fixed by materializing the tracked path. |
| **Operating mode** | `INTERNAL_SIMULATION` / `PAPER_ONLY`. Live is observational only; `LIVE-001` and every Live gate unchanged. |
| **Paper-only restrictions** | No broker, live-order or gateway module is imported by the controller. Its only submit call is the canonical Paper route under the same lock as `POST /paper/orders`. The cancel route's broker branch is refused before it is reached, including on Emergency Stop. |
| **Risk / authorization requirements** | A complete owner policy with no defaults, plus a **separate recorded arming** (`ARM_PAPER_ONLY_AUTOMATION`), bound to one account, one experiment and the ledger risk-policy hash. Route capabilities: reads `audit.read`; arm/start/resume `paper.order.submit`; configure/disarm/pause/stop/emergency-stop `state.write`. The governed ledger and deterministic-risk limits stay in force underneath and are not replaced by the policy. The `operator` field on an arming request is informational metadata, not authorization. |
| **Runtime deployment state** | Accepted source synchronized to the portable runtime from the accepted git objects: 186 files (108 created, 78 updated), 78 preimages preserved under `destination-tests/20261012-auto01/previous/`, every destination hash verified against the accepted objects with 0 mismatches, and a repeat comparison showing 0 remaining differences. Runtime UI rebuilt from the synchronized source (exit 0, identical asset hashes and bundle metrics); the synchronized source imports under the launcher `PYTHONPATH` and its route/capability invariants hold. **Service restart pending — it is the one remaining action, and it is the owner's:** the backend running at `127.0.0.1:8766` still serves the pre-sync code (`GET /paper/automation/status` → `UI_ROUTE_NOT_FOUND`), so a `STOP_PORTABLE` / `START_PORTABLE` cycle is required before the workstation serves AUTO-01. Nothing was armed and no vendor session was terminated. |
| **Known empirical limitations** | Unattended behaviour against live providers and a real model in a regular session is `NOT_OBSERVED`; the running workstation predates the synced source, so live observational acceptance of the automation surface is `NOT_OBSERVED` as well. No liquidation rule exists (daily-loss halt, session close and Emergency Stop do not flatten positions). No entry without a governed `OpportunityV1`. Half-day session closes are not modelled. Two earlier known behaviours are addressed in this integration: a superseded generation can no longer latch or report over the run that replaced it (recorded as `EMERGENCY_LATCH_SUPERSEDED`, covered by a regression test), and the last evaluating cycle's blockers are carried into a closed-session read so a simultaneous budget, data or risk block stays visible. |

## What must NOT be recorded

- Do not record the working tree, a branch tip, or a snapshot commit as the accepted SHA.
- Do not record `PAPER_AUTOMATION` as active, armed, or deployed for unattended operation.
- Do not record any test-selected setting (limits, capital, cadence, models) as an owner
  decision.
- Do not record simulated P&L as a performance result or a durable edge.
- Do not create a second AUTO-01 initiative or move other priorities.

## Upgrade path

When Notion is reachable: read the existing AUTO-01 task/page, compare its stated status with
the fields above, and update only the fields that differ. The accepted SHA and integration PR
are now recorded, so the integration fields can be written. Do not mark the task Done while the
workstation restart is outstanding: record implementation-complete and integrated, one pending
runtime restart, and `NOT_OBSERVED` for live-provider unattended behaviour.
