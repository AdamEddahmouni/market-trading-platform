# Campaign supervision and heartbeat (RTH15-09)

**Status:** Implemented on this branch as a **minimal** IMP-owned supervisor.
**Evidence class for new tests:** `SOFTWARE_CONTROLLED_EVIDENCE`.
**Does not** mark RTH15-09 empirically complete. **Does not** rewrite September 22
outage evidence. September 22 Segment B gap `14:26:00.749`–`14:57:27.624` ET
remains `NOT_OBSERVED`; root cause remains **UNKNOWN**.

## What this is

Durable ownership + heartbeat/progress proof for an **armed** observational
campaign, built on existing contracts:

- loopback service liveness ([`service_liveness.py`](../../src/market_platform_foundation/platform/operator_diagnostics/service_liveness.py))
- launcher process identity ([`local_launcher.py`](../../tools/platform/local_launcher.py), [`service_health.py`](../../tools/platform/service_health.py))
- operator diagnostics snapshot ([`snapshot.py`](../../src/market_platform_foundation/platform/operator_diagnostics/snapshot.py))
- BUILD 32 heartbeat stale semantics ([OPERATIONAL_RELIABILITY_SLO_DR_V1.md](OPERATIONAL_RELIABILITY_SLO_DR_V1.md))

It is **not** a full control center, admin console, or parallel liveness architecture.

## Who owns an armed campaign

The **IMP campaign supervisor** owns an armed campaign. Ownership is durable under
`{IMP_STATE_DIR}/campaign-supervision/`:

| File | Contents |
|------|----------|
| `ownership.json` | campaign ID, runtime SHA, supervisor PID/identity, child PIDs + create times + parent PID when known, safe command fingerprint (no secrets), arm timestamp, observation-window ID, expected poll cadence, expected next cycle, state directory, arm status, segment ID |
| `heartbeat.json` | last heartbeat, last successful poll/progress, expected next heartbeat/poll, cadence, stale threshold, application readiness flags |
| `outages.jsonl` | additive outage intervals |

`ARMED_RUNNING` is an **arm** token, not proof of liveness.

## How processes launch / terminal independence

**Selected mechanism (tested):** IMP-owned supervisor. Spawn prefers Windows
`CREATE_BREAKAWAY_FROM_JOB` + `CREATE_NEW_PROCESS_GROUP` + `CREATE_NO_WINDOW`
and falls back without breakaway on `OSError`. Software-controlled shell-exit
proof on this host used the no-breakaway fallback because breakaway can stall
under some parent job objects — still **not** `Start-Process -WindowStyle Hidden`.
`DETACHED_PROCESS` was tested and omitted (aborted child Python processes).
POSIX: `start_new_session`. Helper:
[`tools/platform/detached_process.py`](../../tools/platform/detached_process.py).
Platform launcher spawn reuses these flags.

**Not assumed durable:** `Start-Process -WindowStyle Hidden`. That path is
explicitly **not** labeled terminal-independent.

CLI:

```powershell
python tools/platform/campaign_supervisor.py mechanism
python tools/platform/campaign_supervisor.py arm --state-dir $env:IMP_STATE_DIR --campaign-id ... --observation-window-id ...
python tools/platform/campaign_supervisor.py run --state-dir $env:IMP_STATE_DIR --auto-poll
python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR --rth-close
```

## Heartbeat / progress / stale detection

Progress tokens (campaign supervision): `HEALTHY`, `STARTING`, `STALE`,
`PROCESS_DEAD`, `APPLICATION_UNREADY`, `SESSION_UNAVAILABLE`, `NOT_APPLICABLE`,
`UNKNOWN`.

Fail closed when arm is `ARMED_RUNNING` and any of:

- required process dead
- heartbeat/progress older than stale threshold
- expected cycle elapsed without progress
- bound port / process without application progress

Operator diagnostics surfaces this under
`sections.runtime.runtime_resilience.campaign_supervision` and
`readiness_vs_liveness.liveness.campaign_supervision`. Severity becomes
`ACTION_REQUIRED` for stale/dead armed campaigns.

## Liveness vs data freshness

Healthy campaign heartbeat **does not** mean:

- fresh provider data
- valid Opportunity Engine output
- strategy quality / Item 9 calibration
- market evidence

Those remain separate surfaces (`service_liveness` market-data view, readiness
freshness, opportunity summary).

## Outage classification / NOT_OBSERVED / recovery

Outage records are **additive**. Missed evidence is `NOT_OBSERVED`. Root cause
defaults to `UNKNOWN` (no false narrative). No synthetic polls. No backfill.
Deliberate recovery (`recover`) refreshes PIDs while preserving original arm
timestamp, segment ID, runtime SHA, and existing outage gaps — it does **not**
silently create Segment C.

Automatic restart is **not** required. Prefer detect → fail visible → deliberate
recovery.

## Shutdown

- `CLEAN_SHUTDOWN` / `RTH_CLOSE_SHUTDOWN` → progress `NOT_APPLICABLE` (not an outage)
- Do not misclassify intentional RTH close as PROCESS_DEAD/STALE outage

## Execution safety

`execution_authority=BLOCKED`, `execution_mode=NONE`, `allows_network_submit=false`,
`BUILD28_LIVE_SUBMIT_FORBIDDEN` remains enforced by existing preflight.

## Evolution path (without building the control center now)

This minimal supervisor can later grow into an IMP control plane by adding
governed start/stop/state, job inventory, unified liveness/heartbeat, outage
history, and recovery workflows — **reusing** these ownership/heartbeat/outage
files and diagnostics composition rather than inventing a second stack.

## Historical September 22

Do **not** rewrite Segment A/B manifests or claim the outage was prevented.
Software-controlled acceptance proves the mechanism; it is not market proof and
does not reproduce the September 22 root cause (still **UNKNOWN**).
