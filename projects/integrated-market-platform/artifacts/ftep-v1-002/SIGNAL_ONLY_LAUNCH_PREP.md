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

**Dual cohort arms (baseline + AI-enhanced):** One governed `session-start` (or operator runbook) creates **two** `ForwardTestService.create_session` calls for the same frozen campaign — one per preregistered arm (`BASELINE`, then `AI_ENHANCED`). They share a single ACTIVE campaign binding row (first session id retained); a second binding INSERT is not required per arm.

Session creation uses governed Paper forward-test API / `ForwardTestService.create_session` with full campaign identity (`campaign_id`, `manifest_fingerprint`, cohort arms). **SIGNAL_ONLY** — no Paper order preview/submit.

Governed session creation (RTH open only; appends `governed-session-start-evidence.jsonl`):

```powershell
$env:IMP_PERSIST_STATE = "1"
python tools/imp.py ftep session-start FTEP-V1-002 --json
```

Expect two `sessions_created` entries (`BASELINE`, `AI_ENHANCED`), zero `session_errors`, and a non-empty `evidence_paths` list. Re-run `campaign-status` afterward — `governed_session_count` must match durable SQLite (still **zero orders**).

## Empirical catalyst attention pipeline (operator)

`ForwardTestService` does **not** spawn a post-session or background catalyst listener. Intelligence for FTEP-V1-002 remains `RECORDED_ARTIFACTS_ONLY` at the session-policy layer; observational live news ingress (`IMP_OBSERVATIONAL_NEWS_INGRESS=1`) is scaffolding only and is **not** auto-wired into forward-test `observe` paths ([PAPER_FORWARD_TESTING_BRIDGE.md](../../docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md)).

During an **active governed SIGNAL_ONLY session** (after both cohort `create_session` calls succeed, US_EQUITY_RTH open):

1. Keep persistence on (`IMP_PERSIST_STATE=1`).
2. Refresh headline context (owner credentials; no secrets in logs): `python tools/finviz/probe.py` — append probe receipt paths to the wave operator log.
3. Run the **event-driven attention collector dry path** on fixture or exported rows (does not create locks or orders):
   ```powershell
   python tools/imp.py ftep opportunity-summaries --json
   # or campaign fixture:
   python tools/imp.py ftep opportunity-summaries --input artifacts/forward-test-campaigns/FTEP-V1-002/opportunity-attention-fixture.json --json
   ```
4. Correlate ranked summaries with open `session_id`s from `governed-session-start-evidence.jsonl` in the operator log. Do **not** call `create_decision` / lock APIs unless a separate owner authorization increment explicitly enables empirical locks (`empirical_lock_authorized` remains false in the frozen manifest).

When **US_EQUITY_RTH is closed** (weekends, holidays, outside 09:30–16:00 America/New_York), run **fixture smoke only** — steps 2–3 with `--input` fixture or `--sample`; skip live Finviz probe and skip `session-start` without `--dry-run`.

## Safety

- Paper orders: **0**
- Live orders: **0**
- Post-freeze manifest mutations: **0**
