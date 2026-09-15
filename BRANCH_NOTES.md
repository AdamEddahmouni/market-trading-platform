# diagnosis/launcher-routing-20260915

Diagnostic/candidate only. **Do not merge as-is. Do not land this `d588728d` patch blindly.**

| Field | Value |
|-------|-------|
| **Branch** | `diagnosis/launcher-routing-20260915` |
| **Worktree** | `.worktrees/diagnosis-launcher-routing-20260915` |
| **Base SHA** | `d588728d60b139ae44b5a3667a8e120d1e21ee1c` (`main` at branch creation) |
| **HEAD** | *filled after commit* |
| **Frozen RTH SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` (do not thaw / do not edit) |
| **rebase-required** | **YES** — rebase or reproduce onto **post-close `origin/main`**, then re-run focused tests |

## Land rule

Must rebase/reproduce onto post-close `origin/main`. This branch is **not** based on frozen `7aade60` and is **not** guaranteed to match current `origin/main`.

## Target operator behavior

- Single command: `START_PLATFORM.cmd` from `projects/integrated-market-platform`
- Opens **`http://127.0.0.1:5173/`** (SPA root), not proxied `/discover`
- `select_backend_python`: override, then repo `.venv` only
- **No** `%USERPROFILE%\moomoo-api-test` auto-select
- Start probes `import sklearn` before spawning the API
- `START_PLATFORM.cmd` / `PLATFORM_CONTROL.cmd` pin `IMP_PLATFORM_BACKEND_PYTHON` to repo `.venv` when unset

## Owned files (Lane P3)

- `projects/integrated-market-platform/tools/platform/local_launcher.py`
- `projects/integrated-market-platform/START_PLATFORM.cmd`
- `projects/integrated-market-platform/PLATFORM_CONTROL.cmd`
- `projects/integrated-market-platform/ui/vite.config.ts`
- `projects/integrated-market-platform/tools/platform/control_service.py`
- `projects/integrated-market-platform/src/market_platform_foundation/ui_api/server.py` (`normalize_ui_path` unquote only)

Do **not** edit live-OE files owned by P1/P4 (`opportunity_projections`, projections attention/as_of, news EventV1, observation ingress).

## Tests

```powershell
cd projects\integrated-market-platform
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest tests.platform.test_local_launcher tests.platform.test_operator_control_service tests.ui1.test_ui_api.Ui1ApiTests.test_percent_encoded_explain_ref_round_trips -v
```

**25 passed** (2026-09-15, isolated worktree, canonical IMP `.venv`).
