# AUTO-01 — Notion sync manifest (repo, pending)

**Purpose:** the exact update that must be applied to the Notion AUTO-01 task/page once Notion
access is available. Repo authority remains [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md)
and the architecture contract [PAPER_AUTOMATION.md](../architecture/PAPER_AUTOMATION.md).

**Sync status:** `NOTION_SYNC_BLOCKED` — Notion is not reachable from the development machine
in this session. No Notion write was attempted or claimed. This manifest is the intended
update; the operational runbook is
[AUTONOMOUS_PAPER_OPERATIONS_RUNBOOK.md](../operations/AUTONOMOUS_PAPER_OPERATIONS_RUNBOOK.md).

## Fields to set

| Field | Value |
| --- | --- |
| **Initiative** | `AUTO-01` — Autonomous market intelligence and internal Paper trading operations (existing initiative; **no new initiative is created and no unrelated priority is reordered**) |
| **Implementation state** | `IMPLEMENTED` — one server-owned controller over the existing Screener, AI, Action Decision, risk, Paper and ledger authorities |
| **Accepted Git SHA** | `PENDING_OWNER_INTEGRATION` — to be filled by the coordinator from the merged AUTO-01 PR merge commit on `origin/main` (do not fill from the working tree or a branch tip) |
| **Integration PR** | `PENDING_OWNER_INTEGRATION` |
| **Pre-integration base** | `39ca4b5a1301b61adf0a91ddb1efafba3a84456d` (`origin/main` at the recovery checkpoint; PR #495 merged) |
| **Software acceptance evidence** | Focused AUTO-01 suites: 106 backend (35 policy, 8 universe, 63 trading-correctness) and 12 UI. Pre-fix affected validation 6,565 tests / 36 skipped / 0 failures; post-fix 6,567 / 36 / 0. Full UI suite 1,439 tests across 183 files. UI typecheck, formatting, lint and documentation-link checks pass. **FULL closure validation: `PENDING` at the time of writing.** |
| **Operating mode** | `INTERNAL_SIMULATION` / `PAPER_ONLY`. Live is observational only; `LIVE-001` and every Live gate unchanged. |
| **Paper-only restrictions** | No broker, live-order or gateway module is imported by the controller. Its only submit call is the canonical Paper route under the same lock as `POST /paper/orders`. The cancel route's broker branch is refused before it is reached, including on Emergency Stop. |
| **Risk / authorization requirements** | A complete owner policy with no defaults, plus a **separate recorded arming** (`ARM_PAPER_ONLY_AUTOMATION`), bound to one account, one experiment and the ledger risk-policy hash. Route capabilities: reads `audit.read`; arm/start/resume `paper.order.submit`; configure/disarm/pause/stop/emergency-stop `state.write`. The governed ledger and deterministic-risk limits stay in force underneath and are not replaced by the policy. The `operator` field on an arming request is informational metadata, not authorization. |
| **Runtime deployment state** | `PENDING_OWNER_INTEGRATION` — portable SSD runtime synchronization and restart verification are outstanding; nothing has been deployed from this work. |
| **Known empirical limitations** | Unattended behaviour against live providers and a real model in a regular session is `NOT_OBSERVED`. No liquidation rule exists (daily-loss halt, session close and Emergency Stop do not flatten positions). No entry without a governed `OpportunityV1`. Half-day session closes are not modelled. The controller self-latch can be lost if a disarm → configure → re-arm → start races the failing cycle, and a non-blocked primary status can coexist with open blockers (both stated in the architecture doc's Limitations). |

## What must NOT be recorded

- Do not record the working tree, a branch tip, or a snapshot commit as the accepted SHA.
- Do not record `PAPER_AUTOMATION` as active, armed, or deployed for unattended operation.
- Do not record any test-selected setting (limits, capital, cadence, models) as an owner
  decision.
- Do not record simulated P&L as a performance result or a durable edge.
- Do not create a second AUTO-01 initiative or move other priorities.

## Upgrade path

When Notion is reachable: read the existing AUTO-01 task/page, compare its stated status with
the fields above, and update only the fields that differ. If the accepted SHA is still
`PENDING_OWNER_INTEGRATION`, leave the status at implementation-complete and note the pending
integration rather than marking the task Done.
