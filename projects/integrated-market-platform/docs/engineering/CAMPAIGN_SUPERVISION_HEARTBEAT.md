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

## How processes launch / parent-exit survival

**Default / tested spawn flags (Windows):** `CREATE_NEW_PROCESS_GROUP |
CREATE_NO_WINDOW`. Platform launcher and campaign supervisor use these by
default. Helper: [`tools/platform/detached_process.py`](../../tools/platform/detached_process.py).

**Proven (software-controlled):** a supervisor spawned with those default flags
stays alive and heartbeats after a Python `Popen` parent calls `SystemExit(0)`
(parent-process exit). Evidence class: `SOFTWARE_CONTROLLED_EVIDENCE`.

**UNPROVEN on this host:**

- Windows job-kill / terminal-independent durability
- `CREATE_BREAKAWAY_FROM_JOB` survival (opt-in only; may hang or be denied under
  some parent job objects)
- `Start-Process -WindowStyle Hidden` as a durable path (explicitly rejected)
- `DETACHED_PROCESS` (tested; aborted child Python processes — not used)

**Product guarantee:** fail-visible detection when the supervisor/heartbeat is
dead or stale (`ARMED_RUNNING` alone is never HEALTHY) — **not** a proven
detached OS service or terminal-independent host.

POSIX uses `start_new_session` (not claimed as full terminal-detach proof).

CLI:

```powershell
python tools/platform/campaign_supervisor.py mechanism
python tools/platform/campaign_supervisor.py environment-preflight --state-dir $env:IMP_STATE_DIR --campaign-id ... --observation-window-id ...
python tools/platform/campaign_supervisor.py arm --state-dir $env:IMP_STATE_DIR --campaign-id ... --observation-window-id ...
python tools/platform/campaign_supervisor.py run --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py poll-loop --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR --rth-close
```

**Environment preflight (before ARM):** fails closed when required API entrypoint or
`ui/node_modules` (operator UI dependency readiness) is absent. UI remains an
**optional runtime role** for observation ingestion; missing UI deps are still
fail-visible before arm so `:5173` cannot silently never start. Required
observation roles: `supervisor`, `poller`, `api`. Optional operator display: `ui`.

**Durability invariants (2026-09-23):**

- `register-child` / `recover` must **not** clobber `ownership.supervisor_pid`
  with a one-shot shell PID (that produced false `PROCESS_DEAD` on RTH-OBS-NEWS-20260923).
- Status/heartbeat evaluation injects launcher-grade `service_health.process_alive`
  (Windows `OpenProcess`); src fallback avoids unreliable `os.kill(pid, 0)`.
- Missing required roles (e.g. unregistered poller) are `PROCESS_DEAD`.
- `poll-loop` is the long-lived SOFTWARE_CONTROLLED poller role; one-shot ingress
  scripts must not be registered as the durable poller.

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

## Observation start gate (campaign observation readiness)

ONE read model composes supervision + platform service liveness + provider /
ingress signals into a fail-visible pre-RTH gate:

- Module: `platform/operator_diagnostics/campaign_observation_readiness.py`
- Diagnostics: `sections.campaign_observation_readiness` on `GET /operator/diagnostics`
- CLI: `python tools/platform/campaign_supervisor.py readiness --state-dir $env:IMP_STATE_DIR`
- **ARM OBSERVATION** = existing `campaign_supervisor.py arm` (execution stays
  `BLOCKED`; never **GO LIVE**). Operator Control shows the gate and CLI arm
  command; it does **not** POST a parallel UI arm path.

Fail-loud: intended campaign today + RTH soon/open + `NOT_ARMED` →
`CAMPAIGN_NOT_ARMED_BEFORE_RTH` blocking alert (`ACTION_REQUIRED`).

Optional intent declaration (env or `{IMP_STATE_DIR}/campaign-supervision/observation-intent.json`):
`campaign_id`, `intended_date_et`, `frozen`, `runtime_sha`, `observation_window_id`.

## Historical September 22

Do **not** rewrite Segment A/B manifests or claim the outage was prevented.
Software-controlled acceptance proves the mechanism; it is not market proof and
does not reproduce the September 22 root cause (still **UNKNOWN**).
