# Local Platform Launcher Design

## Goal

Give a Windows operator a safe, double-clickable way to start, open, inspect,
and stop the complete local Integrated Market Platform without remembering two
terminal commands or killing unrelated processes.

## Operator experience

The repository root exposes three entry points:

- `START_PLATFORM.cmd` starts the API and Vite UI, waits for both local ports,
  and opens `http://127.0.0.1:5173/discover`.
- `STOP_PLATFORM.cmd` stops only processes owned by the launcher.
- `PLATFORM_CONTROL.cmd` presents Start/Open, Open Browser, Status, Stop/Exit,
  and Finviz Status options in one small terminal menu.

All entry points resolve the repository from their own location, so they work
when double-clicked or called from another directory. Errors remain visible and
name the missing prerequisite or log file.

## Architecture

`tools/platform/local_launcher.py` is a standard-library controller. It owns
process discovery, prerequisite checks, hidden child-process creation, local
HTTP readiness polling, browser opening, status reporting, and shutdown. The
CMD files are intentionally thin adapters.

Runtime state is written atomically to the gitignored
`.local/platform-launcher.json`. Each service record contains its PID, expected
command identity, and log path. Shutdown queries the live Windows command line
and acts only when it still matches that identity; missing, stale, or reused
PIDs are removed from state without being terminated. Descendants of a
verified launcher-owned root are stopped with Windows `taskkill /T`.

## Runtime selection and gates

The controller uses the repository CPython 3.11 venv for itself. For the API it
prefers, in order: `IMP_PLATFORM_BACKEND_PYTHON`, the existing
`%USERPROFILE%\moomoo-api-test\.venv\Scripts\python.exe`, and the repository
venv. This keeps the Moomoo SDK available without modifying the governed
foundation dependency lock.

The API child receives these defaults unless the operator already supplied an
explicit value: `IMP_LIVE_OBSERVATIONAL=1`, `IMP_MOOMOO_LIVE=1`,
`IMP_PAPER_EXECUTION=1`, `IMP_LIVE_INTERNAL_SIMULATION=1`,
`IMP_PERSIST_STATE=1`, and `PYTHONUNBUFFERED=1`. These gates permit
observational data and internal paper simulation only. The launcher never sets
live broker execution authority.

The application already loads the repository `.env`; the launcher does not
read, print, copy, or place credentials on command lines. Finviz automatic
re-fetch and recovery therefore use the existing secure store and provider
configuration unchanged.

## Failure behavior

- An occupied API or UI port not owned by the launcher blocks Start and reports
  the exact port.
- Missing Python, npm, `ui/node_modules`, or source entry points blocks Start
  before any process is created.
- If one child fails or readiness times out, both launcher-owned children are
  stopped and the operator receives both log paths.
- Starting an already healthy launcher-owned platform is idempotent and only
  opens the browser when requested.
- Status never contacts an external market-data provider; it checks local
  process identity and loopback HTTP readiness only.

## Verification

Offline unit tests inject process, command-line, readiness, and browser
adapters. They cover runtime selection, gates, idempotent start, partial-start
rollback, stale/reused PID safety, and exact stop scope. A final Windows smoke
check starts the real local API/UI, verifies both loopback endpoints, exercises
Status, then stops them and verifies both ports are closed. Provider live probes
remain separate and opt-in.

