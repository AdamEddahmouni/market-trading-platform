# Deployment, Release Engineering & Change Control (BUILD 34)

> **BUILD 34 packages and deploys the already-qualified supervised system. Deployment may change where the system runs, but it may not silently change what the system is authorized to do.**

## Core Principle

Deployment is separate from runtime authorization:

```text
Release artifact          ≠  RuntimeActivationV1
RuntimeActivationV1       ≠  LiveExecutionAuthorizationV1
Deployment success        ≠  Session authorization
Service healthy           ≠  Order authorization
Credentials present       ≠  Live enabled
```

## Build-Once / Promote-Same-Artifact

```text
exact accepted source → release bundle → TEST qualification → promote same artifact → SUPERVISED_LIVE
```

Promotion changes **environment configuration only**. The executable artifact hash must remain identical across promotion. Rebuilding per environment is prohibited.

Release identity uses `REL-{sha256}` derived from:

- exact Git commit SHA
- source tree hash (tracked files at HEAD)
- dependency lock hash (`phase0-dependency-lock.json`)
- semantic bundle content hash

Dirty source trees **cannot** produce accepted releases.

## Environments

| Environment | Purpose | Broker | Persistence | Execution mode | Authority |
|-------------|---------|--------|-------------|----------------|-----------|
| LOCAL_DEV | Developer workstation | NONE | local-dev | OFFLINE | NONE |
| TEST | Automated qualification | TEST | test | PAPER | PAPER |
| QUALIFICATION | Integration qualification | PAPER | qualification | PAPER | OBSERVATION_ONLY |
| SUPERVISED_PILOT | BUILD 33 pilot | SUPERVISED_LIVE | supervised-pilot | SUPERVISED_LIVE | SUPERVISED_LIVE |
| SUPERVISED_LIVE | Human-supervised live | SUPERVISED_LIVE | supervised-live | SUPERVISED_LIVE | SUPERVISED_LIVE |

Unknown environment kinds fail closed. LIVE is never inferred from credential presence.

## Config vs Policy

Deployment configuration references canonical policy objects by ID. Environment variables and deployment config **cannot** override:

- model thresholds
- risk limits
- opportunity thresholds
- calibration parameters
- provider-selection thresholds
- pilot caps

## Secret Boundary

Versioned artifacts contain **symbolic secret references only** (`ENV:`, `OS:`, `VAULT:`). Actual secrets are runtime-only. Secret presence does not alter execution authority.

## Service Supervision

Service graph (fixture supervisor for qualification):

1. `operator-api` — critical
2. `market-data-runtime` — depends on operator-api
3. `intelligence-runtime` — depends on market-data-runtime
4. `reconciliation-worker` — depends on intelligence-runtime; critical

**Process RUNNING ≠ live READY.** After restart, live execution readiness remains false until reconciliation prerequisites pass. Crash loops are detected after 5 restarts.

## Deployment Canary

Deployment canary ≠ trading canary. Default: zero real orders.

Canary exercises:

- service health (blocked readiness)
- read-only provider observations
- read-only broker/account state
- reconciliation
- operator control plane

## Migration

Current schema: `intelligence-v1`. Destructive migrations require verified backup. Rollback compatibility must be assessed before deployment.

## Rollback

Code rollback ≠ order rollback ≠ fill rollback. Broker truth survives software rollback. Rollback startup is **BLOCKED** until broker reconciliation and operator review. No pending order replay.

## Change Control

All deployments require an approved `DeploymentChangeRequestV1`. Config-only changes are auditable via configuration hash. Manual deployed-file edits are detected as drift.

## Human-Control Preservation

BUILD 34 does not modify BUILD 29–30 requirements:

- human session authorization required
- per-order confirmation required
- manual incident resume required
- kill switch unchanged

## BUILD 35 Boundary

A future BUILD 35 may focus on release lifecycle governance, versioned production releases, environment promotion policy, operational change windows, and scheduled release qualification. It must **not** automatically remove human live-execution controls.

## Module Location

```text
src/market_platform_foundation/intelligence/live_canary/deployment/
```

Operator API: `GET /canary/deployment` (read-only, `DEPLOYMENT_READ_ONLY` authority boundary).

## Known Limitations

See `artifacts/deployment-qualification/BUILD34_KNOWN_LIMITATIONS.md`.
