# Tuesday RTH operator checklist — 2026-09-15 (historical)

**Status:** Historical 2026-09-15 one-pager. **Not** the next lawful preopen.

**Next lawful RTH preopen (current `main`):** [NEXT_RTH_CAMPAIGN_RUNBOOK.md](NEXT_RTH_CAMPAIGN_RUNBOOK.md#next-lawful-rth-preopen-checklist). Canonical SHA: [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) **CURRENT_MAIN** `5b74876d` until a later pin.

**Evidence class:** SOFTWARE only. No Paper/Live orders. No empirical locks.  
**Canonical CLI contracts:** verified against argparse on `origin/main` (Lane A Phase 5.5B).

Deep reference: [RTH_EMPIRICAL_OPS_RUNBOOK.md](RTH_EMPIRICAL_OPS_RUNBOOK.md).

## Bootstrap (once per workstation)

```powershell
cd projects\integrated-market-platform
python tools\imp.py env bootstrap --link-venv   # if needed
$report = python tools\state_path_diagnostic.py | ConvertFrom-Json
$env:IMP_STATE_DIR = $report.canonical_state_dir
$env:IMP_PERSIST_STATE = "1"
```

Use project `.venv` (Python 3.11+). Never commit session env gates.

## T−15 minutes (≈ 09:15 ET)

1. **State path** — `python tools\imp.py state-path` (resolve mismatch before RTH).
2. **Item 7 cutoff** — compute immediately before any Item 7 command (mandatory):

   ```powershell
   $item7CutoffNs = python -c "from market_platform_foundation.clock import monotonic_wall_ns; print(monotonic_wall_ns())"
   ```

3. **RTH ops command center** — global `--json` **before** subcommand:

   ```powershell
   python tools\rth_empirical_ops.py --json preflight
   python tools\rth_empirical_ops.py --json status
   ```

   Expect `acceptance_label=RTH_EMPIRICAL_OPS_READY` when blockers are absent.  
   Off-hours: `disposition=SOFTWARE_READY_RTH_REQUIRED` is software success.

4. **Delegated preflight** (unchanged tools):

   ```powershell
   python tools\ftep_finviz_prospective_preflight.py FTEP-V1-002 --json
   python tools\imp.py ftep integrity-check FTEP-V1-002 --json
   python tools\moomoo\opend_bar_1m_prospective_proof.py readiness
   python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns $item7CutoffNs
   ```

5. **Temporary gates** (operator shell only — never commit):

   ```powershell
   $env:IMP_FINVIZ_LIVE = "1"
   $env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
   ```

## 09:30 open — observational sequence (RTH)

Recompute `$item7CutoffNs` at session start if Item 7 commands run again.

| Step | Command | Receipt / acceptance |
|------|---------|----------------------|
| Finviz prospective | `python tools\ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` | UTF-8 JSON stdout even on 429/token-absent/gates-inactive/provider-failure; `watch_mode=PROSPECTIVE_FINVIZ_INGRESS`; zero rows → `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS`; do not immediately retry 429 |
| Item 9 OpenD 1m | See **Item 9** below | Versioned JSON under receipt dir; contract `item9.bar-ohlcv-prospective-proof/1.1.0` |
| Item 7 status | `python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns $item7CutoffNs` | Read-only; no forced settlement |
| Ops dry-run bundle | `python tools\rth_empirical_ops.py --json run-observational` | `operator_run_id=RTHOPS-*`; `orders_placed=false`; optional artifact with `--write-run-artifact` |

End of session summary:

```powershell
python tools\rth_empirical_ops.py --json summarize
```

### Finviz sequence (live ingress)

Prerequisites: governed RTH session, Finviz credentials, gates in §T−15.  
Command (positional slug; `--json` is tool-local, not RTH-ops global):

```powershell
python tools\ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json
```

Do **not** use `rth_empirical_ops.py` for live Finviz ingress (`LIVE_INGRESS_REFUSED_BY_OPS_LAYER`).

### Item 9 sequence (prospective 1m BAR_OHLCV)

Subcommand emits JSON to stdout; **no** top-level `--json` flag on this CLI.

```powershell
$receiptDir = "artifacts\ftep-v1-002\item9-prospective-proof-receipts"
python tools\moomoo\opend_bar_1m_prospective_proof.py prospective `
  --poll `
  --instrument-id AAPL `
  --experiment-id item9-prospective-20260915-rth-aapl `
  --receipt-out $receiptDir `
  --poll-interval-s 5.0 `
  --timeout-s 3900.0
```

Expect `orders_placed=false`, `calibrated=false`. During RTH without `--poll` → `POLL_REQUIRED`.

### Item 7 sequence (corpus collector)

`--training-cutoff-ns` is **required** for `status`, `diagnose`, and `collect`.

```powershell
$item7CutoffNs = python -c "from market_platform_foundation.clock import monotonic_wall_ns; print(monotonic_wall_ns())"
python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns $item7CutoffNs
python tools\item7_corpus_collector.py diagnose --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns $item7CutoffNs
# RTH export (optional; still no production promotion):
python tools\item7_corpus_collector.py collect --training-cutoff-ns $item7CutoffNs --persistence-root $env:IMP_STATE_DIR --output-dir .local\corpus-export --require-rth
```

## Receipt locations

| Artifact | Path |
|----------|------|
| Item 9 prospective proof | `{IMP root}/artifacts/ftep-v1-002/item9-prospective-proof-receipts/` (override with `--receipt-out`) |
| RTH ops run bundle | `$env:IMP_STATE_DIR/rth-empirical-ops/runs/RTHOPS-*.json` when using `--write-run-artifact` on `run-observational` |
| Finviz / FTEP / Item 7 | Machine-readable JSON on stdout (`--json` where supported); persist operator copies under governed `.local` policy |

## Independent review (before closing session)

- Confirm `ftep integrity-check` disposition PASS against canonical `IMP_STATE_DIR`.
- Spot-check Item 9 receipt: contract version, experiment id, `orders_placed=false`.
- Confirm no `empirical_lock_created` / FTEP not `EMPIRICAL_ACTIVE` in ops JSON.
- Comparator: missing Alpaca keys → `COMPARATOR_NOT_CONFIGURED` (expected if not provisioned).

## Failure codes (fail closed)

| Code | Meaning |
|------|---------|
| `SOFTWARE_READY_RTH_REQUIRED` | Tool ready; US equity RTH required |
| `BLOCKED` / `RTH_EMPIRICAL_OPS_BLOCKED` | Hard preflight blocker |
| `COMPARATOR_NOT_CONFIGURED` | Alpaca Paper keys absent |
| `POLL_REQUIRED` | Item 9 during RTH without `--poll` |
| `LIVE_INGRESS_REFUSED_BY_OPS_LAYER` | Use `ftep_watch_catalysts --live-ingress` |
| `FINVIZ_CREDENTIALS_ABSENT` | No Finviz login/token |

## Shutdown / env cleanup

```powershell
Remove-Item Env:IMP_FINVIZ_LIVE -ErrorAction SilentlyContinue
Remove-Item Env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS -ErrorAction SilentlyContinue
# Leave IMP_STATE_DIR / IMP_PERSIST_STATE if still doing read-only diagnostics
```

Do not place Paper/Live orders from this checklist. Evidence class remains **SOFTWARE**.
