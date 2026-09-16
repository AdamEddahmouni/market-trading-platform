# 2026-09-16 08:30 ET macro window — PREP checklist only

**Do not execute from this lane.** Docs-only. Does not start tomorrow's
campaign, does not place orders, does not enable Live, does not turn on the
enrichment worker, and does not delay live-path **software** work.

**Classification:** `EXPERIMENTAL` PREP
**Not canonical.** Frozen 2026-09-15 RTH was not edited.

| Field | Value |
|---|---|
| Window | Wednesday 2026-09-16 **08:30 ET** US macro print (pre-cash-RTH) through **09:30 ET** cash open |
| Campaign | Do **not** activate FTEP-V1-001 (ES still `FROZEN_BLOCKED_EXTERNAL_DATA_ENTITLEMENT`) |
| FTEP-V1-002 | Still SIGNAL_ONLY / not `EMPIRICAL_ACTIVE`; cash RTH 09:30–16:00 ET |
| Base software | Whatever is on `origin/main` **that morning** — today these notes assume `7aade60b` plus any **merged** launcher/kline fixes |

If launcher / session-day kline software has **not** merged, follow P10
workarounds (open SPA `/` by hand; do not expect Item 9 receipts).

## Commands (reference; do not run now)

```powershell
Set-Location "C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform"
python tools\imp.py env
$report = python tools\state_path_diagnostic.py | ConvertFrom-Json
$env:IMP_STATE_DIR = $report.canonical_state_dir
$env:IMP_PERSIST_STATE = "1"
# Token from primary .private — never copy into worktrees
$env:IMP_FINVIZ_SECRET_DIR = "C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform\.private"
```

Launch: `START_PLATFORM.cmd` → confirm `http://127.0.0.1:5173/`.

Preflight:

```powershell
python tools\rth_empirical_ops.py --json preflight
python tools\rth_empirical_ops.py --json status
python tools\ftep_finviz_prospective_preflight.py FTEP-V1-002 --json
python tools\imp.py ftep integrity-check FTEP-V1-002 --json
python tools\moomoo\opend_bar_1m_prospective_proof.py readiness
$item7CutoffNs = python -c "from market_platform_foundation.clock import monotonic_wall_ns; print(monotonic_wall_ns())"
python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns $item7CutoffNs
```

Finviz one-shot (only after gates + token; still not a persistent watch):

```powershell
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
python tools\ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json
```

Off-hours / pre-09:30: Finviz preflight may be `SOFTWARE_READY_RTH_REQUIRED` /
`RTH_CLOSED`. That is software success, not a print miss. Do not force
`--live-ingress` to invent RTH.

Item 9 `--poll` is a **09:30+** cash-RTH tool on this stack (US equity 1m).
Do not start a 3900s AAPL prospective poll at 08:30 expecting a macro-print
bar receipt.

## Evidence paths (create a new dated folder; do not write into frozen 09-15)

Suggested (gitignored `.local`):

`C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform\.local\rth-session-20260916\`

| Slice | Path |
|---|---|
| Preflight JSON | `...\rth-session-20260916\pre-0830\` |
| 08:30–09:30 | `...\rth-session-20260916\macro-0830\` |
| 09:30 transition | `...\rth-session-20260916\rth-open\` |
| Item 9 receipts (only if a versioned file is written) | `{IMP}/artifacts/ftep-v1-002/item9-prospective-proof-receipts/` |
| Item 7 status | `...\rth-session-20260916\item7\` |
| UTF-8 logs | `*.utf8.log` / UTF-8 JSON only |

Do not reuse `.rth-operator-20260915` as the write target.

## Startup order

1. Workstation clock = `America/New_York` (08:30 means ET).
2. OpenD up on `127.0.0.1:11111` **before** 08:30 if any quote/kline diagnostic
   will run (login is operator GUI). Quote connect ≠ kline proof (P7).
3. IMP `.venv` 3.11, **not** `moomoo-api-test`.
4. Canonical `IMP_STATE_DIR` + `IMP_PERSIST_STATE=1` + `IMP_FINVIZ_SECRET_DIR`.
5. `START_PLATFORM.cmd` → SPA `/`. Enrichment worker **OFF**.
6. Integrity-check / ops preflight / Item 9 `readiness` / Item 7 `status`.
7. Stop. Wait for 08:30. Do not enable Live.

## Pre-08:30 (T−30 to T−1)

- Record SHA of the tree that will actually run (`git rev-parse HEAD` /
  `origin/main`).
- Confirm FTEP-V1-001 fingerprint unchanged; **do not** start an ES session.
- Confirm two V1-002 governed sessions still present; locks still **0**.
- Confirm enrichment `worker_enabled=false`.
- Confirm OpenD TCP if using Moomoo.
- Prepare UTF-8 capture paths. Do not start Item 9 `--poll`.
- Do not set Finviz live gates until a lawful observational fetch is intended.
- CallClose during any quote probe is iteration close, not a crash (P7).

## 08:30–09:30 (macro window)

Purpose: **observe** the print window. Not FTEP activation. Not Item 9
prospective proof. Not Item 7 row manufacture.

- If a print is scheduled, record source identity, event time, receive time
  (do not invent a series if the calendar is unknown at PREP time).
- Optional OpenD **quote** snapshot diagnostic only — never derive BBO from
  `last_price`; never treat kline oldest-page as prospective.
- Optional Finviz one-shot only if gates+token are set **and** the operator
  accepts that V1-002 live-ingress is specified around cash RTH; zero rows or
  `RTH_CLOSED` must stay honest.
- ES futures: observational-only if entitled; V1-001 remains blocked — no
  SIGNAL_ONLY authorization workaround.
- No Paper/Live orders. No empirical locks. No enrichment worker.

## 09:30 transition (cash RTH)

Handoff to the P10 observational sequence — **if** the operator chooses to run
Tuesday-style RTH, as a **separate** decision, not as this PREP executing:

1. Recompute `$item7CutoffNs`.
2. Ops `--json status` — during RTH expect `READY` only with shell-local gates.
3. One-shot Finviz `--live-ingress` (repeat later; it will exit).
4. Item 9 `--poll` only after kline-window software is present; otherwise
   expect `PROSPECTIVE_NO_POST_SIGNAL_BAR` again — log it, do not backfill.
5. Item 7 `status` / `diagnose` read-only. 0 rows remains valid.
6. SPA cockpit empty ≠ FTEP failure (P7).

Unset `IMP_FINVIZ_LIVE` / `IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS` at session end.

## Explicit non-goals

- Do not run this checklist as the 2026-09-16 campaign from the diagnosis branch.
- Do not merge these drafts to make them "true" before software.
- Do not thaw frozen 2026-09-15 RTH.
- Do not update `PROGRAM_STATUS.md` or doctrine from this PREP.
