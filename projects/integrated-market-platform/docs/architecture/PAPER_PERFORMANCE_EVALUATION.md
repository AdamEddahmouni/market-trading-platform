# Paper performance evaluation — rebuild step 8

Status: implemented software; prospective market acceptance remains separate.
Internal Paper simulation only. No service, task, experiment, order or model is started by enrollment.

## Owner-approved measures

The owner approved step 8 implementation on 2026-10-26, choosing completed
position episodes, SPY including reinvested dividends, mixed-run labeling for
manual fills, and both fixed-calendar and covered-session reporting.

Day 10 requires account equity strictly above starting capital.
Day 20 requires at least 30 completed trades, positive return after costs,
and return strictly greater than SPY over the same interval. Ties fail.
Conditions are independent: a failed day 10 does not stop day 20.

One completed trade is a per-instrument flat-to-flat episode, including shorts.
Adds and partial reductions do not inflate the count. A reversal completes the
old episode and opens a new one. Ownership is read from canonical order client
identifiers; automation close-outs count even without an AI decision identifier.
Any manual fill makes the whole account mixed and withholds an AI pass. Values
are never recomputed by discarding manual trades, gap losses or bad sessions.

## Enrollment, timing and continuity

Only an active, prospective, flat and completely untraded portfolio experiment
may enroll. Internal simulation, Paper-only authority and matching account and
session are required; Demo, broker-paper and Live execution cannot enroll.
The automation policy and resolved AI engine/model must be configured.
The account, ledger policy, automation policy, model, prompt and code identity
are bound at enrollment. Pre-start fills or material configuration drift prevent
a clean pass.

Day 1 is the next full reporting session. Both clocks start with the experiment's
initial capital and SPY's day 1 regular-session open. Fixed day 10/day 20 retain
their original closes. Covered milestones use the tenth/twentieth covered
session, with all intervening account returns, costs and SPY returns retained.
They are supplemental and cannot replace a failed or incomplete fixed result.

The separate, versioned 2026 reporting calendar includes holidays, daylight
saving transitions, and 13:00 ET closes on November 27 and December 24.
Unsupported years are unavailable; enrollment requires a verified 20-session
schedule. This does not amend the execution calendar or validate early-close
trading behavior.
Source: [official NYSE 2026 calendar](https://www.nyse.com/publicdocs/nyse/ICE_NYSE_2026_Yearly_Trading_Calendar.pdf).

A covered session needs current, complete opening and closing observations
within 60 seconds of the boundaries, usable SPY evidence, and no observation
gap over 120 seconds. Zero trades is valid coverage. Invalid valuation rows
are excluded and explicitly reported. Restarts retain the original run,
boundaries and gaps. Historical SPY recovery cannot invent operational coverage.

## Capture and accounting

The existing platform launcher owns a passive 60-second in-process observer
and a separate bounded benchmark worker. They are independent of browser views
and AI inference duration. They do not configure, arm, start, resume, submit,
cancel, or change execution gates. Capture reads already-owned price streams
into a detached ledger copy; it does not subscribe or persist marks onto the
trading ledger. Failures remain reporting failures and leave a visible gap.

Account-scoped append-only records hold enrollment, ledger inputs, original
valuation/mark clocks and quality, configuration identity, controller state,
benchmark responses, refresh requests, and immutable report revisions. Memory
mode is explicitly labeled non-durable. SQLite uses the existing local-state
connection and indexed evaluation tables; no market-stream scans are needed.

Session-close accounting replays only original events and fills through the
exact cutoff, using admissible marks at or before that cutoff, at most 60 seconds
old. A timestamp argument on the current ledger is not historical replay.
Missing marks remain unavailable. Commissions, fees and posted borrow are
already included in ledger equity and are not subtracted again. Incurred,
unposted borrow uses the canonical borrow calculator on a detached clone and
is shown separately; reported net equity deducts it exactly once.

## SPY and evidence revisions

The bounded existing Moomoo quote transport requests raw daily SPY prices and
full dividend/split records. Fractional shares are bought at day 1's open.
Cash dividends are reinvested at the ex-date close; purchases on that ex-date
are not entitled to its dividend. Splits adjust shares. The benchmark has no
fees or taxes. Additive forward-adjusted prices are not treated as total return.

Unentitled, incomplete, truncated, malformed, unsupported or missing adjustment
data withholds the comparison. A missing benchmark day cannot be skipped.
Simultaneous dividend/split actions with an unverified per-share basis refuse
the comparison. Raw sanitized responses, retrieval times and hashes are kept.
Sources: [daily prices](https://openapi.futunn.com/futu-api-doc/en/quote/request-history-kline.html),
[adjustment records](https://openapi.futunn.com/futu-api-doc/en/quote/get-rehab.html).

Explicit benchmark refresh queues bounded work and produces a new report
revision. Previous report IDs and their original evidence remain readable.
A failed fetch cannot erase previously verified cached benchmark evidence.

## API and user interface

All routes are under `/evaluation/paper-performance/runs` and scope to the
current Paper account. GET requires `audit.read`; POST requires `state.write`,
never order authority.

| Method | Suffix | Behavior |
| --- | --- | --- |
| POST | root | Enroll with only `experiment_id` |
| GET | root | List this account's enrolled runs |
| GET | `/{run_id}` | Read latest saved report, or `?report_id=...` |
| GET | `/{run_id}/export?format=html\|csv&report_id=...` | Download that exact saved revision |
| POST | `/{run_id}/refresh-benchmark` | Empty body; queue evidence revalidation |

Reads and exports perform no capture, provider calls, inference or trading.
Reports use `paper-performance/1.0.0`. They include both clocks, condition-level
verdicts, daily account/SPY values, coverage gaps, completed trades, costs and
evidence hashes. Verdicts are Not due, Pass, Fail, or Cannot determine.

The existing Paper portfolio link opens the Evaluation page. Its scorecard,
gap-preserving equity chart, costs and daily table coexist with existing
prospective outcome/evidence reports. Standalone escaped HTML and CSV use the
same frozen report ID as the screen; no external assets are needed.

## Verification and limits

Tests use temporary databases, controlled clocks, fixture fills and SDK doubles.
The real state database, scheduled tasks, services and paid AI remain untouched.
No live SPY entitlement, continuous market operation or profitability has been
established. Fresh market-data and release acceptance require separate owner
authorization. The three previously recorded full-suite baseline issues are
outside step 8.
