# RTH empirical operations runbook (Phase 5 Lane H)

Software-only coordination layer. Does **not** replace underlying CLIs, declare
`EMPIRICAL_ACTIVE`, create empirical locks, or place Paper/Live orders.

**Operator one-pager (Tuesday 2026-09-15):**
[TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md).

## Environment (operator workstation)

```powershell
cd projects\integrated-market-platform
$env:IMP_STATE_DIR = "C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform\.local"
python tools\imp.py env bootstrap --link-venv   # if needed
```

Use the project `.venv` on Windows (tzdata / zoneinfo).

## Command center

```powershell
python tools\rth_empirical_ops.py --json preflight
python tools\rth_empirical_ops.py --json status
python tools\rth_empirical_ops.py --json run-observational
python tools\rth_empirical_ops.py --json summarize
```

`--json` is a **global** option (before the subcommand). `preflight --json` is rejected by argparse.

Acceptance label when the ops layer is wired and hard blockers are absent:
`RTH_EMPIRICAL_OPS_READY` (software only — not an empirical evidence gate).

## Tuesday 2026-09-15 US equity RTH (09:30–16:00 ET)

### 1. Preflight (independent checks)

Expect `acceptance_label=RTH_EMPIRICAL_OPS_READY` when canonical state,
FTEP integrity, Finviz credentials, and session counts are valid.
Off-hours `disposition` may be `SOFTWARE_READY_RTH_REQUIRED`; during RTH expect
`disposition=READY` when live gates are temporarily enabled in the **shell only**.

Delegated tools (unchanged):

```powershell
python tools\ftep_finviz_prospective_preflight.py FTEP-V1-002 --json
python tools\imp.py ftep integrity-check FTEP-V1-002 --json
python tools\moomoo\opend_bar_1m_prospective_proof.py readiness
python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns <ns>
```

### 2. Temporary gates (session shell only — never commit)

```powershell
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
```

### 3. Observational sequence (RTH)

| Step | Command | Expected receipt / code |
|------|---------|-------------------------|
| Finviz prospective read | `python tools\ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` | `watch_mode=PROSPECTIVE_FINVIZ_INGRESS`; zero rows → `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS` |
| Item 9 prospective 1m | `python tools\moomoo\opend_bar_1m_prospective_proof.py prospective --poll --instrument-id AAPL --experiment-id item9-prospective-20260915-rth-aapl --receipt-out artifacts\ftep-v1-002\item9-prospective-proof-receipts --poll-interval-s 5.0 --timeout-s 3900.0` | JSON on stdout; receipt `item9.bar-ohlcv-prospective-proof/1.1.0`; `orders_placed=false`, `calibrated=false` |
| Item 7 status | `python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns <ns>` | Read-only status; no forced settlement (`--training-cutoff-ns` required) |
| Ops dry-run bundle | `python tools\rth_empirical_ops.py --json run-observational` | `operator_run_id=RTHOPS-*`; sub-artifact refs only |

### 4. Failure codes (fail closed)

| Code | Meaning |
|------|---------|
| `SOFTWARE_READY_RTH_REQUIRED` | Tool ready; US equity RTH required |
| `BLOCKED` / `RTH_EMPIRICAL_OPS_BLOCKED` | Hard preflight blocker |
| `COMPARATOR_NOT_CONFIGURED` | Alpaca Paper keys absent (expected if not provisioned) |
| `POLL_REQUIRED` | Item 9 during RTH without `--poll` |
| `LIVE_INGRESS_REFUSED_BY_OPS_LAYER` | Ops CLI refuses live ingress (use delegated watch CLI) |
| `FINVIZ_CREDENTIALS_ABSENT` | No Finviz login/token |

### 5. Paper comparator

Missing `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` → `COMPARATOR_NOT_CONFIGURED`.
Do not fabricate fills or place Paper orders from this lane.

## Authority

Live remains observational-only. FTEP stays not `EMPIRICAL_ACTIVE` until
separately governed receipts apply. Evidence class for this runbook: **SOFTWARE**.
