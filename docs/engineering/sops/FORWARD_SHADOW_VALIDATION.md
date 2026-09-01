# SOP — Forward Shadow Validation (P6 Shadow Run 1)

**Status:** Operator procedure  
**Protocol:** [P6_SHADOW_RUN_1_PROTOCOL.md](../P6_SHADOW_RUN_1_PROTOCOL.md)

## Distinction (mandatory)

| Mode | Meaning | Forward evidence? |
|------|---------|-------------------|
| Fixture validation | Offline unittest/CI replay | **No** — infrastructure proof only |
| Historical replay | Deterministic reproduction from sealed captures | **No** — replay ≠ prospective |
| True forward shadow | Observations collected after run `open` from live observational ingress | **Yes** — `ACTUAL_FORWARD` |

Never label fixture or replay results as forward validation.

## Prerequisites

1. Clean git worktree at pinned HEAD (tracked mutations block `open`).
2. `validate.py full` green; pin receipt SHA-256 for preflight.
3. Moomoo OpenD running locally; observational runtime health receipt pinned.
4. Environment:
   - `IMP_LIVE_OBSERVATIONAL=1`
   - `IMP_MOOMOO_LIVE=1`
   - `IMP_SHADOW_RECORDING=0` during preflight and `open`
   - Execution gates **disabled** (`IMP_LIVE_EXECUTION`, `IMP_PAPER_EXECUTION`, etc.)
5. Auth: `LOOPBACK_TRUST` default; `ENFORCED` mode requires principal with observational access (TD-005).

## Canonical CLI

```powershell
$env:PYTHONPATH='src'
$store = ".local/state/shadow"   # default via run_shadow_run store_root_default()
```

### 1. Preflight (no side effects)

```powershell
.venv\Scripts\python.exe tools/research/run_shadow_run.py preflight `
  --instrument BIYA `
  --first-session 2026-09-02 `
  --holidays NONE `
  --early-closes NONE `
  --capture-id CAP-BIYA-SR1-<session> `
  --expected-head <40-char-git-sha> `
  --validation-evidence <path-to-full-validation.json> `
  --validation-sha256 <sha256> `
  --runtime-health-evidence <path-to-moomoo-health.json> `
  --runtime-health-sha256 <sha256> `
  --report artifacts/shadow-run-1/preflight-report.json
```

Status `READY` emits `opening_handoff.argv` only — preflight never opens a run.

### 2. Open run (preregister manifest)

```powershell
.venv\Scripts\python.exe tools/research/run_shadow_run.py open `
  --instrument BIYA `
  --first-session 2026-09-02 `
  --holidays NONE `
  --early-closes NONE `
  --capture-id CAP-BIYA-SR1-<session>
```

Record returned `run_id` and `manifest_hash`.

### 3. Arm recording

Restart observational runtime with:

```powershell
$env:IMP_SHADOW_RECORDING='1'
$env:IMP_SHADOW_RUN_ID='<run_id>'
```

### 4. Collect observations

Runtime admits trades → recorder writes append-only decisions. Inspect:

```powershell
.venv\Scripts\python.exe tools/research/run_shadow_run.py status --run-id <run_id>
```

### 5. Close

```powershell
.venv\Scripts\python.exe tools/research/run_shadow_run.py close --run-id <run_id>
# or --force with --reason when stopping rule unmet but aborting
```

### 6. Label matured horizons

```powershell
.venv\Scripts\python.exe tools/research/run_shadow_run.py label-due --run-id <run_id>
```

Repeat until `FULLY_LABELED` or capture gaps documented.

### 7. Report and acceptance

```powershell
.venv\Scripts\python.exe tools/research/run_shadow_run.py report --run-id <run_id>
.venv\Scripts\python.exe tools/research/run_shadow_run.py acceptance `
  --run-id <run_id> `
  --matrix-out artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json `
  --validation-green
```

## Resume behavior

- Same `run_id` + compatible manifest: `open` verifies without rewriting contract.
- Append-only decisions; duplicate buckets are silent no-ops.
- Material code/config change: new `run_id` required.

## Incident handling

1. Preserve pre-fix evidence.
2. Record defect in completion record / WORK_LOG.
3. Do not mutate historical decision rows.
4. Version protocol or start new run segment if evidence boundary compromised.

## Artifact locations

| Artifact | Path |
|----------|------|
| Protocol | `artifacts/shadow-run-1/P6_SHADOW_RUN_1_PROTOCOL.json` |
| Source audit | `artifacts/shadow-run-1/SOURCE_AVAILABILITY_AUDIT.json` |
| Acceptance matrix | `artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json` |
| Experiment store | `.local/state/shadow/experiment.sqlite3` |
| Captures | `.local/state/shadow/captures/*.jsonl` |

## Blockers (current baseline)

- Moomoo OpenD not configured → forward observations **blocked**; machinery remains resumable.
- ES data (ADR-DATA-001) excluded — do not fabricate ES forward evidence.
- TD-004 Moomoo paper real-wire separate from shadow observational path.
