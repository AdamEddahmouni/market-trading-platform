# Agent handoff — IMP-POST-RTH-CLOSE-08

Skill: `imp-handoff`. Session: Lane G status / roadmap reconciliation (docs-only).

## Canonical state

- repository: `AdamEddahmouni/market-trading-platform` (IMP at `projects/integrated-market-platform/`)
- branch: `docs/imp-post-rth-close-08-status`
- worktree: `.worktrees/lane-g-status`
- **CURRENT_GIT_MAIN** / **CURRENT_SOFTWARE_IMPLEMENTATION**: `2306ff4a0db74d6ed35d9c5d1bb82bf8b3dc7c56` (`origin/main` after [#281](https://github.com/AdamEddahmouni/market-trading-platform/pull/281))
- **ITEM9_FROZEN_COLLECTOR**: `fed2d9f7e183aecfcac61a7664df69aafc12ea25` (`.imp-actual-01-phase-d`; collector **stopped** `2026-09-18T16:00:11` ET; **`ACTIVE_COLLECTORS=0`**)
- **SEP15_FROZEN_EMPIRICAL**: `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` — do not rewrite

## Objective

Reconcile authoritative status after 2026-09-18 RTH Item 9 close (Lane 0) without mutating receipts, merging #222, or calibrating Item 9.

## Completed (Lane G)

- [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) v1.46: **CURRENT_MAIN** `2306ff4a`; Item 9 **`2`/`3`** admitted RTH dates; **IMP-POST-RTH-CLOSE-08** row; HELD lanes matrix
- [IMP_POST_RTH_CLOSE_08_LANE_G.md](IMP_POST_RTH_CLOSE_08_LANE_G.md) — Lane 0 closeout + date ledger + parallel **HELD** branches
- [NEXT_RTH_CAMPAIGN_RUNBOOK.md](NEXT_RTH_CAMPAIGN_RUNBOOK.md) gate line
- [IMP_DUAL_CORPUS_01_NOTION_SYNC.md](IMP_DUAL_CORPUS_01_NOTION_SYNC.md) Item 9 summary
- [WORK_LOG.md](WORK_LOG.md) entry

## Honest gates

```text
ITEM9_DISTINCT_RTH_DATES=2/3
ITEM9_CALIBRATED=NO
ITEM9_GATE_STATE=INSUFFICIENT_CALIBRATION_EVIDENCE
PR222_MERGED=NO
LIVE_EXECUTION=OFF
FTEP_EMPIRICAL_ACTIVE=NO
RECEIPTS_REWRITTEN=NO
```

## HELD engineering (not program-main)

| Lane | Branch @ SHA | Disposition |
|---|---|---|
| Facts | `feat/grounded-fact-extraction-v1` @ `90773a41` | smoke `ibp-factual-smoke-766E16CAF41F3210`; **not merged** |
| Drawdown | `research/simulator-drawdown-wiring-v1` @ `2b194d74` | **APPROVE HELD** |
| Fill | `research/fill-price-realism-v1` | pack `6A66AE5C`; **APPROVE HELD** |
| Cost v4 | `benchmark/lane-e-cost-sensitivity-v4` @ `7b5e4be9` | pack `1DEF586A`; re-review **APPROVE** (reviewer `03eaa3d2`); **not merged** |

## Validated

- `python tools/check_docs_links.py` — run on Lane G doc set (see WORK_LOG)
- Item 9 `corpus-status` — **not** re-run in Lane G (Lane 0 authority recorded in closeout JSON)

## Evidence-sensitive state

- Lane 0 closeout: `artifacts/ftep-v1-002/item9-lane0-provider-outage-closeout-20260918.json` (under `.imp-actual-01-phase-d`)
- **NO** receipt rewrite; outage epoch `121031` gap preserved

## Next work

1. **CALENDAR:** next US equity cash RTH — governed Item 9 `--poll` @ frozen collector when preflight `READY_TO_COLLECT` (third distinct admitted date).
2. **HELD lanes:** continue facts / drawdown / fill / cost v4 on isolated branches; merge only via normal review (not from status PR).
3. **Item 7:** #222 remains **isolated** — do not merge from status docs.

## Model / escalation

Composer only. No Fast/Kimi/Grok High. Single agent.
