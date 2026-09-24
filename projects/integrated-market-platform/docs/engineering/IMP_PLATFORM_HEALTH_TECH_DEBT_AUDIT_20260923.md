# IMP platform health and technical-debt audit — 2026-09-23

**Status:** Audit record. Not a behavior change. Not empirical market proof.

**Evidence class:** `SOFTWARE_CONTROLLED` plus static inspection. No Item 7 rows, no Item 9 calibration, no Live orders, no arm of `RTH-OBS-NEWS-20260924`.

**Audit branch:** `audit/platform-health-tech-debt-20260923`

**Base:** `origin/main` `8562c76ac76c8ca038b18b36ddeb8cf3b382c10c` (merge of #406).

**Companion:** [IMP_PLATFORM_HEALTH_TECH_DEBT_AUDIT_20260923.json](../../artifacts/audits/IMP_PLATFORM_HEALTH_TECH_DEBT_AUDIT_20260923.json)

## Executive technical-health summary

`origin/main` matches the #406 merge. The Sep 24 campaign remains pinned to runtime `c15527221a21d7bc88acefbe0971b6de9292247e` (tree `e77f72208b6547d63dc4b7101c5cfa357114052b`), state `FROZEN_NOT_ARMED`, and its state directory `.local/rth-campaign-20260924` was absent in the audit worktree and in the main checkout. This audit did not arm it.

What this lane actually proved:

- Parent-process exit survival of a detached supervisor, without `CREATE_BREAKAWAY_FROM_JOB`, on this Windows host (`test_00_shell_exit_supervisor_survives_parent_process_exit`).
- Campaign heartbeat, stale detection, role death, clean shutdown, RTH-close classification, recovery that preserves arm/segment, and execution authority remaining blocked (23 heartbeat acceptance tests).
- One open outage row when a required role is dead, and a second status check that does not duplicate it.
- Poll classification that separates an empty success, a provider/process failure, and a software-controlled cycle.
- Controlled Replay golden path from fixture input through Watch/Dismiss, DecisionTrace, and TradeReview, plus Paper preview and durable order-history readback. Evidence class stayed `SOFTWARE_CONTROLLED / FIXTURE_REPLAY`. Reset refuses a non-namespaced directory.
- Mandatory security selectors for offline network denial, credential redaction, and unknown-identifier fail-closed.
- `python tools/imp.py format` and `python tools/imp.py lint` exit 0.

What this lane did not prove:

- Windows job-object or terminal-kill survival. The product flag `job_or_terminal_kill_survival_proven` is intentionally `false`.
- A finished `python tools/imp.py test affected` run. The runner has no test-count cap. Interruption is `KeyboardInterrupt` only. A local durability unittest was itself stopped by `KeyboardInterrupt` during preflight `git rev-parse`.
- Empirical Item 7, Item 9 calibration, Full30, or Live execution. Those locks stay closed.
- UI browser behavior, npm install, or a production dependency upgrade.

`PROGRAM_STATUS.md` still names `CURRENT_MAIN` as `2c40c51c` (#404). That prose is stale. Runtime truth is `8562c76a`. The frozen campaign SHA is a third value and must not be replaced by either tip.

## Repository hygiene

| Item | Observation |
|---|---|
| Starting checkout | Detached `80d290ff`, 146 commits behind `origin/main`. Not the audit tree. |
| Audit worktree | `.worktrees/platform-health-tech-debt-20260923` on `audit/platform-health-tech-debt-20260923` at `8562c76a`. |
| Open PRs at audit start | None. #405 and #406 are `MERGED`. |
| Linked worktrees | Dozens of historical worktrees remain, including merged lanes (`fix-sep24-operator-launch`, `sep24-rth-campaign-freeze`, `sep24-runtime-rehearsal` at superseded `02d69976`). |
| Risk | An agent that opens an old worktree can edit the superseded runtime `02d69976` or a detached review SHA. `.worktrees/` is gitignored. Nothing was deleted. |
| Campaign namespace | Absent. Rehearsal state under `fix-sep24-operator-launch/.local/rehearsal/` was not opened or modified. |

## Subsystem verification matrix

Primary status is one of: `PROVEN`, `TESTED_WITH_LIMITATIONS`, `IMPLEMENTED_BUT_UNVERIFIED`, `KNOWN_BROKEN`, `PARTIALLY_IMPLEMENTED`, `INTENTIONALLY_INACTIVE`, `EMPIRICAL_PROOF_REQUIRED`, `UNKNOWN`.

| Subsystem | Component | Status | Evidence | Limitation | Next action |
|---|---|---|---|---|---|
| Environment | `python tools/imp.py env` | `TESTED_WITH_LIMITATIONS` | Env report `healthy`. Resolved Python 3.11.15 via the main checkout `.venv`. PATH Python 3.10.11 is unsupported and unused. | Worktree has no private `.venv`; it links the main checkout. | Keep using `imp.py env` before validation. |
| Campaign supervision | Parent-exit survival | `PROVEN` | Heartbeat acceptance `test_00` passed on this host. | Does not prove job-kill or console-close survival. | Leave the unproven flag false until a disposable job-kill test exists. |
| Campaign supervision | Job/terminal kill | `IMPLEMENTED_BUT_UNVERIFIED` | `mechanism_description` sets `job_or_terminal_kill_survival_proven: false`. Breakaway is opt-in. | Not retested. A job-kill test can kill the agent session. | Document that tomorrow's launch should be a standalone PowerShell, not a Cursor job. |
| Campaign supervision | Heartbeat, stale, role death, shutdown, recovery | `TESTED_WITH_LIMITATIONS` | 23/23 heartbeat acceptance tests passed. | Software fixtures. Not an armed RTH session. | No code change in this lane. |
| Campaign supervision | Outage ledger | `PARTIALLY_IMPLEMENTED` | Dead-role status appends one open `NOT_OBSERVED` row and does not duplicate it. `interval_end_utc` defaults to null. No production writer sets an end. | Recovery and shutdown leave the open row. Dashboards can treat a recovered gap as still open. | Next implementation lane. |
| Campaign supervision | Poll shutdown latency | `TESTED_WITH_LIMITATIONS` | Default cadence 30s. `poll-loop` sleeps after each cycle, then re-reads ownership. `shutdown` only flips ownership and heartbeat. | One extra poll can run after `RTH_CLOSE_SHUTDOWN` is written. Ownership itself flips immediately. | Next implementation lane. |
| Campaign supervision | Spawn PID | `TESTED_WITH_LIMITATIONS` | Freeze runbook says the `SPAWNED` pid is the Windows shim. `run` writes `ownership.supervisor_pid = os.getpid()`. Register-child test does not clobber that pid. | Operators who register the shim repeat the Sep 23 defect. | Keep the runbook warning. Do not treat shim pid as the supervisor. |
| Campaign supervision | Detached logs | `PARTIALLY_IMPLEMENTED` | `spawn-detached` always opens `detached-child.log` in append mode (`ab`). `detach-flags-used.txt` is overwritten with `write_text`. | Supervisor and poller stdout share one file. Flags from the second spawn replace the first. Not executed as a spawn in this lane (code inspection). | Separate logs per role. |
| Campaign supervision | Finviz preflight | `TESTED_WITH_LIMITATIONS` | Missing `FINVIZ_ELITE_AUTH` / `FINVIZ_AUTH` / `IMP_FINVIZ_ELITE_AUTH` is `WARN` with `required_for_arm=false`, so `ready_to_arm` can stay true. Freeze doc says stop if the first live poll is `TOKEN_ABSENT`. | Arm is allowed without the news credential. The stop rule is after arm. | Operator must confirm token presence before arm. Do not change the freeze contract in this lane. |
| Provider / ingestion | Finviz prospective news | `EMPIRICAL_PROOF_REQUIRED` | Poll classifier distinguishes empty vs failure in software tests. | No live Finviz call in this lane. No token printed. | First lawful poll tomorrow is the proof, on the frozen runtime. |
| Controlled Replay | Fixture to Radar/Watch/Review | `TESTED_WITH_LIMITATIONS` | Golden-path acceptance passed. Live observational context refused. Reset refuses a non-namespaced path. | `SOFTWARE_CONTROLLED / FIXTURE_REPLAY`. Not market proof. | Keep the class label. |
| Paper | Preview, submit, acknowledgement | `TESTED_WITH_LIMITATIONS` | Preview handoff and durable order-history readback passed. Evidence class stayed fixture replay. | No Live submit. Duplicate-submit under concurrency not retested here. | Hardening batch after observation ledger. |
| Security | Offline denial, redaction, unknown id | `PROVEN` | Three mandatory selectors passed via `imp.py test focused`. | Selectors, not a full penetration test. | Keep them mandatory. |
| Item 7 | Governed corpus | `EMPIRICAL_PROOF_REQUIRED` | Freeze lock `NOT_ESTABLISHED`. This lane did not collect rows. | Software tests exist and were not rerun as a scored corpus. | Do not invent rows. |
| Item 9 | Calibration | `INTENTIONALLY_INACTIVE` | Freeze lock `FORBIDDEN` / `PARTIAL_NOT_CALIBRATED`. | Not executed. | Do not calibrate. |
| Smoke10 | Historical scored run | `KNOWN_BROKEN` | Immutable `ibp-smoke10-8C23029DD46FDA78 = FAIL 10/10`. Not rerun. | Historical failure is the record. | Do not relabel. |
| Live execution | Broker submit | `INTENTIONALLY_INACTIVE` | Freeze `LIVE_EXECUTION=OFF`. Replay env test refuses Live. | Not a broker integration test. | Leave blocked. |
| UI | Build, types, routes | `IMPLEMENTED_BUT_UNVERIFIED` | Not built or browser-tested in this lane. | `npm audit` is lockfile-only. | Separate UI contract lane. |
| API | Health and contracts | `IMPLEMENTED_BUT_UNVERIFIED` | Launcher and readiness code exist. This lane did not start the API. | No localhost stack was launched. | Do not start it against the campaign namespace. |
| Docs | `PROGRAM_STATUS` tip | `KNOWN_BROKEN` | `CURRENT_MAIN` cell still says `2c40c51c`. `git rev-parse origin/main` is `8562c76a`. | Docs drift, not runtime drift. | Docs pin update after this audit, without moving the freeze SHA. |
| Test runner | `test affected` | `TESTED_WITH_LIMITATIONS` | `execute_selection` sets `interrupted` only on `KeyboardInterrupt`. No 232-test cap. | Local durability unittest received `KeyboardInterrupt` during preflight `git rev-parse` after 23 passing tests. Full affected suite not finished. | Treat local interruption as harness/stop, not a product failure, until a completed local run exists. |

## Findings registry

### CRITICAL

NONE FOUND.

No data-corruption, Live-enablement, or campaign-namespace write was observed. The frozen campaign was not modified.

### HIGH

1. **Job/terminal kill survival is explicitly unproven.** Severity `HIGH`. Type `HARDENING`. Confidence `PROVEN` (the negative claim is tested and documented). Blast radius: campaign process ownership if the launch parent is a Windows job (Cursor terminal). Parent-process exit survival is proven. Tomorrow's procedure uses `spawn-detached` and does not require the arm shell to stay open for parent-exit. Closing Cursor, or a job with kill-on-close, is the residual risk. Fix urgency `BEFORE_NEXT_RTH` as an operator constraint: launch from standalone PowerShell. A code change cannot be applied to tomorrow without a new freeze.

2. **Finviz credentials do not block arm.** Severity `HIGH`. Type `HARDENING`. Confidence `PROVEN` by preflight code and the freeze runbook. Blast radius: provider lane `finviz_prospective_news`. `ready_to_arm: true` with `credentials_presence_finviz=WARN` is the documented contract. The fail-visible stop is the first poll class `TOKEN_ABSENT` / `GATES_INACTIVE` / `SECRET_DIR_MISSING`. Fix urgency `BEFORE_NEXT_RTH` as an operator check, not a silent contract change on the frozen runtime.

### MEDIUM

3. **Open outage rows are never closed.** Type `BUG` / `OBSERVABILITY`. Confidence `PROVEN`. `record_open_outage_if_changed` appends while `progress.outage` is true and returns without writing when the signature is unchanged or when the outage clears. `cmd_shutdown` does not touch the ledger. `interval_end_utc` is only set by the builder default `None` and by one test that passes it explicitly. Consequence: a gap during arm-to-register, or a later recovery, leaves a row that still looks open. Urgency `NEXT_HARDENING_BATCH`. Safe to implement on `main` while the freeze stays pinned.

4. **Poller observes shutdown only after the current sleep.** Type `BUG`. Confidence `PROVEN` by code. Default poll cadence is 30 seconds. Maximum extra wait is one cadence. `RTH_CLOSE_SHUTDOWN` is durable immediately; the process may invoke one more cycle afterward. Urgency `NEXT_HARDENING_BATCH`. Does not by itself extend the ownership window.

5. **`spawn-detached` reports the shim pid and shares one log.** Type `OBSERVABILITY`. Confidence `STRONGLY_SUPPORTED` (runbook plus `Popen.pid` and `open("ab")`). The durable pid is `ownership.supervisor_pid` after `run` adopts `os.getpid()`. Two children append to `detached-child.log`, so lines interleave. `detach-flags-used.txt` is replaced by the second spawn. Urgency `NEXT_HARDENING_BATCH`.

6. **`PROGRAM_STATUS` `CURRENT_MAIN` is stale, and the runbook still contains a `bf405f46` platform-surface section.** Type `DOCS_OPS`. Confidence `PROVEN` for the SHA cell. The Sep 24 section of the runbook points at `c155272`. Older sections still describe the closed Sep 23 runtime as if it were the current surface. Urgency `NEAR_TERM`. Do not retarget the freeze while editing prose.

7. **Historical worktrees can point agents at the superseded runtime.** Type `DOCS_OPS`. Confidence `PROVEN`. `sep24-runtime-rehearsal` is detached at `02d69976`. Urgency `NEAR_TERM`. Do not delete from this lane.

### LOW

8. **Spawn log handle is kept on the `Popen` object and not closed.** Type `OBSERVABILITY`. Confidence `CODE_INSPECTION_ONLY`. The short-lived `spawn-detached` CLI exits, so the OS reclaims the handle. A long-lived caller would retain one descriptor per spawn. `ResourceWarning` is consistent with that. Urgency `BACKLOG`.

9. **npm audit: 7 findings (1 critical, 1 high, 5 moderate), lockfile only.** Type `SECURITY`. Confidence `PROVEN` for the lockfile report. Not upgraded.

| Package | Severity | Direct | Context |
|---|---|---|---|
| `vitest` `<=4.1.10` | critical | yes | Dev/test UI server. Arbitrary file read when the Vitest UI server is listening. Not the campaign runtime. |
| `vite` `<=6.4.2` | high | yes | Dev server path traversal / Windows `server.fs.deny` bypass. Not served as the production API. |
| `react-router` / `react-router-dom` `<=7.17.0` | moderate | `react-router-dom` direct | Open redirect and SSR hydration constructor injection. Relevant if those routes are reachable in the operator UI. |
| `esbuild` `<=0.24.2`, `@vitest/mocker`, `vite-node` | moderate | transitive | Dev-server request/file issues via Vite. |

`npm audit fix --force` would move Vite to 8 and Vitest to 5. That is a breaking upgrade. Urgency `BACKLOG` / `NEAR_TERM` for a dedicated dependency PR. Not this lane.

10. **Local `test affected` stop is an external `KeyboardInterrupt`, not an IMP cap.** Type `TEST_GAP`. Confidence `REPRODUCED` for the interrupt path; `CODE_INSPECTION_ONLY` for the historical "232 tests" count. `validate.py` has no test ceiling. This lane did not finish the affected suite. Urgency `BACKLOG` unless a completed local run fails.

## Inherited backlog verification

| Inherited item | Result |
|---|---|
| Process survival `job_or_terminal_kill_survival_proven: false` | **Confirmed.** Parent-exit survival re-proven. Job/terminal kill remains unproven on purpose. |
| Finviz credential warn vs fail | **Confirmed and reclassified.** Behavior matches the freeze runbook. It is an operator stop-after-first-poll rule, not an undocumented bug. Still high operational risk if the launch shell has no token. |
| Open outages never close | **Confirmed and expanded.** No writer sets `interval_end_utc` on recovery or shutdown. |
| Shutdown latency up to one poll cadence | **Confirmed.** Default 30s. Ownership flips immediately. |
| Shim PID vs durable PID | **Confirmed.** Documented in the freeze runbook. Safe if the operator uses `ownership.supervisor_pid`. |
| Detached log overwrite | **Reclassified.** The log is append (`ab`), not truncate. Harm is interleaving plus overwrite of `detach-flags-used.txt`. |
| Affected suite stops near 232/0 | **Reclassified.** No product cap. Interrupt mechanism is `KeyboardInterrupt`. Not marked `KNOWN_BROKEN`. |
| ResourceWarning on spawn logs | **Confirmed as low.** Unclosed parent handle. |
| npm audit 7 / 1 critical | **Confirmed and named.** Critical is Vitest UI, dev-only. |
| Stale `CURRENT_MAIN` | **Confirmed.** Cell is `2c40c51c`; `origin/main` is `8562c76a`. |

## Validation results

| Command | Scope | Result | Evidence class |
|---|---|---|---|
| `python tools/imp.py env` | Audit worktree | `healthy`. Resolved 3.11.15. | software |
| `python tools/imp.py format` | Format | exit 0 | software |
| `python tools/imp.py lint` | Lint | exit 0 | software |
| `python tools/imp.py test focused` three security selectors | Offline denial, credential redaction, unknown identifier | 3 passed, 0 failed | software |
| `python -m unittest tests.acceptance.test_campaign_supervision_heartbeat_acceptance` | Heartbeat/survival/shutdown | 23 passed, then the combined process was interrupted | software |
| Combined unittest with durability module | Interrupted inside `test_missing_ui_deps_fail_visible_before_arm` at preflight `git rev-parse` | `KeyboardInterrupt`. Not a failed assertion. | software / harness |
| Three durability tests named below | Outage append, poll classification, register-child | 3 passed in 2.3s | software |
| Controlled Replay golden path, preview, submit-ack | 9 tests | 9 passed in 13.0s | `SOFTWARE_CONTROLLED / FIXTURE_REPLAY` |
| `npm audit --package-lock-only` in `ui/` | Lockfile | exit 1, 7 findings | dependency report |
| `python tools/imp.py test affected` | Not finished | Not run to completion. See finding 10. | not claimed |

Disposable spawn of two children to confirm log interleaving was not executed. Auto-review blocked the spawn helper. The append-mode conclusion is from `detached_process.py`.

## Controlled Replay

Exercised, all passing, class `SOFTWARE_CONTROLLED / FIXTURE_REPLAY`:

- context gate refuses Live observational
- replay env does not enable Live
- reset refuses a non-namespaced directory and clears the replay namespace
- source to Watch/Dismiss, DecisionTrace, TradeReview, stale warning
- Paper preview handoff under server authority
- unwatched/ineligible refusal
- submit yields a durable order and order-history readback

Not exercised here: second-submit idempotency under concurrency, malformed provider payloads, partial API outage, UI rendering.

## Persistence, idempotency, time

- Campaign ownership and heartbeat are JSON files. Outages and poll attempts are append-only JSONL. A repeated status check with the same dead-role signature does not append a second outage row (tested).
- Recovery preserves arm timestamp and segment (tested). It does not close the outage row (code).
- Paper acknowledgement survived readback inside the replay acceptance test. Cross-process restart of Paper was not separately sampled beyond that test's own durability assertion.
- Poll cadence, heartbeat cadence, and stale-after are timezone-aware UTC timestamps (`datetime.fromtimestamp(..., tz=timezone.utc)`). Session bounds `09:30`–`16:00` America/New_York live in the freeze record. This lane did not change the session date.
- `cmd_shutdown` is idempotent at the ownership layer: a missing ownership prints `ALREADY_STOPPED`. It does not kill PIDs.

## Security and dependencies

- Live submit remains blocked in the freeze artifact and in the replay env test.
- Mandatory offline-network and credential-redaction selectors passed.
- No credentials were printed.
- npm findings are dev-server and router issues. The critical Vitest issue requires the Vitest UI server to be listening. It is not the frozen campaign runtime.

## Dead / duplicate / stale

- Superseded runtime `02d699768dce2ad2e85d7215f2588fd18a36fcce` is an ancestor of the frozen runtime and must not be used tomorrow. A worktree still checks it out.
- `NEXT_RTH_CAMPAIGN_RUNBOOK.md` contains both the current Sep 24 procedure and older `bf405f46` sections. The freeze doc is the launch authority.
- `spawn-detached` plus `local_launcher.py` are both required by the freeze procedure. They are complementary (supervisor/poller vs API), not two campaign arms.
- Dozens of linked worktrees are historical. They were not removed.

## Documentation drift

| Document | Class |
|---|---|
| `artifacts/campaign-freeze/RTH-OBS-NEWS-20260924.freeze.json` | `DOC_CORRECT` for freeze SHA, tree, `FROZEN_NOT_ARMED`, empirical locks |
| `docs/engineering/RTH_OBS_NEWS_20260924_FREEZE.md` | `DOC_CORRECT` for launch order and shim-pid warning |
| `docs/platform/PROGRAM_STATUS.md` `CURRENT_MAIN` | `DOC_STALE` (`2c40c51c` vs `8562c76a`) |
| `docs/engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md` | `DOC_AMBIGUOUS` — Sep 24 section is current; later `bf405f46` sections are the closed campaign |

## Prioritized implementation batches

### Batch A — observation ledger and shutdown visibility

Findings 3, 4, 5, 8. Close or supersede open outage rows when the signature clears, without rewriting history. Wake the poller on shutdown instead of waiting out the cadence. Give supervisor and poller separate logs. Close the spawn handle.

Blast radius: campaign supervision only. Can land on `main` while `RTH-OBS-NEWS-20260924` stays pinned to `c155272`. It does not change tomorrow unless a later freeze is explicitly authorized.

Validation: heartbeat acceptance, durability acceptance, a disposable shutdown-latency test. No campaign id `RTH-OBS-NEWS-20260924`.

### Batch B — status prose and worktree hazard

Findings 6 and 7. Point `CURRENT_MAIN` at `8562c76a` without moving the freeze cell. Mark superseded worktrees in the runbook, not by deleting them.

### Batch C — UI dependency advisories

Finding 9. Separate PR. Do not `--force` upgrade during a campaign week unless the Vitest UI server is actually exposed.

### Batch D — test-runner completion evidence

Finding 10. One uninterrupted local `test affected` (or CI log) so the 232-test story is closed with an exit code. Do not change test semantics.

## Empirical locks (unchanged)

`ITEM7_GOVERNED_CORPUS=NOT_ESTABLISHED`

`SEP23_ITEM7_EMPIRICAL_ROWS=0`

`ITEM9_CALIBRATED=NO`

`ITEM9_CALIBRATION_RUN=FORBIDDEN`

`ITEM9_STATUS=PARTIAL_NOT_CALIBRATED`

`FULL30=NOT_RUN`

`FTEP_EMPIRICAL_ACTIVE=NO`

`LIVE_EXECUTION=OFF`

Historical Smoke10 `ibp-smoke10-8C23029DD46FDA78` remains `FAIL 10/10`.

## Next implementation lane

**Batch A — observation ledger and shutdown visibility** on `main`, without retargeting `c15527221a21d7bc88acefbe0971b6de9292247e`.
