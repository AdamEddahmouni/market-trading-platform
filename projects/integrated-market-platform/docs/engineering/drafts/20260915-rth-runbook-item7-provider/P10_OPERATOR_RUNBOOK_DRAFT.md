# P10 — Operator runbook draft (not canonical until software lands)

**Classification:** `EXPERIMENTAL` / proposed `RUNBOOK`
**Not canonical.** Do not replace
[TUESDAY_RTH_OPERATOR_CHECKLIST.md](../../TUESDAY_RTH_OPERATOR_CHECKLIST.md) or
[RTH_EMPIRICAL_OPS_RUNBOOK.md](../../RTH_EMPIRICAL_OPS_RUNBOOK.md) until the
matching launcher, kline-window, and persistence software is on `origin/main`.

Base SHA for these notes: `7aade60bf8041df5ebf9f0ac856d5d8802845c8d`.
Frozen RTH checkout `.rth-operator-20260915` is **read-only**.

Corresponding software (not on this SHA; do not merge from here):

- `diagnosis/launcher-routing-20260915` — SPA `/`, stop `moomoo-api-test`
- `diagnosis/item9-prospective-bar-20260915` — session-day 1m kline window

## Launch

From the **IMP checkout** `projects\integrated-market-platform` (primary tree
or a *current* worktree — not the frozen `.rth-operator-20260915` tree):

```text
START_PLATFORM.cmd
```

That script pins `IMP_LAUNCHER_PYTHON` to the repository `.venv\Scripts\python.exe`
and runs `tools\platform\local_launcher.py start --open`.

**SPA URL:** `http://127.0.0.1:5173/` (root `/`).

On this base SHA, `local_launcher.py` still opens
`http://127.0.0.1:5173/discover` (`DISCOVER_URL`). Vite proxies `/discover` to
the API, so the operator does **not** land on the SPA. Until launcher software
lands, after Start either:

- browse `http://127.0.0.1:5173/` manually, or
- use `/control` at `http://127.0.0.1:5173/control` for lifecycle only.

Do not treat `/discover` as FTEP live discovery. API
`http://127.0.0.1:8766`. Supervisor `http://127.0.0.1:8767` (loopback-only).

## Interpreter: IMP `.venv`, not `moomoo-api-test`

| Use | Interpreter |
|---|---|
| Platform, FTEP, Item 7/9, RTH ops | `projects\integrated-market-platform\.venv` (CPython 3.11; `tzdata` in the venv) |
| OpenD vendor SDK | `python tools\imp.py env install-opend` into **that same** `.venv` |
| Forbidden | Mixing `PYTHONPATH` with another venv's `site-packages`; auto-selecting `moomoo-api-test` (no sklearn) |

`START_PLATFORM.cmd` already requires the repo `.venv`. CLI work must use it
too. Linked worktrees: `python tools\imp.py env` then
`env bootstrap --link-venv` if no local `.venv`.

## FTEP ingress ≠ live discovery

| Path | What it is | What it is not |
|---|---|---|
| `python tools\ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` | One-shot Finviz prospective fetch | Persistent watch; cockpit feed; OE mint |
| SPA `/` / Live observational | Workstation UI | FTEP ingress |
| `/discover` | API proxy collision on this SHA | Discovery product |

FTEP PASS with an NVDA row does not fill the opportunity cockpit. Empty cockpit
(`LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`) does not invalidate Finviz
ingress. See P7.

Gates (all required; token is a gate):

```powershell
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
# Token from primary checkout — do not copy .private into worktrees
$env:IMP_FINVIZ_SECRET_DIR = "C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform\.private"
```

Never commit these. Point `IMP_STATE_DIR` at primary `.local`.
`python tools\imp.py ftep watch-catalysts` does **not** pass `--live-ingress`.

## Enrichment worker OFF

Default and required for observational RTH:

- `IMP_INTELLIGENCE_ENRICHMENT_WORKER` unset
- `worker_enabled=false` (`NoOpEnrichmentDispatcher` is fine)
- Do not set dispatcher/worker env to enable Grok automation

2026-09-15 snaps: `snap-1115/enrichment-status.json` → `worker_enabled: false`.

## Item 9 — expected outcomes (honesty table)

CLI (no top-level `--json` on this tool):

```powershell
$receiptDir = "artifacts\ftep-v1-002\item9-prospective-proof-receipts"
python tools\moomoo\opend_bar_1m_prospective_proof.py prospective `
  --poll `
  --instrument-id AAPL `
  --experiment-id item9-prospective-<date>-rth-aapl `
  --receipt-out $receiptDir `
  --poll-interval-s 5.0 `
  --timeout-s 3900.0
```

| Code | When | Operator meaning |
|---|---|---|
| `SOFTWARE_READY_RTH_REQUIRED` | Off-hours, no `--poll` | Tool ready; not a failure of OpenD |
| `POLL_REQUIRED` | During RTH without `--poll` | Re-run with `--poll` |
| `PROSPECTIVE_NO_POST_SIGNAL_BAR` | Poll finishes; no bar with `available_time > signal_time` | On **this SHA**: oldest-page kline from `start=None,end=None`. PIT is correct. Not a receipt. |
| `MOOMOO_PROTOCOL_ERROR` | History kline RET_OK miss / SDK exception | Fail-closed; quote connect may still have succeeded. Not `MOOMOO_AUTH_FAILURE`. Do not backfill the gap. |
| `MOOMOO_AUTH_FAILURE` | Quote context not logged in | OpenD GUI / login; different from CallClose |
| Versioned receipt `item9.bar-ohlcv-prospective-proof/1.1.0` | First post-signal bar selected | Still `orders_placed=false`, `calibrated=false`, FTEP not `EMPIRICAL_ACTIVE`. Does **not** close Item 9. |

Stdout JSON with `receipt: null` is an **outcome**, not a versioned receipt
file. Do not copy it into `item9-prospective-proof-receipts` as success.

Until session-day kline software lands, expect poll #1-class
`PROSPECTIVE_NO_POST_SIGNAL_BAR` even when OpenD quote is healthy.

## CallClose

SDK `reason=CallClose` every ~5s = the poll closed that iteration's
`OpenQuoteContext`. Expected. Not a drop, not logout, not entitlement loss.
See P7.

## UTF-8 receipts

Windows consoles may emit cp1252. Operator copies of JSON/logs must be UTF-8
(today: `poll-stdout.utf8.log` transcodes). Rules:

- Write receipts with UTF-8 (`encoding="utf-8"`, `\n`)
- Do not commit mojibake JSON
- `--json` stdout redirected to a file: save as UTF-8
- Versioned Item 9 receipts stay under `artifacts/ftep-v1-002/item9-prospective-proof-receipts/`
- Session working copies stay under governed `.local` (gitignored)

## Evidence paths

| What | Path |
|---|---|
| Canonical durable state | `C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform\.local` |
| Finviz token store | `...\projects\integrated-market-platform\.private` (`IMP_FINVIZ_SECRET_DIR`) |
| Frozen 2026-09-15 session copies | `...\market-trading-platform\.rth-operator-20260915\projects\integrated-market-platform\.local\rth-session-20260915\` |
| Lane A Finviz | `...\lane-a-finviz\finviz-ingress-YYYYMMDD-HHMMET.json` |
| Lane B Item 9 | `...\lane-b-item9\` (outcomes + `.utf8.log`; versioned receipt only if written) |
| Lane C Item 7 | `...\lane-c-item7\status.json` etc. |
| Enrichment / integrity snaps | `...\lane-f-monitor\` |
| FTEP governed session evidence | `artifacts/ftep-v1-002/governed-session-start-evidence.jsonl` (may be gitignored; still on disk) |
| Item 9 versioned receipts | `{IMP root}/artifacts/ftep-v1-002/item9-prospective-proof-receipts/` |
| RTH ops bundle | `$env:IMP_STATE_DIR/rth-empirical-ops/runs/RTHOPS-*.json` with `--write-run-artifact` |

State path:

```powershell
cd projects\integrated-market-platform
python tools\imp.py env
$report = python tools\state_path_diagnostic.py | ConvertFrom-Json
$env:IMP_STATE_DIR = $report.canonical_state_dir
$env:IMP_PERSIST_STATE = "1"
```

## Startup order (observational)

1. OpenD listening `127.0.0.1:11111` (operator GUI; IMP does not log in for you).
2. IMP `.venv` + `IMP_STATE_DIR` / `IMP_PERSIST_STATE=1`.
3. `START_PLATFORM.cmd` → confirm SPA at `/` (workaround until launcher software).
4. `python tools\rth_empirical_ops.py --json preflight` then `--json status`
   (`--json` **before** the subcommand).
5. Delegated: Finviz preflight, `ftep integrity-check FTEP-V1-002`, Item 9
   `readiness`, Item 7 `status` with a fresh `--training-cutoff-ns`.
6. Temporary Finviz/FTEP gates in **this shell only**.
7. One-shot `ftep_watch_catalysts.py ... --live-ingress --json` as needed.
8. Item 9 `--poll` in its own window (do not expect a receipt on this SHA).
9. Item 7 collector remains read-only. Enrichment stays OFF. No Paper/Live orders.

End: `python tools\rth_empirical_ops.py --json summarize`. Unset live gates.
Leave `IMP_STATE_DIR` if still doing read-only diagnostics.

## Must land with software

This draft is false as canonical operator truth on `7aade60b` until:

1. Launcher opens `/` and refuses `moomoo-api-test`.
2. Item 9 requests session-day kline (and ideally reuses quote context).
3. (Item 7) persistence writer + BBO-grid wiring exist — see P8 — before any
   runbook claims governed rows.
