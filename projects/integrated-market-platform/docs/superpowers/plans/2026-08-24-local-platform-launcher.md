# Local Platform Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe double-click Start/Open/Status/Stop controls for the complete local platform.

**Architecture:** A standard-library Python controller owns lifecycle state and validates process identity before shutdown. Thin root-level CMD adapters invoke the controller from any working directory.

**Tech Stack:** CPython 3.11 standard library, Windows process tools, CMD, unittest.

## Global Constraints

- Never set or expose live execution authority.
- Never log, copy, or pass credentials on a command line.
- Stop only launcher-owned processes whose current command identity matches recorded state.
- Bind API and UI to loopback (`127.0.0.1`) on ports 8766 and 5173.
- Preserve the governed foundation's standard-library-only dependency lock.

---

### Task 1: Tested lifecycle controller

**Files:**
- Create: `tools/platform/local_launcher.py`
- Create: `tests/platform/test_local_launcher.py`

**Interfaces:**
- Consumes: repository root, local environment, `subprocess`, `urllib.request`, and `webbrowser`.
- Produces: CLI actions `start`, `stop`, `status`, `open`, and `menu`; atomic `.local/platform-launcher.json` ownership state.

- [ ] **Step 1: Write failing lifecycle tests**

  Add unit tests that inject a fake OS adapter and assert backend-Python
  precedence, observational/paper default gates, idempotent healthy start,
  rollback after UI readiness failure, refusal to kill a PID with a changed
  command identity, and exact verified process-tree termination.

- [ ] **Step 2: Run the focused test and observe RED**

  Run:

  ```powershell
  $env:PYTHONPATH='src'
  .venv\Scripts\python.exe -m unittest tests.platform.test_local_launcher -v
  ```

  Expected: import failure because `tools.platform.local_launcher` does not
  exist.

- [ ] **Step 3: Implement the minimal controller**

  Implement typed service/state records, atomic JSON persistence, prerequisite
  validation, Python selection, environment construction, hidden child launch,
  local readiness polling, browser opening, sanitized status, verified
  `taskkill /T /F`, rollback, and argparse/menu dispatch. Use dependency
  injection for every OS effect exercised by tests.

- [ ] **Step 4: Run focused tests and changed validation**

  Run the focused command above, followed by:

  ```powershell
  $env:PYTHONPATH='src'
  .venv\Scripts\python.exe tools\validate.py changed
  ```

  Expected: all launcher tests pass and changed validation reports zero
  failures/errors.

### Task 2: Root entry points and operator documentation

**Files:**
- Create: `START_PLATFORM.cmd`
- Create: `STOP_PLATFORM.cmd`
- Create: `PLATFORM_CONTROL.cmd`
- Modify: `README.md`
- Modify: `ui/README.md`
- Test: `tests/platform/test_local_launcher.py`

**Interfaces:**
- Consumes: launcher CLI from Task 1.
- Produces: double-click Start/Open and Stop, plus an interactive control menu.

- [ ] **Step 1: Write failing entry-point contract tests**

  Assert all three CMD files resolve `%~dp0`, use the repository venv, call the
  expected launcher action, and pause only when the operator needs to read a
  result. Assert README copy names the one-click path, logs, ports, and safe
  stop behavior.

- [ ] **Step 2: Run the focused test and observe RED**

  Run the focused unittest command from Task 1. Expected: missing CMD/README
  contract assertions fail.

- [ ] **Step 3: Add thin CMD adapters and concise docs**

  Make Start call `start --open`, Stop call `stop`, and Control call `menu`.
  Each adapter changes to its own root and prints a CPython 3.11 venv setup
  instruction if the launcher interpreter is missing. Document OpenD as a
  separately installed local gateway and Finviz as secure-store configuration.

- [ ] **Step 4: Run focused and changed validation**

  Expected: focused tests and `tools/validate.py changed` both exit 0.

### Task 3: Real local smoke and final gates

**Files:**
- Modify only if a smoke failure is reproduced by a new failing test.

**Interfaces:**
- Consumes: completed launcher and installed local prerequisites.
- Produces: fresh evidence that start/open/status/stop works on this Windows machine.

- [ ] **Step 1: Start without opening a browser and inspect status**

  Run `START_PLATFORM.cmd --no-open` through the controller equivalent, verify
  `http://127.0.0.1:8766/context` and `http://127.0.0.1:5173/`, and run
  `status`. Do not run external provider probes.

- [ ] **Step 2: Stop and verify closure**

  Run `STOP_PLATFORM.cmd` through the controller equivalent, then confirm no
  launcher-owned process or listener remains on ports 8766/5173.

- [ ] **Step 3: Run final offline validation and UI gates**

  Run:

  ```powershell
  $env:PYTHONPATH='src'
  .venv\Scripts\python.exe tools\validate.py full
  cd ui
  npm run test
  npm run build
  ```

  Expected: all offline Python tests and UI tests pass; UI build exits 0.

- [ ] **Step 4: Commit launcher work**

  Stage only the spec, plan, launcher, tests, CMD entry points, and docs. Keep
  unrelated audit JSON modifications unstaged. Commit with conventional
  messages and leave local `main` at the verified launcher head.

