# repair/launcher-routing-from-main-20260915

**NOT FOR MERGE UNTIL 2026-09-15 RTH RECONCILIATION COMPLETE.**

Isolated reconstruction of the launcher/Vite candidate onto current `origin/main`.
The stale diagnosis branch is **kept**, not merged.

| Field | Value |
|-------|-------|
| **Branch** | `repair/launcher-routing-from-main-20260915` |
| **Worktree** | `.worktrees/repair-launcher-routing-from-main-20260915` |
| **Base SHA** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` (`origin/main` at reconstruction) |
| **HEAD** | *filled after commit* |
| **Source candidate** | `diagnosis/launcher-routing-20260915` (`9b0781c9` / patch `a2dd6ced`) |
| **Stale diagnosis base** | `d588728d60b139ae44b5a3667a8e120d1e21ee1c` (do not merge that branch) |
| **Frozen RTH** | `.rth-operator-20260915` at `7aade60b` — not edited |
| **auto-merge** | **NO** |

## Reconstruct vs cherry-pick

Cherry-picked `a2dd6ced` onto `7aade60b`, then dropped P1-owned `server.py` /
`tests/ui1/test_ui_api.py`. This is not a merge of `diagnosis/launcher-routing-20260915`.

## Operator behavior

- `START_PLATFORM.cmd` from `projects/integrated-market-platform`
- Opens **`http://127.0.0.1:5173/`** (SPA root), not proxied `/discover`
- `select_backend_python`: override, then repo `.venv` only
- **No** `%USERPROFILE%\moomoo-api-test` auto-select
- Start probes `import sklearn` before spawning the API
- Vite HTML bypass for `/discover` (and SPA/API collisions)
- Proxy `/opportunities` `/intelligence` `/canary`
- Control status uses `port_is_open`, not HTTP self-probe

## Owned files this reconstruction

- `tools/platform/local_launcher.py`
- `START_PLATFORM.cmd`
- `PLATFORM_CONTROL.cmd`
- `ui/vite.config.ts`
- `tools/platform/control_service.py`
- launcher/control tests + operator docs that name the SPA URL

## Follow-on (P1 or tiny separate commit)

**Skipped `server.py` `normalize_ui_path` percent-decode.** P1 owns
`src/market_platform_foundation/ui_api/server.py` on
`repair/live-oe-cockpit-state-20260915` (EventV1/OE ingress). The diagnosis
unquote for `/explain/explain%3Areplay%3Acontext` is **not** on this branch.

Landing later: add `normalize_ui_path` +
`tests.ui1.test_ui_api.Ui1ApiTests.test_percent_encoded_explain_ref_round_trips`
without colliding P1's handler changes.

## Tests

```powershell
cd projects\integrated-market-platform
$env:PYTHONPATH='src'
# interpreter: repo .venv (link-venv if this worktree has none)
python -m unittest tests.platform.test_local_launcher tests.platform.test_operator_control_service -v
```
