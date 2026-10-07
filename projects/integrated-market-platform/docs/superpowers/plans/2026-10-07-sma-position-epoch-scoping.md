# SMA position epoch scoping correctness repair

Classification: **SOFTWARE_CONTROLLED**. Base: `e411ec1edd39d50a50aa0c400c7d5dd02bea143b` (post-PR-468). Implementation and integration receipts are recorded by the PR and Git history.

## Failure map and red evidence

The old `position_epoch()` scanned every account `PositionChanged` row with one `previous` quantity and one `opening` pointer. Inputs hashed after that scan were account, session, requested instrument, side, selected opening fill ID and selected sequence. Instrument was present in the hash but missing from the transition scan. Experiment identity was implicit in the account rather than explicit. This was incorrect opening lineage, not a literal equal-hash collision.

On the exact base, real $100k portfolio ledger fills demonstrated:

- AAPL BUY 10 / NVDA BUY 10: NVDA selected AAPL's opening fill (red assertion failure).
- AAPL open / NVDA open then fully closed: AAPL's epoch became `None` although AAPL remained open (red assertion failure).
- AAPL close/reopen with an intervening NVDA scale-in: the reopening epoch selected NVDA's fill instead of AAPL's reopening fill (red assertion failure).
- AAPL stop active / NVDA close / AAPL partial close: AAPL's stop ID rolled unexpectedly (red service assertion failure).
- AAPL close/reopen before reevaluation: read-only status exposed the old stop and decision facts (red service assertion failure).

Tests: [epoch regressions](../../../tests/intelligence/test_sma_position_epoch_scope.py), [governed integration acceptance](../../../tests/trading_correctness/test_trade_lifecycle.py). Original single-instrument epoch baseline passed. The first weaker reopen assertion passed and was strengthened to require the exact reopening fill before implementation.

## Correct identity and affected surfaces

`position_epoch()` scopes transitions to canonical instrument identity, resolving an untagged legacy row only through its explicit FillRecorded ID. Unknown/conflicting fill instrument lineage fails closed. Ledger sequence orders transitions; event timestamps never define boundaries. Partial reductions and additional entry fills preserve the opening fill; flat/reversal changes it.

For portfolio experiments, the epoch is exactly OCT1-10 `episode_identity(account_id, experiment_id, instrument_id, opening_fill_id)`: `TE-` plus the existing canonical serialized SHA-256 convention (128 hash bits). Legacy instrument-scoped ledgers use session ID as the experiment namespace. No new independent episode authority is introduced.

Persisted state version is `sma-trailing-stop-state/1.1.0`; identity semantics are `sma-position-epoch/2.0.0`. The unchanged status/history envelopes continue to expose opaque string IDs with additive lineage fields. Clients do not parse the prefix. The reference policy and formula version remain unchanged.

Affected modules: risk epoch/event contract; stop service evaluation/status/decision/EXIT reads; stop persistence exact episode lookup; deterministic ActionDecision server_exit lineage; lifecycle stop/history joins. Existing SQLite payload tables and account/instrument indexes are reused. Frontend schemas accept opaque IDs and additive fields. Research stop methodology and OCT1-11 metrics are unchanged.

## Compatibility

Historical policies, decisions, events and OCT1 receipts are not rewritten. A v1 state is readable only if its legacy hash matches the corrected current instrument opening fill, sequence, account, session and side. Safe reads project the canonical episode without writing. Evaluation migrates the state payload while preserving stop ID, level, terminal breach, update history and legacy epoch reference. This preserves historical stop-state references.

A mismatched v1 identity yields `BLOCKED / LEGACY_POSITION_EPOCH_AMBIGUOUS`, hides actionable stop facts, performs no stop update and generates no EXIT. No symbol/account/timestamp guessing is used. Ambiguous historical state remains available by its original stored identity; explicit operator review/configuration is required. Portfolio positions with no opening fill fail closed. The pre-existing no-fill monitor fallback remains solely for non-portfolio fixture/legacy projections; it is versioned and is never used for portfolio experiments.

Read-only status and decision facts verify the current episode before returning active state. A full close/reopen therefore hides the former stop immediately, before evaluation. Lifecycle joins modern state and history by canonical episode, account and instrument; legacy explicitly referenced historical records remain historical. Repository history stays bounded; exact episode state lookup also includes closed activations.

## Controlled acceptance

Production policy, stop service, ActionDecision, governed handoff, Paper preview/submit/risk/simulator, portfolio ledger, SQLite and lifecycle projection were exercised. Provider bars/quotes, marks, candidate receipts/model proposals, clock and harness auth were fixtures.

AAPL stop 145 / NVDA stop 238; AAPL tightened to 147 with NVDA unchanged, then NVDA tightened independently to 240. AAPL quote 141 breached only AAPL. AAPL deterministic EXIT retained account, experiment, instrument, canonical episode and stop ID; position stayed LONG until explicit governed Paper close. At breach, fills and explicit submits remained 2, model calls remained 2 (zero incremental calls), and Live attempts remained 0. A fresh process restored AAPL's breached 147 state and NVDA's 240 state with identical IDs.

Explicit revalidated close flattened AAPL. A later governed BUY 3 reopened AAPL with new epoch `TE-383c0bcd9c375e80dab118d86c7e00aa`, stop 140, null previous stop/carry/breach, while NVDA retained 240. The former AAPL epoch was `TE-c518ecc4c2e828ec4f37c40f6e40923f`; NVDA was `TE-2c9fab284ddc218c9ef364174745770a`. Reentry after restart did not inherit old state. A second real process restart after reopening restored the new AAPL 140 stop and unchanged NVDA 240 stop with identical episode IDs. The production Vite bundle displayed both lifecycle detail panels, deterministic AAPL EXIT with position still open, and the clean new AAPL episode. Earlier-run active positions remained visible.

SMA completed-bar admission, no same-bar lookahead, long max/short min clamps, safety precedence and manual execution boundaries are unchanged. No automatic Paper or Live submit and no model dependency was added.

## Performance and complexity

Two-position fixture, 14 ledger events; 1,000 samples except 50 SQLite restores. Median / p95 microseconds: epoch 14.2 / 17.3; scoped stop lookup 9.3 / 11.0; stop history projection 16.1 / 19.3; opening SQLite and restoring two scoped states 4,765.35 / 5,969.2. These are local software timings, not market latency or broad performance claims.

Epoch reconstruction scans ledger history and sorts ledger sequence (`O(n log n)` worst case); stop lookups retain the existing account/instrument SQLite index. Episode lookup filters JSON after instrument scope; memory lookup scans current records. History remains indexed/bounded in SQLite. No indexing project or cached lifecycle authority was introduced.

## Validation and retained unsuccessful attempts

- FAST base: 23 run, 0 skipped, 0 failures/errors, 12.212s; observe-only SEVERE_REGRESSION versus historical timing baseline.
- Focused relevant Python suites: 257 run, 0 skipped, 0 failures/errors, 33.248s.
- Governed multi-position focused acceptance: 1 passed, 0 skipped/failures/errors, 7.791s (discovery 2.707s).
- CHANGED: 5,512 run, 43 skipped, 0 failures/errors, 413.997s; preliminary core checkpoint flag retained.
- UI: 179 files / 1,374 tests passed, 109.44s; typecheck passed. Production build passed, 8.61s; entry 100.76 KiB gzip under 200 KiB.
- Final FAST: 23 run/passed, 0 skipped/failures/errors, 5.789685s; timing remains observe-only SEVERE_REGRESSION.
- Final review tests: 51 run/passed, 0 skipped/failures/errors, 19.631s, including persisted legacy ambiguity and terminal breach preservation.
- Format/lint, docs links (292 governance files), monorepo/history guards and their nine isolated tests passed.
- FULL: **8,173 run / 8,120 passed / 53 skipped / 0 failures / 0 errors**, 411.852267s, not interrupted. Exact canonical FULL selection with default two workers passed in an isolated Windows console group; no runner/test changes. Structured results retained locally and normalized in the acceptance receipt.

`POSITION_EPOCH_REGRESSION`: five concrete red assertions above. `TEST_HARNESS`: invalid file/class-only focused selectors ran zero tests; exact method selectors used thereafter. Governed fixture initially requested quantities above approved risk and lacked consistent price/mark facts; corrected fixtures, no weakened gates. Windows test-file encoding briefly caused an import error; UTF-8 restored. Browser harness restart initially lacked a post-signal bar and reused an Opportunity counter; rejected attempts were retained, clock continuity and unique fixture Opportunity IDs corrected. An old EXIT handoff rejected changed inputs; operator revalidation used the unchanged production path. A receipt script accessed absent optional reason_codes after a successful fill; ledger verified the completed fill before continuing. Browser panel reload requires reopening the panel; direct DOM button activation was used when CLI clicks did not expand detail. Initial Vite npm argument forwarding failed; direct Vite CLI served the built bundle. Benchmark initially lacked the test package import path; corrected to `src;.`.

Two multi-worker FULL attempts ended with `KeyboardInterrupt`: 210 passed, 0 skipped/failures/errors, 134.343126s and 114.381897s. Classification `UNKNOWN`; no cause established and neither counts as completed FULL. A detached attempt ended before producing a result (`ENVIRONMENT`). A serial attached FULL also received KeyboardInterrupt after 2,059 run, 2,054 passed, 5 skipped, zero failures/errors, 228.070s (`UNKNOWN`). The successful final attempt used an isolated Windows console group with the same canonical FULL selection; no runner or tests were changed. Initial root guard module imports resolved a third-party tests namespace (`TEST_HARNESS`); file-based discovery then passed all nine checks.

## Review and limitations

Reviewed account/instrument/experiment identity, opening fill boundaries, partial/scale-in stability, old state leakage, restart, ambiguous legacy state, deterministic EXIT and execution authority. Corrected newest stop activation selection and included scope metadata in new stop events. The close/reopen stop history is joined by episode rather than inferred from symbol.

This is software correctness evidence only. No prospective market validation, simulator calibration, new asset support or trading authority is claimed. Existing explicit handoff revalidation, provider freshness and bounded-history behavior remain their own authorities. No subsequent lane was started.
