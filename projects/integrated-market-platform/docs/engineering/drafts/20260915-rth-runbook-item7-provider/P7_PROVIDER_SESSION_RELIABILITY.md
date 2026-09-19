# P7 — Provider / session reliability (2026-09-15 evidence only)

**Classification:** `EXPERIMENTAL` diagnosis
**Not canonical.** Frozen RTH `.rth-operator-20260915` SHA
`7aade60bf8041df5ebf9f0ac856d5d8802845c8d` was not modified. No new providers.

Evidence root (operator copies; gitignored):

`C:\Users\adame\Desktop\market-trading-platform\.rth-operator-20260915\projects\integrated-market-platform\.local\rth-session-20260915\`

Canonical durable state used by the session:

`C:\Users\adame\Desktop\market-trading-platform\projects\integrated-market-platform\.local`

Python: IMP `.venv` 3.11.15. Enrichment worker unset / `worker_enabled=false`.
Live OFF. FTEP not `EMPIRICAL_ACTIVE`. Empirical locks **0**.

## 1. Finviz gates (three-part, fail closed)

`prospective_catalyst_ingress_enabled` requires **all** of:

1. `IMP_FINVIZ_LIVE` in `{1,true,yes}`
2. a configured Finviz Elite token (`configured_token`)
3. `IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS` in `{1,true,yes}`

Missing token is the same blocker as missing env flags:
`INGRESS_GATES_INACTIVE` → `PROSPECTIVE_CATALYST_INGRESS_GATES_INACTIVE` →
`watch_mode=SESSION_ACTIVE_CORRELATION` (not prospective ingress).

| Stamp (ET) | Exit | Watch mode | Ingress | Notes |
|---|---:|---|---|---|
| 09:33 | 1 | `SESSION_ACTIVE_CORRELATION` | `LIVE_INGRESS_FAILED` / `INGRESS_GATES_INACTIVE` | Env flags recorded; frozen worktree `.private` had **no** token |
| 09:36 | 1 | same | same | Same blocker; no HTTP fetch |
| 09:39 | 0 | `PROSPECTIVE_FINVIZ_INGRESS` | `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS` | Token via `IMP_FINVIZ_SECRET_DIR` → **primary** IMP `.private` |
| 10:01 | 0 | `PROSPECTIVE_FINVIZ_INGRESS` | `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS` | 100 ingested / 19 universe-filtered / 0 accepted |
| 10:48 | 0 | `PROSPECTIVE_FINVIZ_INGRESS` | `LIVE_INGRESS_SUCCESS` | 1 qualifying row (NVDA / management); planned 10:30, late 10:48 |

Operator rule: never copy `.private` into worktrees. Point
`IMP_FINVIZ_SECRET_DIR` at the primary checkout `.private`. Env flags without a
token still fail closed.

Zero qualifying rows at 09:39 / 10:01 is **valid prospective evidence**, not a
provider outage. Credentials appeared to work once the secret dir was correct.

## 2. Live-ingress is one-shot, not a persistent watch

`tools/ftep_watch_catalysts.py` fetches once and exits. Observed durations
3–7 seconds. `dry_run=true`, `durable_lock=false`. No daemon, no loop.

A PASS receipt is a **single** Finviz page at ingest time. It does not keep
FTEP watching the tape. Rechecks require a new command (planned 10:00, 10:30,
12:00, …). `python tools/imp.py ftep watch-catalysts` does **not** pass
`--live-ingress`.

Ops layer `rth_empirical_ops.py run-observational` refuses live ingress
(`LIVE_INGRESS_REFUSED_BY_OPS_LAYER`). Use the delegated CLI.

## 3. FTEP ingress ≠ opportunity cockpit / live discovery

Same session:

- FTEP CLI can PASS (`LIVE_INGRESS_SUCCESS`, NVDA catalyst, both governed
  sessions correlated, no auto lock).
- Opportunity / Live observational path independently reports
  `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`, ranked items `[]`,
  `opportunity_operator_acks=0` (see P8).

Those are **different pipes**. A Finviz FTEP row is not a cockpit opportunity
and is not Path A OE mint. Do not treat empty Live discovery as a Finviz
outage, and do not treat FTEP PASS as cockpit coverage.

SPA `/discover` is an API-proxied route, not the FTEP ingress surface. Opening
it from the launcher is a routing bug (P10), not a provider bug.

## 4. OpenD quote vs kline

Transport is one loopback quote context (`127.0.0.1:11111`, `moomoo_OpenD.exe`).
Quote **connect** and history **kline** are different vendor calls.

On this base SHA, `fetch_history_kline_1m` uses
`request_history_kline(..., start=None, end=None, max_count=...)`. The vendor
expands that to `[today-365d, today]` and returns the **oldest** page.

| Surface | Today's evidence |
|---|---|
| Quote connect | Succeeded through poll #1 (750 cycles) and poll #2 (212 cycles). TCP 11111 stayed up after protocol-error exit. Not `MOOMOO_AUTH_FAILURE`. |
| History kline | Poll #1: bars returned but none with `available_time > signal_time` → `PROSPECTIVE_NO_POST_SIGNAL_BAR`. Poll #2: `MOOMOO_PROTOCOL_ERROR` on kline fetch (RET_OK miss or SDK exception). |
| Snapshot / last_price hop | Separate Path A quote path; not a 1m bar receipt. |

Do not add a second quote provider. Software follow-up (not this SHA): request
the **session-day** window (`start=end=YYYY-MM-DD`, `max_count>=1000`) and
reuse one quote context / `get_cur_kline` so a 5s history loop does not burn
`historyKLQuota`. That repair lives on `diagnosis/item9-prospective-bar-20260915`
and is **not** on `origin/main` `7aade60b`.

## 5. CallClose is poll-iteration close, not a transport drop

SDK logs `on_disconnect: ... reason=CallClose` about every 5s because the
prospective poll opens a quote context, fetches, then `close()`s. First-poll
inspection: "CallClose only; expected per-iteration close; not a transport
drop." Hour-2: "CallClose only until exit; OpenD TCP still true after exit;
not a GUI login drop."

Do **not** treat CallClose as OpenD crash, logout, or entitlement loss.

## 6. History quota

A 5s `request_history_kline` loop on a 3900s timeout (~750 iterations) is a
quota-hostile pattern. Poll #2 protocol-error after ~19m (and resume ~33m /
358 CallClose cycles) is consistent with kline-path pressure, **not** proven
as a numeric `historyKLQuota` counter in today's receipts. Do not invent a
quota remaining figure. Software should stop re-paging year-old history every
5 seconds.

## 7. Item 9 poll #1 and poll #2

Contract `item9.bar-ohlcv-prospective-proof/1.1.0`. No versioned receipt file
was written (`receipt=null`, `orders_placed=false`, `calibrated=false`).

### Poll #1 — `PROSPECTIVE_NO_POST_SIGNAL_BAR` (oldest-page kline)

- Experiment: `item9-prospective-20260915-rth-aapl`
- 09:34:30–10:39:31 ET, exit 1, full 3900s, 750 quote-connect iterations
- PIT correctly refused year-old bars (`available_time > signal_time` failed)
- Outcome JSON is **not** a versioned receipt

### Poll #2 — `MOOMOO_PROTOCOL_ERROR`

- Experiment: `item9-prospective-20260915-rth-aapl-hour2`
- 10:41:13–11:00:00 ET, exit 1, ~19m, not a full timeout
- Quote connect succeeded through 212 iterations; last cycle fail-closed on
  kline; governed poll does not retry this reason
- Resume 11:07:37–11:40:11 ET same `MOOMOO_PROTOCOL_ERROR` (358 CallClose
  cycles). Gap after resume was **not** backfilled.

`ITEM9_PROSPECTIVE_BAR_RECEIPT_CAPTURED` remains unearned. Simulator remains
**not** `CALIBRATED`.

## 8. What this is not

- Not a Finviz Elite outage after 09:39.
- Not a new provider requirement.
- Not FTEP `EMPIRICAL_ACTIVE`.
- Not cockpit / OE coverage.
- Not Item 7 rows.
- Not permission to thaw frozen RTH or edit doctrine.
