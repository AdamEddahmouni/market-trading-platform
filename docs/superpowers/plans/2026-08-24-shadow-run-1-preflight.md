# Shadow Run 1 Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible, local-only, fail-closed `preflight` command and JSON report that verifies the frozen BIYA Shadow Run 1 section-14 prerequisites and emits, but never executes, the exact `open` handoff.

**Architecture:** Extend the existing `tools/research/run_shadow_run.py` operator CLI with pure parsing/check functions and a `cmd_preflight` orchestrator. The preflight consumes pinned local validation and runtime-health receipts, inspects Git and environment state without network access, validates the explicit session calendar, and returns a canonical report whose `opening_handoff.argv` is the only path toward `open`; it never imports or calls experiment-store opening code.

**Tech Stack:** CPython 3.11 standard library only, `argparse`, `hashlib`, `json`, `pathlib`, `subprocess`, `unittest`.

## Global Constraints

- Preserve the frozen protocol and constants in `docs/superpowers/specs/2026-08-23-platform-p6-shadow-run-1-design.md`.
- Preflight performs no socket, HTTP, provider, SDK, runtime-start, or experiment-store operation.
- Missing, malformed, stale, mismatched, dirty, unpinned, unsafe, or ambiguous input blocks readiness.
- Require instrument `BIYA`, a 40-hex expected HEAD, a clean porcelain-v1 worktree including untracked paths, and evidence SHA-256 pins.
- Accept only authoritative validation JSON with `mode=full`, `status=passed`, zero failures/errors, no interruption, no unrun suites, and the exact offline-full suite set from the governed validation manifest.
- Accept only a pinned local Moomoo health receipt reporting `READY`, localhost OpenD reachability, a working quote context, and observational readiness.
- Require `IMP_LIVE_OBSERVATIONAL=1` and `IMP_MOOMOO_LIVE=1`; require `IMP_SHADOW_RECORDING`, live execution, internal simulation, and paper execution gates to be disabled.
- Require explicit holiday and early-close declarations (`NONE` or comma-separated ISO dates), reject overlap, reject an ineligible first session, and freeze the resulting eight-session list.
- The report may be written atomically to a local path and is always printed as canonical JSON.
- Do not edit `tools/validation_manifest.json`.

---

### Task 1: Focused preflight behavior tests

**Files:**
- Modify: `tests/platform/test_shadow_run1_cli.py`

**Interfaces:**
- Consumes: existing `run_shadow_run` module and `cmd_open` behavior.
- Produces: desired `cmd_preflight(args: dict[str, Any]) -> tuple[int, dict[str, Any]]` contract.

- [ ] **Step 1: Write failing tests**

Add fixture helpers that create canonical validation and runtime-health JSON receipts, calculate their SHA-256 values, and inject deterministic Git/environment state. Test one ready case and focused blocked cases for a dirty/unpinned tree, non-full or incomplete validation, digest mismatch, armed recording, unsafe execution gates, unhealthy/non-local runtime evidence, and ineligible/ambiguous calendar inputs. In the ready test, patch `build_manifest_body` and `open_experiment_store` to raise if called, then assert:

```python
self.assertEqual(rc, 0)
self.assertEqual(report["status"], "READY")
self.assertEqual(report["protocol"], "SHADOW_RUN_1_BIYA_FROZEN")
self.assertEqual(report["opening_handoff"]["argv"][3], "open")
self.assertFalse(report["side_effects"]["network_calls"])
self.assertFalse(report["side_effects"]["run_opened"])
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.platform.test_shadow_run1_cli -v
```

Expected: fail because `cmd_preflight` and the `preflight` parser do not exist.

---

### Task 2: Local-only fail-closed preflight command/report

**Files:**
- Modify: `tools/research/run_shadow_run.py`
- Test: `tests/platform/test_shadow_run1_cli.py`

**Interfaces:**
- Consumes: `--expected-head`, `--validation-evidence`, `--validation-sha256`, `--runtime-health-evidence`, `--runtime-health-sha256`, `--instrument`, `--first-session`, `--holidays`, `--early-closes`, `--capture-id`, `--store-root`, and optional `--report`.
- Produces: `cmd_preflight(args) -> (0, READY report)` or `(2, BLOCKED report)` and an exact `opening_handoff.argv` only when every check passes.

- [ ] **Step 1: Implement minimal pure helpers**

Add helpers for strict SHA/date/declaration parsing, canonical JSON reading, SHA-256 calculation, expected offline-full suite extraction from `tools/validation_manifest.json`, validation-receipt checks, runtime-health checks, environment-gate checks, strict Git state checks, PowerShell display quoting, and atomic report writing. Each helper returns structured check details; exceptions become blocking check results rather than permissive fallbacks.

- [ ] **Step 2: Implement `cmd_preflight`**

Evaluate every prerequisite without early side effects, collect named checks, set `status` to `READY` only when all checks pass, and include:

```python
{
    "schema_version": "platform/shadow-run-1-preflight/1.0.0",
    "protocol": "SHADOW_RUN_1_BIYA_FROZEN",
    "status": "READY" or "BLOCKED",
    "checks": [...],
    "worktree": {"expected_head": ..., "actual_head": ...},
    "evidence": {"validation": {...}, "runtime_health": {...}},
    "runtime_configuration": {...},
    "calendar": {"first_session": ..., "session_dates": [...]},
    "opening_handoff": {"argv": [...], "powershell": ...} or None,
    "side_effects": {"network_calls": False, "run_opened": False},
}
```

Do not call `build_manifest_body`, `open_experiment_store`, `cmd_open`, any live-runtime function, or any Moomoo tool.

- [ ] **Step 3: Wire argparse and atomic report output**

Add the `preflight` subparser with all safety-critical inputs required, dispatch it through `cmd_preflight`, atomically write `--report` when supplied, print one canonical JSON document, and return nonzero for `BLOCKED`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.platform.test_shadow_run1_cli -v
```

Expected: all Shadow Run 1 CLI tests pass.

- [ ] **Step 5: Run changed validation**

Run:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools/validate.py changed
```

Expected: `PASSED`; inspect `full_suite_required` and retain the final FULL requirement.

---

### Task 3: Final verification and dirty-file audit

**Files:**
- Verify only; no planned edits.

**Interfaces:**
- Consumes: completed implementation and existing dirty-file baseline.
- Produces: fresh evidence for handoff.

- [ ] **Step 1: Run the complete offline suite once**

Run:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools/validate.py full
```

Expected: authoritative offline FULL passes without selecting live suites.

- [ ] **Step 2: Inspect the final diff and status**

Run `git diff -- tools/research/run_shadow_run.py tests/platform/test_shadow_run1_cli.py docs/superpowers/plans/2026-08-24-shadow-run-1-preflight.md` and `git status --short`. Confirm the five pre-existing dirty/untracked paths are unchanged and no run store, capture, or external evidence was created.

