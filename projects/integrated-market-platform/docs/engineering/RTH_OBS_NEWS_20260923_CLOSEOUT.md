# RTH-OBS-NEWS-20260923 closeout

**Status:** Closed forensic record. Derivative of frozen receipts. Does not rewrite them.

**Evidence class of this document:** closeout analysis. The campaign receipts remain `LIVE_OBSERVATIONAL` where they say so, and `HISTORICAL_RECONSTRUCTED` where the persisted event says so.

**Machine receipt:** [RTH-OBS-NEWS-20260923.closeout.json](../../artifacts/campaign-closeout/RTH-OBS-NEWS-20260923.closeout.json)

**Frozen runtime:** `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64`. Later software, including [#403](https://github.com/AdamEddahmouni/market-trading-platform/pull/403) and [#402](https://github.com/AdamEddahmouni/market-trading-platform/pull/402), is not this runtime.

## Executive verdict

`RTH-OBS-NEWS-20260923` ran after a late arm at `2026-09-23 13:03:32.789458 -04:00` on frozen runtime `bf405f46` and closed `RTH_CLOSE_SHUTDOWN` at `2026-09-23 17:40:52 -04:00`. The cash session from `09:30:00` through that arm is `NOT_OBSERVED` and was not backfilled. After the arm, Finviz ingress receipts exist, including one NVDA article admitted to the serving book, then a long stretch of successful empty polls, an internal poll gap, and a terminal run of provider `URLError` failures. Supervision was `PROCESS_DEAD` at every armed status snapshot. No operator Watch/Dismiss, no Paper order, no ForecastV1, no governed Item 7 row, and no Item 9 bar were produced. Terminal class remains `PARTIAL_LATE_ARM`.

## Identity

| Field | Value |
|---|---|
| Campaign ID | `RTH-OBS-NEWS-20260923` |
| Campaign slug | `FTEP-V1-002` |
| Segment | `A` |
| Frozen runtime SHA | `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64` |
| Runtime tree SHA | `c3b5a08b94e93e4ead3c9802092ecdebea1c3434` |
| Frozen checkout | `.worktrees/audit-bf405f4-freeze` |
| Session date | `2026-09-23` America/New_York |
| Intended scope | US equity RTH news observation, `09:30:00`–`16:00:00` ET |
| Arm | `2026-09-23 13:03:32.789458 -04:00` (`2026-09-23T17:03:32.789458Z`, ns `1790183012789457920`) |
| Arm authority | `arm_capture.txt` and `RTH-OBS-NEWS-20260923.manifest.json` |
| Terminal class | `PARTIAL_LATE_ARM` |
| Segment status | `CLOSED` |
| Execution | `execution_authority=BLOCKED`, `live=OFF`, `allows_network_submit=false`, safety token `BUILD28_LIVE_SUBMIT_FORBIDDEN` |
| Evidence directory | `projects/integrated-market-platform/.local/rth-campaign-20260923` (572 files) |
| Directory integrity | SHA-256 `ec9723f66da5db6e340c2955052e1cd17f75f982a5b0e522fea257c54ae036e0` over sorted `sha256  relative/path` lines. Algorithm is in the machine receipt. |

Shared mutable state outside that directory was read and not treated as the frozen set: `.local/imp-state.sqlite3` and `.local/campaign-supervision/`. The campaign subdirectory `state/imp-state.sqlite3` is a pre-arm copy (filesystem time `12:50` ET) with zero intelligence rows.

## Coverage

US cash RTH `09:30:00`–`16:00:00` ET is `6h 30m` (`23400s`).

| Interval (ET) | Class | Duration | What the receipts show |
|---|---|---|---|
| `09:30:00.000` → `13:03:32.789` | `NOT_OBSERVED` | `3h 33m 32.789s` (`12812.789s`) | Before arm. Manifest token `NOT_OBSERVED`. No backfill. |
| `13:03:32.789` → `13:03:38` | `OBSERVED_FAILURE` | ~5s | Arm. Supervisor status `PROCESS_DEAD` / `REQUIRED_PROCESS_DEAD`. `logs/supervisor.err.log` aborts in `os.kill(pid, 0)` with `OSError: [WinError 87]` as the cause of `KeyboardInterrupt`. |
| `13:03:46` filesystem write | `OBSERVED` empty provider poll | one receipt | `live-ingress-001.json`: `FINVIZ_LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS`, `PASS`, `row_count=0`. Clock inside the file is absent; time is the filesystem write. |
| `13:05:37` and `13:06:33` retrievals | `OBSERVED_FAILURE` at admit | two receipts | Same NVDA article fetched (`row_count=1`, classification `SUCCESS`). Cockpit admit `UI_API_COCKPIT_ADMIT_UNREACHABLE`, WinError `10061` connection refused on `127.0.0.1:8766`. Disposition `BLOCKED`. |
| `13:13:50` → `13:13:58` | `OBSERVED_DEGRADED` | one admitted retrieval | `live-ingress-004.json` `COCKPIT_ADMIT_HTTP_OK`. Event and observational opportunity persisted. Status snapshot `13:13:59Z` is still `PROCESS_DEAD`; the registered poller child probed alive and the api/supervisor children probed dead. |
| `13:13:59` → `14:42:50` | `NOT_OBSERVED` | `1h 28m 51s` | No ingress receipt after the one-shot followup. Absence is not healthy observation. |
| `14:42:50` → `14:47:59` | `OBSERVED_DEGRADED` | `5m 9s` | Summary polls 5–12: `SUCCESS_EMPTY`, `PASS`. Campaign heartbeat `last_successful_poll_utc` stays `2026-09-23T17:13:45.962684Z`. |
| `14:47:59` → `14:53:18` | `NOT_OBSERVED` | `5m 19s` | No poll line in the jsonl. `supervisor-durable-failure-receipt.json` at `14:49:23` ET. Summary sidecar for poll index 13 is later, `14:59:21`. |
| `14:53:18` → `15:42:00` | `OBSERVED_DEGRADED` | polls resumed | Empty qualifying Finviz polls continue (summary indices through 86 end `15:42:00`). Supervision heartbeat still stuck at `13:13:45` ET on the pre-close snapshot. |
| `15:42:35` → `15:59:43` | `OBSERVED_FAILURE` | `17m 8s` | Summary indices 87–127: `LIVE_INGRESS_FAILED`, `PROVIDER_FAILURE`, blocker `FINVIZ_PROSPECTIVE_FETCH_FAILED`, captured fetch error `network_error: URLError`. No HTTP status in the receipt. |
| `15:59:43` → `16:00:17` | `UNKNOWN` then stop | `34s` | No further poll body. Jsonl records `POLLER_STOP_RTH_CLOSE` twice at `16:00:17` ET ("Reached 16:00 ET"). |
| `16:00:00` → `17:40:37` | after the cash close | `1h 40m` | Not an RTH observation interval. Governed close had not started. |
| `17:40:37` → `17:40:52` | `LATE_GOVERNED_CLOSE` | `15s` | `close-timing-20260923.json`. `RTH_CLOSE_SHUTDOWN`. On-time 16:00 close missed. |

Post-arm clock span until 16:00 is `2h 56m 27.211s` (`10587.211s`). That span is not continuous healthy observation.

Distinct full ingress receipts: **127** (`live-ingress-001.json` through `live-ingress-127.json`).

Jsonl `live-ingress-poller-20260923.jsonl`: **219** `LIVE_INGRESS_POLL` lines and **2** `POLLER_STOP_RTH_CLOSE` lines, **119** distinct `poll_index` values, maximum multiplicity **2**. `219` is a line count with overlapping writers, not 219 independent attempts. `ingress-session-summary.json` records `prior_receipts_001_004_not_in_jsonl=true`.

## Timeline

Times are America/New_York unless marked UTC.

| Time | Event | Source |
|---|---|---|
| `09:30:00` | Cash RTH open. Campaign not armed. | Manifest `not_observed` |
| `09:02:00` publication (`13:02:00Z`) | NVDA headline already published. This instant was not observed by the campaign. | Event `event_time_ns` `1790168520000000000` |
| `12:50` filesystem | Campaign-local sqlite copy, zero intelligence rows. | `state/imp-state.sqlite3` |
| `12:58` filesystem | UI vite logs created. | `logs/ui-vite.*.log` (empty) |
| `13:01:59` filesystem | UI API stdout/stderr logs stop growing. | `logs/ui-api.out.log`, `logs/ui-api.err.log` |
| `13:03:32.789` | **Arm.** | `arm_capture.txt` |
| `13:03:35` | Supervisor process aborts in `process_alive` → `os.kill`. | `logs/supervisor.err.log` |
| `13:03:38Z` | Status `PROCESS_DEAD`. Ownership `supervisor_pid=119016` matches heartbeat pid. Children api `99128` and supervisor-role `132724` probe dead. Required roles include poller, which is absent. | `supervisor-status-after-arm.json` |
| `13:03:46` filesystem | Ingress 001, zero qualifying rows, `PASS`. | `live-ingress-001.json` |
| `13:05:37` | Ingress 002 retrieves the NVDA article. Admit refused (`10061`). | `live-ingress-002.json` |
| `13:06:33` | Ingress 003, same article, admit refused again. | `live-ingress-003.json` |
| `13:13:45Z` | Heartbeat `last_successful_poll_utc`. This value never advances on later snapshots. | followup and pre-close status |
| `13:13:46`–`13:13:47` | Followup registration. Ownership `supervisor_pid=136220` equals the poller child's `parent_pid`. Heartbeat pid is `5888`. Child role `supervisor` is `111828`. Poller `112116` probes alive; api and supervisor-role probe dead. Status `PROCESS_DEAD`. | `supervisor-status-followup.json` |
| `13:13:50` | NVDA article retrieved again. | ingress 004 metadata `retrieved_time` |
| `13:13:57.889` | Event received and SURFACE trace decision time. | sqlite `received_time_ns` / `decision_time_ns` |
| `13:13:58.104` | Opportunity `newsopp-91EABF7A3AF6C83ACFE3BAFA626846AE` persisted. | `intelligence_opportunities` |
| `13:13:58.181` | Event `91EABF7A3AF6C83ACFE3BAFA626846AE` persisted. | `intelligence_events` |
| `13:13:59` → `14:42:50` | No ingress receipt. | gap between 004 and summary 005 |
| `14:42:50` → `14:47:59` | Polls 5–12, `SUCCESS_EMPTY`. | `live-ingress-005` … `012` summaries |
| `14:48:08`–`14:48:11Z` | Recovery status. Ownership `supervisor_pid=22752`. Heartbeat pid `134508`. All three children probe dead. `last_successful_poll` still `17:13:45Z`. | `supervisor-status-recovery-1447ET.json` |
| `14:49:23` | Durable failure receipt: `SUPERVISOR_DURABLE_RUN_FAILURE`, `PRESERVED_FAILURE_NOT_DURABLE_SUPERVISOR`. | `supervisor-durable-failure-receipt.json` |
| `14:53:18` | Next jsonl poll line (index 13). | poller jsonl |
| `14:59:21` | Summary sidecar poll 13, still `SUCCESS_EMPTY`. Poller pid file rewritten. | `live-ingress-013-summary.json`, `live-ingress-poller.pid` |
| `15:01:43` | Separate Moomoo snapshot probe `US.AAPL`, `probe_status=OK`, `lane_outcome=DERIVED_BBO_DESIGN_REQUIRED`, `temporal_order_valid=false`. Append script traceback; no Item 7 row. | `item7-bbo-probe-20260923.json`, `item7-bbo-capture-20260923.json` |
| `15:42:35` → `15:59:43` | Polls 87–127 provider `URLError`. | summaries |
| `15:59:44` | Historical Moomoo capture-catalog rows reindexed. Capture windows are earlier than this session. | parent sqlite `capture_catalog.indexed_at` |
| `16:00:17` | Poller stop, reason `Reached 16:00 ET`, recorded twice. | jsonl |
| `17:40:49Z` | Pre-close status still `ARMED_RUNNING` + `PROCESS_DEAD`. Ownership `supervisor_pid=102152`. Heartbeat pid still `134508`. Children probe dead. | `supervisor-status-pre-close.json` |
| `17:40:37` → `17:40:52` | Late governed close. Final arm status `RTH_CLOSE_SHUTDOWN`. Progress `NOT_APPLICABLE`. | `close-timing-20260923.json`, `close-supervisor-status-after.json` |

Why the arm was after `09:30` is `UNKNOWN`. The manifest records the lateness. Logs show a UI API process before the arm. They do not record a blocker that prevented a `09:30` arm.

## Runtime and process evidence

Required roles on the ownership record: `supervisor`, `poller`, `api`. UI was not a required role.

`ui-start-skip.txt` states UI `:5173` was not started because the frozen checkout has no `ui/node_modules`, and `npm ci` was not run.

`logs/ui-api.err.log` records `SecretLeakError` while building a provider-health payload (secret-shaped keys, no secret values copied here) and `ConnectionAbortedError` WinError `10053`. That is an API response failure. It is not, by itself, proof the API process exited.

Admit failures at `13:05` and `13:06` are connection refused. Admit at `13:13:50` reached `127.0.0.1:8766`. The API was down for those two attempts and reachable for the third.

Frozen `campaign_supervisor.py` `cmd_register_child` assigns `ownership.supervisor_pid = os.getpid()` for every registration. The `13:13` followup snapshot shows `supervisor_pid` equal to the poller's parent and different from both the heartbeat pid and the child registered with role `supervisor`. That overwrite is demonstrated.

`os.kill(pid, 0)` aborting the first supervisor is demonstrated by `logs/supervisor.err.log` (and the same pattern in `supervisor-recovery2.err.log`). `process_alive` catches `OSError` and returns false; it does not catch `KeyboardInterrupt`, so the probe aborted the process.

The `14:49` receipt says the probe classified `PROCESS_DEAD` while `Get-Process` showed the process alive. No `Get-Process` listing is stored in that receipt. That specific "still alive" claim is `LIKELY_BUT_NOT_PROVEN`.

`campaign-supervision/outages.jsonl` was absent at analysis time. Failures live in ingress receipts and status snapshots, not in the outage ledger.

Final ownership left on disk (`arm_status=RTH_CLOSE_SHUTDOWN`, `supervisor_pid=102152`) still lists child pids from the `14:48`/`14:59` registration. `api.pid` in the campaign directory is a different pid (`139420`, filesystem time `14:54`). Ownership and pid files disagree.

## Provider evidence

Provider on the admitted event: `finviz` (`source.provider_id`, adapter `finviz.news`). Watch mode on the receipts: `PROSPECTIVE_FINVIZ_INGRESS`. Attention kind: `LIVE_PROSPECTIVE`.

| Outcome | Distinct receipts | Notes |
|---|---|---|
| `FINVIZ_LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS` / `SUCCESS_EMPTY` / `PASS` | 83 | 001 plus summary indices 5–86 |
| Fetch `SUCCESS` with `row_count=1`, admit blocked | 2 | 002, 003, NVDA |
| `COCKPIT_ADMIT_HTTP_OK` / `PASS` | 1 | 004, NVDA, `admitted_count=1` |
| `LIVE_INGRESS_FAILED` / `PROVIDER_FAILURE` / `BLOCKED` | 41 | indices 87–127, `network_error: URLError` |

Qualifying instrument: `NVDA` only. Headline captured on the receipt: "Nvidia Scores Winning Streak: Trump-Xi Meeting, China Sales Outlook In Focus". Publication `2026-09-23T13:02:00Z` (`09:02` ET). Retrieval on the admitted attempt `2026-09-23T17:13:50Z` (`13:13:50` ET).

No HTTP status code is stored on the `URLError` failures. Upstream cause (DNS, reset, vendor, credential transport) is `UNKNOWN`.

A separate Moomoo OpenD snapshot for `US.AAPL` at `15:01:43` ET returned prices in `item7-bbo-probe-20260923.json` (`bid_price=337.23`, `ask_price=337.24`, `last_price=337.24`) with `lane_outcome=DERIVED_BBO_DESIGN_REQUIRED` and `TEMPORAL_ORDER_VIOLATION`. The append tool crashed (`AttributeError` in the frozen capture script). That probe is not a governed Item 7 row and is not a Finviz news observation.

## Pipeline evidence

Serving book used for the admitted row: parent `.local/imp-state.sqlite3`. Two other opportunities in that database persisted `2026-09-22` and are excluded.

| Stage | Count | Earliest | Latest | Classification |
|---|---|---|---|---|
| Provider attempt (distinct ingress JSON) | 127 | 001 filesystem `13:03:46`; first in-file retrieval `13:05:37` | `15:59:43` | Real attempts after arm |
| Lawful provider observation with a qualifying row | 3 fetches, 1 article | `13:05:37` | `13:13:50` | Same NVDA article |
| EventV1 persisted | 1 | `13:13:58.181` | same | `NEWS_ARTICLE`, id `91EABF7A3AF6C83ACFE3BAFA626846AE` |
| Ingestion stamp on that event | 1 | | | Captured `ingestion_mode=HISTORICAL_RECONSTRUCTED` |
| DetectionV1 / BUILD 09 `NEWS_EVENT` | 0 | | | `news_event_build09=INACTIVE` on the opportunity metadata |
| ForecastV1 / champion | 0 | | | No forecast artifact under the persistence root |
| Observational opportunity persisted | 1 | `13:13:58.104` | same | `NEWS_OBSERVATIONAL`, `newsopp-91EABF7A3AF6C83ACFE3BAFA626846AE` |
| Opportunity Engine `assess` / strategy admission | 0 | | | Trace eligibility `STRATEGY_FAMILY_ABSENT`. Frozen news hop does not call ForecastV1-gated `assess`. |
| SURFACE decision trace | 1 | `13:13:57.889` | same | `decision_kind=SURFACE`, `operator_action=null`, `review_id=null`, mode `PAPER` |
| Ranked feed during later polls | count 2, ids not listed | `14:42:50` | `15:59:43` | `READY` on 122 summaries; one summary recorded a remote-connection error. Which two ids were shown is `UNKNOWN`. |
| Operator Watch/Dismiss | 0 | | | Close record `watch_dismiss=NOT_PERFORMED`. No ack row for this opportunity. |
| TradeReview for this opportunity | 0 | | | The one `trade_reviews` row is an earlier timestamp |
| Paper order / preview | 0 | | | No `paper_events` payload mentions `91EABF7A`. Trace `preview=null`. |
| Item 7 governed row | 0 | | | See below |
| Item 9 prospective bar | 0 | | | No receipt file with mtime on `2026-09-23` under the frozen collector store |

Zero DetectionV1 and zero ForecastV1 follow from an inactive detector and a missing forecast, not from a crashed detector process. Zero strategy admission follows from `STRATEGY_FAMILY_ABSENT` plus the ForecastV1 gate. Zero operator decisions follow from no Watch/Dismiss.

The event stamp `HISTORICAL_RECONSTRUCTED` is a captured field. On current `main`, the same stamp is applied when live gates are off, and also when publication is before the observation window even if live gates are on (`test_news_ingest_mode_stamp.py`). Those are current interpretations. The receipt itself also says `LIVE_PROSPECTIVE`. Publication `09:02` ET is before the `13:03:32` arm, so this row does not observe the pre-arm interval and is not relabeled `LIVE_OBSERVED`.

Quality flags on the event and opportunity: `PROVIDER_LINKAGE_SOURCE_URL_MISSING`, quality state `GOOD`. `live_authority=false`.

## Operator evidence

No Watch, Dismiss, or other operator action is stored for `newsopp-91EABF7A3AF6C83ACFE3BAFA626846AE`. UI `:5173` did not start. Later poll summaries report a ranked feed count of 2 without ids. Whether an operator could see the new row is `UNKNOWN`.

## Item 7

`SEP23_ITEM7_EMPIRICAL_ROWS=0`

`ITEM7_GOVERNED_CORPUS=NOT_ESTABLISHED`

Evidence:

- Campaign status file `item7-status-20260923-1455ET.json`: `governed_candidate_rows=0`, `forecast_total=0`, `snapshot_total=0`, blockers `NO_GOVERNED_PATH_A_TRAINING_CORPUS` and `RTH_OR_FUTURE_OUTCOMES_REQUIRED`.
- Read-only `tools/item7_corpus_collector.py status` on current `main` discovery, persistence root `.local`, `--training-cutoff-ns 1790200000000000000`, `--now-ns 1790195000000000000`, no `--output`: same zeros. `paths_scanned=0`. This command prints JSON only.
- The `15:01` AAPL snapshot was not appended. The capture file is the script traceback.
- Missing chain: no PIT snapshot corpus, no PRODUCTION forecast, no settled outcome, no joinable governed row. The NVDA news opportunity is not an Item 7 training row.

## Item 9

`ITEM9_STATUS=PARTIAL_NOT_CALIBRATED`

`ITEM9_CALIBRATED=NO`

`ITEM9_CALIBRATION_RUN=FORBIDDEN`

`DO_NOT_PROMOTE`

`FULL30=NOT_RUN`

`item9-opend-readiness-1455ET.json` captured `calibrated=false`, `empirical_active=false`, `item9_status=PARTIAL_NOT_CALIBRATED`.

`item9-corpus-status-20260923-1455ET.json` is a failed process invocation (`item9_corpus_status.py` path missing on the checkout that ran it), not a corpus measurement.

`item9-preflight-20260923-1455ET.json` is a usage error from a checkout whose `imp.py` had no `item9` group. It is not a preflight result.

No file under `.imp-actual-01-phase-d/.../item9-prospective-proof-receipts` has a last-write time on `2026-09-23`. This campaign did not add a distinct RTH date, a bar, or a calibration sample. Software readiness and empirical satisfaction stay separate. Sample-gate state from the `2026-09-21` collector receipts is unchanged by this campaign and was not re-measured here.

## Latency and lineage

Linked timestamps for the one NVDA article:

| Interval | Value |
|---|---|
| Publication `09:02:00` → retrieval `13:13:50` | `4h 11m 50s` |
| Arm `13:03:32.789` → retrieval `13:13:50` | `10m 17.211s` |
| Retrieval `13:13:50` → event `received_time` `13:13:57.889` | `7.889s` |
| Event receive → opportunity `created_at_ns` | `0s` (same nanosecond `1790183637889268100`) |
| Opportunity create → opportunity persist | `0.215s` |
| Opportunity persist → event persist | `0.077s` |

No detector timestamp, no ForecastV1 timestamp, no Opportunity Engine assess timestamp, no Radar-id timestamp, no operator-action timestamp, no Paper timestamp. Those intervals are not calculated.

Complete source→operator chain: **no**.

Controlled Replay latency is not this campaign's latency.

Moomoo probe clocks are a different lane (`TEMPORAL_ORDER_VIOLATION`) and are not a news lineage.

## Root-cause findings

| Finding | Class | Evidence |
|---|---|---|
| Supervisor run aborted because `os.kill(pid, 0)` raised `KeyboardInterrupt` caused by WinError 87 | `PROVEN_ROOT_CAUSE` of the first supervisor exit | `logs/supervisor.err.log`, frozen `process_alive` |
| `register-child` wrote the registering process pid into `ownership.supervisor_pid` | `PROVEN_CONTRIBUTOR` to later `PROCESS_DEAD` / pid mismatch | Frozen `cmd_register_child`; followup snapshot pids |
| Required poller missing at the instant after arm | `PROVEN_CONTRIBUTOR` | after-arm children are api and supervisor-role only; required roles include poller |
| API not listening at `13:05`–`13:06` | `PROVEN_ROOT_CAUSE` of those two admit failures | WinError `10061` on the admit receipt |
| UI never started | `PROVEN` operator-display gap | `ui-start-skip.txt` |
| Heartbeat `last_successful_poll` frozen at `13:13:45` ET while later polls ran | `PROVEN` | pre-close snapshot versus summaries through `15:59` |
| Provider `URLError` `15:42:35`–`15:59:43` | `SYMPTOM_ONLY` | blocker and `fetch_error` captured; upstream cause `UNKNOWN` |
| "Get-Process showed alive while status said dead" | `LIKELY_BUT_NOT_PROVEN` | prose in the `14:49` receipt; no process listing |
| Why arm waited until `13:03:32` | `UNKNOWN` | lateness is recorded; mechanism is not |
| Duplicate jsonl poll lines | `PROVEN` recording overlap | 219 lines, multiplicity 2 |

## Post-campaign software fixes

These are later `SOFTWARE` changes. They do not change the frozen campaign.

| Change | What it changes for a future arm | What it does not prove |
|---|---|---|
| [#403](https://github.com/AdamEddahmouni/market-trading-platform/pull/403) `8232b155` | `register-child` keeps the durable supervisor pid unless `--adopt-as-supervisor`. Supervisor liveness uses the launcher probe instead of `os.kill`. Missing required roles stay `PROCESS_DEAD`. `poll-loop` is the long-lived poller. `environment-preflight` fails closed when the API entrypoint or `ui/node_modules` is missing. | A future RTH session. Sep 23 pids, heartbeats, and receipts. |
| [#402](https://github.com/AdamEddahmouni/market-trading-platform/pull/402) `4fcec08b` | Durable Paper order acknowledgement after Workspace submit. | Anything about this observational campaign. No Paper order occurred. |
| [#398](https://github.com/AdamEddahmouni/market-trading-platform/pull/398) | `NEWS_ARTICLE` can become `NEWS_EVENT` on current `main`. | The frozen runtime, where `news_event_build09` stayed `INACTIVE`. |
| [#394](https://github.com/AdamEddahmouni/market-trading-platform/pull/394) | Discovery of governed Item 7 rows if they exist. | It found zero. It did not create rows. |

## What this campaign proves

- The campaign was armed and later shut down. It is not an unrun day.
- Pre-arm RTH is `NOT_OBSERVED`, and the NVDA article's `09:02` publication does not fill that gap.
- Finviz was queried after the arm: 83 empty successes, 3 fetches of one NVDA article, 41 `URLError` failures.
- One observational opportunity and one `NEWS_ARTICLE` event were persisted, with a `SURFACE` trace and no operator action.
- The frozen supervisor exited on the `os.kill` probe, and `register-child` overwrote `supervisor_pid` with the registrar pid.
- Live execution stayed off. No Paper order was tied to the new opportunity.

## What this campaign does not prove

- Full-session or continuous post-arm coverage.
- A healthy supervisor, poller, and API together for any interval.
- A prospective-current `LIVE_OBSERVED` stamp on the NVDA event.
- DetectionV1, ForecastV1, Opportunity Engine strategy admission, operator decision, or Paper.
- Item 7 corpus, Item 9 calibration, Full30, FTEP empirical activation, or a new Smoke10 result.
- That [#403](https://github.com/AdamEddahmouni/market-trading-platform/pull/403) would have kept this session healthy.
- The upstream cause of the `15:42` `URLError` run.
- Why the arm was late.

## Next RTH requirements

The next campaign is a new id and a new frozen runtime that contains [#403](https://github.com/AdamEddahmouni/market-trading-platform/pull/403). Do not resume `bf405f46` under `RTH-OBS-NEWS-20260923`.

Before arm:

1. Preflight fails closed if `ui/node_modules` or the API entrypoint is missing, then the operator still has to show API `:8766` accepting admit and, if an operator display is required, UI `:5173` actually serving.
2. Arm before `09:30` ET. A late arm is a new partial campaign, not a backfill.
3. Ownership `supervisor_pid` is the long-lived supervisor, not a one-shot shell. Required roles `supervisor`, `poller`, `api` each have a live pid. Heartbeat `last_successful_poll_utc` advances when polls succeed.
4. The poller is `campaign_supervisor.py poll-loop`, not a one-shot ingress script registered as the poller.
5. Status is fail-visible: dead or stale stays `PROCESS_DEAD` or `STALE` and is written to `outages.jsonl`. `ARMED_RUNNING` alone is not healthy.
6. First Finviz receipt is either `SUCCESS_EMPTY` or a qualifying row whose `ingestion_mode` matches the publication-versus-window rule. `URLError` without a status remains a failed poll.
7. Close at `16:00` ET with `shutdown --rth-close`, then a derivative closeout outside the receipt directory.
8. Item 7 rows, Item 9 bars, calibration, Full30, FTEP empirical locks, and Live submit stay forbidden until their own gates are met. This campaign did not meet them.

| Requirement | Class |
|---|---|
| Pre-RTH armed state | `REQUIRES_NEXT_RTH_PROOF` |
| Durable supervisor pid not replaced by a one-shot registrar | `SOFTWARE_PROVEN` on `main` via [#403](https://github.com/AdamEddahmouni/market-trading-platform/pull/403); `REQUIRES_NEXT_RTH_PROOF` empirically |
| Required-role liveness | `SOFTWARE_PROVEN` as a status rule; `REQUIRES_NEXT_RTH_PROOF` on a real session |
| Poll-loop durability | `SOFTWARE_PROVEN` as a command and acceptance test on `main`; `REQUIRES_NEXT_RTH_PROOF` empirically |
| API reachable for admit | `REQUIRES_NEXT_RTH_PROOF` |
| Provider fetch through the session | `REQUIRES_NEXT_RTH_PROOF` |
| UI dependency preflight | `SOFTWARE_PROVEN` (`environment-preflight`); operator display still `REQUIRES_NEXT_RTH_PROOF` |
| Heartbeat advances on real polls | `REQUIRES_NEXT_RTH_PROOF` |
| Ingress health visible in receipts | `SOFTWARE_PROVEN` as receipt fields; session-long health `REQUIRES_NEXT_RTH_PROOF` |
| Fail-visible dead/stale state | `SOFTWARE_PROVEN` as tokens; Sep 23 showed those tokens while the probe also aborted the supervisor |
| On-time terminal close | `REQUIRES_NEXT_RTH_PROOF` |
| Item 7 governed row | `BLOCKED` until forecast, snapshot, and outcome evidence exist |
| Item 9 calibration | `BLOCKED` (`ITEM9_CALIBRATION_RUN=FORBIDDEN`) |
| Live execution | `BLOCKED` |
| Re-arm of `bf405f46` as this campaign | `BLOCKED` |

Historical Smoke10 `ibp-smoke10-8C23029DD46FDA78` remains `FAIL 10/10` and was not rerun. Controlled Replay remains `SOFTWARE_CONTROLLED` / `FIXTURE_REPLAY`.
