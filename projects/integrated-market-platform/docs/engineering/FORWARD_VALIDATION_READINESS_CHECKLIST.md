# Forward-Validation Readiness Checklist

**Owner:** Platform docs (`docs/platform/` + this file)
**Status:** Checklist — prerequisite map for reopening forward-validation campaigns. No
campaign listed here is currently active, and **this document grants no execution
authority**; each row is a gate that must be re-opened deliberately under the owning
protocol.
**Source:** [Hardening plan P0-1](../../../../docs/reviews/2026-09-04-hardening-task-plan.md)

## How to use

Every candidate forward-validation campaign is one row. To reopen a campaign, every
prerequisite in its row must be `✅` (or carry an explicit, recorded exception), then the
campaign must produce its listed acceptance artifacts for the record to count. A reviewer
can tell in one page which connectivity / env / credential / fixture / rollback
prerequisites block each campaign *today* and what the campaign must produce.

Legend: `❌` blocked today · `🟡` exists but unexercised / needs verification at reopen ·
`✅` present and previously exercised.

## Campaign readiness

### P6 Shadow Run 1 (`artifacts/shadow-run-1/`, protocol: `docs/engineering/P6_SHADOW_RUN_1_PROTOCOL.md`)

| Prerequisite | State | Notes |
|---|---|---|
| Instrument + predictor frozen | ✅ | BIYA; `nss-direction-v1` frozen constants in protocol JSON |
| Provider connectivity (Moomoo observational) | 🟡 | `IMP_LIVE_OBSERVATIONAL=1` + `IMP_MOOMOO_LIVE=1`; OpenD TCP must be live — verify at reopen |
| Env vars / credentials | 🟡 | Provider env set must be re-verified; never commit secrets (`.env` gitignored) |
| Fixture / store state | 🟡 | `artifacts/shadow-run-1/store/*.sqlite3` historical artifacts preserved; fresh run store required |
| No-execution invariant | ✅ | Protocol binds Execution = NONE |
| Rollback / stop criteria | ✅ | Protocol defines session count + label horizon |
| Acceptance artifacts | ❌ | P6 acceptance matrix (`P6_ACCEPTANCE_MATRIX.json`) + run manifest + validation receipt must be produced for the new run |
| **Current blocker** | ❌ **DEFERRED** | `PROGRAM_STATUS.md` row: no active forward-observation campaign; historical run preserved |

### EVIDENCE-01C (real-provider operational shakedown; spec precedent `docs/engineering/EVIDENCE_01B_REAL_PROVIDER_RUNTIME_OPERATIONALIZATION.md`)

| Prerequisite | State | Notes |
|---|---|---|
| Real-provider adapter exercised | ❌ | No real-provider shakedown currently active |
| Connectivity (provider + gateway) | ❌ | Not established for 01C |
| Env vars / credentials | 🟡 | Provider env set must be verified at reopen |
| Fixture state | 🟡 | Admitted replay fixture + operationalization paths exist (`EVIDENCE01_*` artifacts under `artifacts/forward-qualification/`) |
| Rollback / isolation | 🟡 | Runtime operationalization exists (01B); exercise again for 01C |
| Acceptance artifacts | ❌ | Accepted outcome record (`EVIDENCE-01C`) with operational-acceptance report |
| **Current blocker** | ❌ **DEFERRED** | `PROGRAM_STATUS.md` + REBASE-00 limitation 6; no accepted outcome exists |

### Live canary (`docs/engineering/LIMITED_LIVE_CANARY_V1.md`, `SUPERVISED_LIVE_CANARY_OPERATIONS_V1.md`)

| Prerequisite | State | Notes |
|---|---|---|
| Canary policy + runner | 🟡 | `src/market_platform_foundation/intelligence/live_canary/` exists; **never executed** end-to-end |
| Mock transport exercised | 🟡 | `live_canary/submission.py` mock transport exists; real transport unexercised |
| Env vars / credentials | ❌ | Broker/live credentials must be provided at reopen |
| Broker inventory / gate state | 🟡 | `live_execution_safety/broker_inventory.py` + BUILD28/29 artifacts exist |
| Rollback | 🟡 | Deployment governance (`live_canary/release_governance/`) present; exercise required |
| Acceptance artifacts | ❌ | Canary run manifest + evidence (`BUILD29_CANARY_*`) for the new run |
| **Current blocker** | ❌ **NOT RUN** | PROGRAM_STATUS: accepted production live broker transport `ABSENT`; live gates closed |

### Tradier sandbox wire (paper/broker adapter to Tradier sandbox)

| Prerequisite | State | Notes |
|---|---|---|
| Broker adapter + contract | 🟡 | Broker abstractions + mock + paper transports exist; real-wire adapters unexercised |
| Sandbox account / credentials | ❌ | Tradier sandbox credentials not present locally |
| Connectivity to sandbox | ❌ | Untested end-to-end |
| Reconciliation foundations | ✅ | Paper broker submission/poll/reconcile seams + reconciliation machinery exist |
| Rollback | 🟡 | Paper ledger is authoritative; verify adapter cannot reach live keys in sandbox mode |
| Acceptance artifacts | ❌ | Wire-contract record + sandbox round-trip evidence |
| **Current blocker** | ❌ | Credentials + first end-to-end sandbox exercise outstanding |

### Moomoo OpenD shakedown (`docs/engineering/`, TD-004)

| Prerequisite | State | Notes |
|---|---|---|
| OpenD TCP available | ❌ | `TECH_DEBT.md` TD-004: **OpenD TCP unavailable** (hard blocker) |
| Adapter / capability map | 🟡 | Provider capability + broker inventory exist |
| Env vars / credentials | 🟡 | Moomoo env vars must be verified at reopen |
| Fixture / dry-run evidence | ✅ | `BUILD28_DRY_RUN_EVIDENCE.json` + execution-safety artifacts exist |
| Rollback | 🟡 | Execution-safety gate spec present; re-exercise |
| Acceptance artifacts | ❌ | Wire contract recorded when OpenD exercised (TD-004 close criterion) |
| **Current blocker** | ❌ | OpenD TCP unavailable (TD-004, `OPEN_D_NOT_INSTALLED`) |

## Cross-cutting prerequisites (apply to every row)

- [ ] Env vars and credentials are provided via the private env path (never committed); each
      campaign lists the exact variables it needs before opening.
- [ ] Fixture state is pinned (admitted replay fixtures; no unadmitted live captures feed
      training or promotion — see provider admission guard, hardening plan P1-5).
- [ ] Rollback path is exercised in the target environment before the campaign begins.
- [ ] The campaign's acceptance artifacts are named before the run (preregistered).
- [ ] No execution authority is claimed by this checklist or by any dry-run artifact.

## Related

- `docs/platform/PROGRAM_STATUS.md` — canonical status incl. EVIDENCE-01C / P6 rows
- `docs/engineering/P6_SHADOW_RUN_1_PROTOCOL.md`
- `docs/engineering/LIMITED_LIVE_CANARY_V1.md`, `docs/engineering/SUPERVISED_LIVE_CANARY_OPERATIONS_V1.md`
- `docs/engineering/TECH_DEBT.md` (TD-004), `docs/engineering/CHAMPION_CHALLENGER_PROMOTION_V1.md`
