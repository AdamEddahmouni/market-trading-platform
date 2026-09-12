# FTEP-V1-002 — governed SIGNAL_ONLY session launch prep

**Status:** Owner SIGNAL_ONLY authorization recorded (`signal-only-authorization-receipt-2026-09-12.json`). **No session started** in orchestrator pass (US equity RTH closed; weekend).

## Preconditions (machine gates)

| Gate | Required disposition |
| --- | --- |
| Manifest | `FROZEN` @ fingerprint `F7083180990BC59578CA045E1E1318A356421BBC9B81EE514C14130CB0B356B1` |
| Authorization receipt | `ftep_signal_only_authorization_receipt` present |
| Persistence | `IMP_PERSIST_STATE=1` or `IMP_STATE_DIR` set |
| Preflight | `READY` (PAPER / FORWARD_TEST) |
| Campaign readiness | `READY` (coverage gaps satisfied; WAVE-A-002 deferred) |
| Calendar | `US_EQUITY_RTH` open (Mon–Fri 09:30–16:00 America/New_York) |
| Execution / Live | **NOT** authorized |

## Operator commands (first RTH session)

From `projects/integrated-market-platform`:

```powershell
$env:IMP_PERSIST_STATE = "1"
python tools/imp.py providers campaign-readiness FTEP-V1-002 --json
```

Expect `disposition`: `READY` and empty `blockers`.

Optional Finviz refresh (no secrets in logs):

```powershell
python tools/finviz/probe.py
```

### Copy-paste: RTH open preflight (no session lock)

Run only when `us_equity_rth_open` is true in campaign-status output (Mon–Fri 09:30–16:00 America/New_York):

```powershell
Set-Location "C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform"
$env:IMP_PERSIST_STATE = "1"
python tools/imp.py ftep campaign-status FTEP-V1-002 --json
python tools/imp.py providers campaign-readiness FTEP-V1-002 --json
```

Abort if `us_equity_rth_open` is false, `campaign_readiness_disposition` is not `READY`, or `signal_only_authorized` is false. Do not start a governed session from this script alone — owner must invoke `ForwardTestService.create_session` (SIGNAL_ONLY) per runbook after gates pass.

Session creation uses governed Paper forward-test API / `ForwardTestService.create_session` with full campaign identity (`campaign_id`, `manifest_fingerprint`, cohort arms). **SIGNAL_ONLY** — no Paper order preview/submit.

## Safety

- Paper orders: **0**
- Live orders: **0**
- Post-freeze manifest mutations: **0**
