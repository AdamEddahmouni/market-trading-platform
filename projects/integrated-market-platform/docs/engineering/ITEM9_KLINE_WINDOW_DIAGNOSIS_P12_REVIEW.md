# Lane P12 — adversarial review of Item 9 kline-window diagnosis

**Status:** `PARTIALLY_CONFIRMED`  
**Reviewer lane:** P12 (falsify, do not patch)  
**Diagnosis under attack:** agent `819114a1` (`diagnosis/item9-prospective-bar-20260915`)  
**Poll SHA:** `7aade60bf8041df5ebf9f0ac856d5d8802845c8d`  
**Review branch:** `review/item9-kline-diagnosis-20260915`  
**Isolation:** frozen `.rth-operator-20260915` not edited; no live Lane B PIDs signaled; no OpenD `request_history_kline` issued during this review (hour-3 poll was running). PIT / `available_time > signal_time` not loosened. **No calibration claim.**

---

## Verdict

| Claim | Classification |
|---|---|
| Overall causal story | **PARTIALLY_CONFIRMED** |
| `start=None, end=None` expands to `[today-365d, today]` | **CONFIRMED** (SDK source) |
| First page is oldest-first | **CONFIRMED** for `K_DAY`; **NEEDS_MORE_EVIDENCE** for `K_1M` |
| Poll #1 returned year-old 1m bars that PIT then rejected | **NEEDS_MORE_EVIDENCE** (stdout never captured rows) |
| Timeout reason uniquely means post-signal PIT reject | **DISPROVEN** as unique (collapsed codes) |
| Not timezone / ns unit bug | **PARTIALLY_CONFIRMED** (clock looks wall-ns; 1m TZ unobserved) |
| Not AAPL mapping | **CONFIRMED** |
| Not quiet tape | **CONFIRMED** (not a sufficient cause) |
| Hour-2 `MOOMOO_PROTOCOL_ERROR` is `historyKLQuota` from the same path | **DISPROVEN** as unique-security quota; error string never logged |
| Candidate fix `start=end=America/New_York session date` | **PARTIALLY_CONFIRMED** as necessary *if* oldest-first |
| Candidate `max_count>=1000` | **CONFIRMED** as required *if* session-day + oldest-first; `120` would still miss RTH |

P2 may still patch the window. Do not treat the diagnosis as empirically proven 1m paging, and do not land session-day with `max_count=120`.

---

## What poll #1 actually showed

Poll `#1` (`item9-prospective-20260915-rth-aapl`): 2026-09-15 09:34:30.709–10:39:31.666 ET, 750 connect/`CallClose` cycles, exit 1, `PROSPECTIVE_NO_POST_SIGNAL_BAR`, `receipt=null`.

Stdout is SDK connect/close plus the timeout JSON. It does **not** print:

- `raw_row_count`
- first/last `time_key`
- `k_ret` / vendor `retMsg`
- whether rows were empty vs year-old vs today-dropped-by-PIT

So the diagnosis sentence “SDK [today-365d, today] oldest page → time_key 2025-09-15 → PIT rejects year-old bars” is a **mechanism inference**, not an observed 1m page.

### Timeout code is not diagnostic

`poll_prospective_proof` retries both `PROSPECTIVE_NO_POST_SIGNAL_BAR` **and** `EXPERIMENT_CONTRACT_MISMATCH`, then reports `PROSPECTIVE_NO_POST_SIGNAL_BAR` at deadline.

`load_moomoo_opend_kline_bars` returns `EXPERIMENT_CONTRACT_MISMATCH` when:

- vendor rows are empty, or
- every row fails `normalize_moomoo_kline_row` (`bar_end > fetched_at`, bad `time_key`), or
- `pit_visible_bars` drops everything (`available_time > observation_time`).

`run_prospective_proof` returns `PROSPECTIVE_NO_POST_SIGNAL_BAR` only when the loader **succeeds with non-empty visible bars** and none satisfy `available_time > signal_time`.

Therefore poll #1 is compatible with **all** of:

1. 120 year-old 1m bars (diagnosis),
2. empty 1m dataframe (`RET_OK` + no rows),
3. today’s bars all dropped by `bar_end > fetched_at` (timezone / incomplete-bar if the page is current).

Without `raw_row_count` / `time_key` on the poll outcome, (1) is not proven.

---

## Attack results

### 1. Returned bars vs empty?

**NEEDS_MORE_EVIDENCE.** Transport discards `page_req_key` (`_page`). `fetch_history_kline_1m` maps any `k_ret != RET_OK` to `MOOMOO_PROTOCOL_ERROR` with **no `retMsg`**. Poll #1 ran ~65 minutes without that exit, so kline calls were not failing closed that hour. That is **not** the same as “120 year-old rows”.

Capability-report `time_key` `2025-09-15 00:00:00` is from probe `K_DAY` `max_count=5`, sampled via `schema_inventory(rows[:1])`. It is not a `K_1M` observation.

### 2. Could entitlement hide 1m while quotes work?

**Unlikely for poll #1; not disproven for empty 1m.** `US_EQUITY_BARS` in the capability report is entitled from **daily** history, not 1m. A 1m-denied account would typically `RET_ERROR` → immediate `MOOMOO_PROTOCOL_ERROR`. 750 cycles argue against that. Empty `RET_OK` 1m remains possible and would timeout as `PROSPECTIVE_NO_POST_SIGNAL_BAR`. Snapshots were **not** called on the poll path (`get_global_state` + `request_history_kline` only).

### 3. Could `signal_time` be in the future so even today’s bars fail PIT?

**DISPROVEN as a clock-unit/future-signal bug.** CLI records `signal_time_ns = monotonic_wall_ns()` = guarded `time.time_ns()`. Log wall times are 2026-09-15 09:34 ET. Prospective mode refuses `--signal-time-ns`. A completed 09:35 ET bar would have `available_time > 09:34:30` if it were in the page.

### 4. Could `bar_end > fetched_at` hide all current bars?

**Not as a complete explanation unless the page is current and timezone is wrong.** Incomplete current minute is dropped on purpose (`normalize_moomoo_kline_row`). At 09:34+ ET, completed 09:30–09:33 bars would pass `fetched_at` if `time_key` is America/New_York. Naive keys are localized to `America/New_York`. Futu US daily sample `00:00:00` is session-date, not UTC midnight. **1m timezone is still unobserved.** If paging is newest-first **and** 1m `time_key` is UTC-naive-as-ET, today’s bars could all look future and collapse to `EXPERIMENT_CONTRACT_MISMATCH` → same timeout. That alternative is **not** killed by poll stdout.

### 5. Is oldest-first definitely SDK behavior on 1m, not just K_DAY?

**NEEDS_MORE_EVIDENCE for K_1M; CONFIRMED for K_DAY.**

SDK facts that **are** confirmed:

- `normalize_start_end_date(..., 365)` with `prefer_end_now=True`: `None/None` → end=local today 23:59:59, start=today−365d 00:00:00.
- `max_count` is a page size; `nextReqKey` continues the range. First call uses `beginTime` of that window.
- Proto: `beginTime` / `endTime` / `maxAckKLNum` / `nextReqKey`. Same API for all `klType`.

K_DAY evidence (2026-09-15 probe): `row_count=5`, first sampled `time_key=2025-09-15 00:00:00`, close ~235.8 (year-old AAPL, not 2026). Newest-first would have shown a 2026 session date. **Oldest-first on K_DAY is real.**

That does **not** prove the first `K_1M` page on this account starts at 2025-09-15 09:30. 1m history depth may be shorter than 365d; the first available 1m bar might be days/weeks old and still entirely `< signal_time`. Diagnosis tests use a **fake** oldest-first catalog — they encode the assumption rather than observe OpenD 1m.

### 6. Could `max_count=120` still miss RTH if the window is correct?

**Yes — CONFIRMED as a patch hazard, even if the diagnosis is right.** Vendor history is oldest-first *inside* `[start, end]`. `extended_time=True`, `Session.ALL`: a session-day window starts at premarket (~04:00). First 120 minutes ≈ 04:00–05:59, all `< 09:34` signal. PIT would still return `PROSPECTIVE_NO_POST_SIGNAL_BAR`. The diagnosis’s `max_count>=1000` (SDK per-request cap; ~960 extended 1m bars) is the part that actually covers RTH. P2 must not ship session-day + `max_count=120`.

Diagnosis fake tests never filled a session day with 330+ premarket minutes; they only proved that a tiny today catalog is visible once the 365d window is closed.

---

## Hour-2 protocol error

Hour-2: 212 cycles, then `MOOMOO_PROTOCOL_ERROR` (last connect 10:59:50, JSON, `CallClose` 11:00:00 — ~10s vs typical ~200ms). No `retMsg`.

Hour-2-resume: **358 more** successful connect/close cycles, then `MOOMOO_PROTOCOL_ERROR` again at 11:40:11 ET.

Vendor `Qot_RequestHistoryKLQuota`: `usedQuota` = unique securities downloaded this period, not per-request count. Repeating `US.AAPL` should not consume 750+ quota units. Resume succeeding for ~33 minutes after hour-2’s alleged quota death **falsifies** “unique-security `historyKLQuota` exhausted, therefore the same path is dead.”

Remaining live explanations (not distinguished): request-frequency / timeout, OpenD connect-churn every 5s, swallowed exception, intermittent protocol. Transport still throws away `retMsg`. P2 should log vendor message **without** treating that as calibration.

---

## Claims the diagnosis got right (keep)

- Poll #1 is not quiet-tape: AAPL RTH for 65 minutes.
- Mapping `AAPL` → `US.AAPL` is not the defect.
- `None/None` 365-day expansion is real and is the wrong window for a prospective 1m first-post-signal bar.
- PIT must keep rejecting year-old bars. Do not admit them.
- Session-day window **plus** a page large enough to include post-signal RTH is the smallest history-kline repair **if** paging is oldest-first.
- `get_cur_kline` / persistent quote context is a follow-up, not required to accept the window bug.

---

## P2 constraints (do not weaken PIT)

1. Do not treat fake-SDK oldest-first tests as empirical 1m proof.
2. Log `raw_row_count`, first/last `time_key`, and vendor `retMsg` on fail-closed (observability, not look-ahead).
3. If patching `request_history_kline`: `start=end` NY session date **and** `max_count>=1000` (or page until post-signal bar / session end). `120` is still wrong under oldest-first.
4. Add a test: session-day + oldest-first + 330 premarket 1m bars + `max_count=120` → still `PROSPECTIVE_NO_POST_SIGNAL_BAR`; same catalog with `max_count>=1000` admits 09:35+.
5. Do not flip `calibrated` / `empirical_active` / `item9_status` off `PARTIAL_NOT_CALIBRATED`.
6. Do not issue extra live `request_history_kline` against a running Lane B poll.

---

## Isolation record

- Read-only: lane-b poll #1 / hour-2 / hour-2-resume logs; `opend_quote_transport.py`; `bar_ohlcv_sources.py`; `bar_ohlcv_prospective_proof.py`; SDK `request_history_kline` / `normalize_start_end_date`; capability-report history_kline sample; diagnosis worktree tests (not merged).
- Did not signal hour-3 (PID 95280 / 182852 at review time).
- Did not edit `.rth-operator-20260915`.
- Did not call OpenD.
