# IMP-POST-RTH-CLOSE-08 — Lane G (status / roadmap reconciliation)

| Field | Value |
|---|---|
| Campaign | `IMP-POST-RTH-CLOSE-08` |
| Lane | **G** — status / roadmap reconciliation (docs-only) |
| Branch | `docs/imp-post-rth-close-08-status` |
| Worktree | `.worktrees/lane-g-status` |
| Authority | [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) (mutable gates); Lane 0 closeout JSON (empirical, not in git) |

Lane G records **canonical program prose** after the 2026-09-18 US equity cash RTH close. It does **not** merge implementation branches, mutate receipts, run calibration, or change Live gates.

## Item 9 — Lane 0 final (governed corpus)

Authoritative closeout from frozen collector **ITEM9_FROZEN_COLLECTOR** `fed2d9f7e183aecfcac61a7664df69aafc12ea25` (checkout `.imp-actual-01-phase-d`). **Do not** use the 15:11 snapshot if it disagrees with this record.

| Field | Value |
|---|---|
| `COLLECTOR_SHA` | `fed2d9f7e183aecfcac61a7664df69aafc12ea25` |
| `COLLECTOR_STOP_TIME` | `2026-09-18T16:00:11` ET |
| `ACTIVE_COLLECTORS` | **0** (post-close) |
| `OUTAGE_EPOCH` | `item9-prospective-20260918-epoch-fed2d9f7-aapl-121031` — receipt **NONE**, **not** backfilled |
| `FIRST_RECOVERY` | `item9-prospective-20260918-epoch-fed2d9f7-aapl-135512.json` |
| `FINAL_SEP18_RECEIPTS` | **143** files, **143** admitted |
| `SEP17_ADMITTED` | **45** (includes **1** `PATH_PROOF_ONLY` / `EMPTY_RAW_PROVENANCE_HASH`) |
| `TOTAL_ADMITTED` / `TOTAL_RECEIPTS` | **188** / **189** |
| `FINAL_EVAL_ROWS` | **39** |
| `DISTINCT_RTH_DATES` | **2** / **3** (admitted dates only) |
| `GATE_STATE` | `INSUFFICIENT_CALIBRATION_EVIDENCE` |
| `CALIBRATION_STATE` | `NOT_CALIBRATED` |
| `FTEP_EMPIRICAL_ACTIVE` | **NO** |
| `LIVE_EXECUTION` | **OFF** |
| `PR222_MERGED` | **NO** |

Closeout artifact (operator tree, not tracked in git):

`artifacts/ftep-v1-002/item9-lane0-provider-outage-closeout-20260918.json`

(under `.imp-actual-01-phase-d/projects/integrated-market-platform/…`).

### Admitted-date ledger (Item 9)

| US cash RTH date | Admitted receipts | Notes |
|---|---|---|
| 2026-09-14 | **NOT_ADMITTED** | no files in corpus dir |
| 2026-09-15 | **NOT_ADMITTED** | activity elsewhere; no admissible receipts in corpus dir |
| 2026-09-16 | **NOT_ADMITTED** | no files |
| 2026-09-17 | **ADMITTED** **45** | one `PATH_PROOF_ONLY` |
| 2026-09-18 | **ADMITTED** **143** | provider outage gap preserved (epoch `121031`) |

**RTH activity ≠ admitted Item 9 date.** Calendar days with hops, watches, or other program activity do not count toward `MINIMUM_DISTINCT_RTH_DATES` unless corpus admission rules admit receipts for that date.

### Next lawful Item 9 increment

On a **future** US equity cash RTH session: preflight from **`.imp-actual-01-phase-d` @ `fed2d9f7`** when **`READY_TO_COLLECT`** → governed Mode B `--poll` → read-only `corpus-status` on the **frozen collector receipt dir**. Target: a **third distinct admitted** RTH date (not 2026-09-17/18). **`ITEM9_CALIBRATION_RUN=FORBIDDEN`** — no automatic calibration fitting.

## Follow-on operator stack (merged after Lane 0 close)

| PR | Purpose | Merge SHA |
|---|---|---|
| [#287](https://github.com/AdamEddahmouni/market-trading-platform/pull/287) | Runtime/provider resilience (Lane B) | `b854c32d` |
| [#288](https://github.com/AdamEddahmouni/market-trading-platform/pull/288) | Simulator experiment spec routing (docs) | `8ad2f154` |
| [#289](https://github.com/AdamEddahmouni/market-trading-platform/pull/289) | **`GET /operator/diagnostics`** snapshot API | `50a1477f` |

UI redesign work remains on isolated branch **`ui/operator-redesign-lab`** — not merged to program-main.

## Parallel lanes — engineering landings (merged to `origin/main`)

All five **IMP-POST-RTH-CLOSE-08** engineering lanes landed via [#282](https://github.com/AdamEddahmouni/market-trading-platform/pull/282)–[#285](https://github.com/AdamEddahmouni/market-trading-platform/pull/285); frozen experiment receipts were not rewritten on merge.

| Lane | Branch / SHA | Status | Notes |
|---|---|---|---|
| Facts | `feat/grounded-fact-extraction-v1` @ `90773a41` | **MERGED** [#282](https://github.com/AdamEddahmouni/market-trading-platform/pull/282) | smoke `ibp-factual-smoke-766E16CAF41F3210` — facts **11/11**, unknown **11/11** (historical); `FULL30_EXECUTED=NO` |
| Drawdown | `research/simulator-drawdown-wiring-v1` @ `2b194d74` | **MERGED** [#283](https://github.com/AdamEddahmouni/market-trading-platform/pull/283) | research-class wiring; v3 receipts untouched |
| Fill realism | `research/fill-price-realism-v1` @ `a36ab28b` | **MERGED** [#285](https://github.com/AdamEddahmouni/market-trading-platform/pull/285) | **EXECUTED** pack `6A66AE5C50700426F71B3734E6FC6A43`; hash `C4FCD3AB…1149`; CI portability fix only (foreign v3 manifest paths → skip/unavailable) |
| Cost sensitivity v4 | `benchmark/lane-e-cost-sensitivity-v4` @ `7b5e4be9` | **MERGED** [#284](https://github.com/AdamEddahmouni/market-trading-platform/pull/284) | **EXECUTED** pack `1DEF586A`; re-review **APPROVE** @ `7b5e4be9`; hash `30FB6972…0B53` |

## Lane G invariants (docs closure)

```text
ITEM9_DISTINCT_RTH_DATES=2/3
ITEM9_CALIBRATED=NO
ITEM9_CALIBRATION_RUN=FORBIDDEN
ITEM9_GATE_STATE=INSUFFICIENT_CALIBRATION_EVIDENCE
PR222_MERGED=NO
LIVE_EXECUTION=OFF
FTEP_EMPIRICAL_ACTIVE=NO
ITEM9_FROZEN_COLLECTOR=fed2d9f7e183aecfcac61a7664df69aafc12ea25
FROZEN_COLLECTOR_MUTATED=NO
RECEIPTS_REWRITTEN=NO
OUTAGE_GAP_BACKFILLED=NO
```
