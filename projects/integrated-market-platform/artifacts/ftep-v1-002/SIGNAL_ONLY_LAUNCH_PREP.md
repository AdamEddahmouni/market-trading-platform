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
python tools/imp.py ftep integrity-check FTEP-V1-002 --json
```

Expect `disposition`: `READY` and empty `blockers`. Integrity-check must report `disposition`: `PASS` (includes unchanged `FTEP-V1-001` fingerprint).

Without `IMP_PERSIST_STATE=1`, integrity-check fails closed with `PERSISTENCE_DISABLED` and prints `operator_hints` explaining that durable state must be enabled (checks are unchanged; only the shell env is missing).

Optional opportunity dry-run (FTEP-V1-002 fixture rows, not live data):

```powershell
python tools/imp.py ftep opportunity-summaries --json
```

Optional session gate dry-run (no locks; still requires RTH open to pass):

```powershell
python tools/imp.py ftep session-start FTEP-V1-002 --dry-run --json
```

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

## Monday RTH operator checklist (cron-style)

Run once per US equity session day after **09:30 America/New_York** and before first `create_session` (skip weekends and US market holidays):

1. Confirm calendar: `python tools/imp.py ftep campaign-status FTEP-V1-002 --json` → `us_equity_rth_open=true`, `manifest_status=FROZEN`, `signal_only_authorized=true`, `governed_session_count=0` (until first session).
2. Enable persistence: `$env:IMP_PERSIST_STATE = "1"`.
3. Machine gates: `python tools/imp.py providers campaign-readiness FTEP-V1-002 --json` → `disposition=READY`; `python tools/imp.py ftep integrity-check FTEP-V1-002 --json` → `disposition=PASS` (includes unchanged **FTEP-V1-001** fingerprint).
4. Dry-run session gate: `python tools/imp.py ftep session-start FTEP-V1-002 --dry-run --json` → `would_create_session=true`, empty `blockers`, non-empty `forward_test_invoke_steps`.
5. Execute **only** the `ForwardTestService.create_session` steps from `forward_test_invoke_steps` (SIGNAL_ONLY, both cohort arms if authorized). **Zero** Paper order preview/submit; **zero** Live.
6. Append evidence: session ids, manifest fingerprint, and gate JSON to the wave operator log / `FINAL_EXECUTIVE_REPORT.md` session section.

If any step fails, stop — do not partially create sessions or mutate manifests.

Session creation uses governed Paper forward-test API / `ForwardTestService.create_session` with full campaign identity (`campaign_id`, `manifest_fingerprint`, cohort arms). **SIGNAL_ONLY** — no Paper order preview/submit.

## Safety

- Paper orders: **0**
- Live orders: **0**
- Post-freeze manifest mutations: **0**
