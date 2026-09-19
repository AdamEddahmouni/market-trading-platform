# Monday 2026-09-21 Item 9 preflight (prepare without collecting)

**Evidence class:** SOFTWARE / operator coordination. **This document does not start collection.**

**Session this runbook prepares:** US equity cash RTH **Monday 2026-09-21** (next eligible distinct admitted date after **2026-09-17** and **2026-09-18**).

**Mutable tip:** do **not** pin `origin/main` here. After `git fetch origin main`, read **CURRENT_MAIN** / **CURRENT_SOFTWARE_IMPLEMENTATION** from [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md). Frozen collector SHA below is the only git pin this page owns.

Related: [NEXT_RTH_CAMPAIGN_RUNBOOK.md](NEXT_RTH_CAMPAIGN_RUNBOOK.md) (full campaign sequencing; its CURRENT_MAIN table may lag), [ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md](ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md), [IMP_POST_RTH_CLOSE_08_LANE_G.md](IMP_POST_RTH_CLOSE_08_LANE_G.md), [OPERATOR_DIAGNOSTICS_MODEL.md](OPERATOR_DIAGNOSTICS_MODEL.md).

## Frozen collector (do not retarget, do not restart)

| Field | Value |
|-------|--------|
| Worktree | `{repo}/.imp-actual-01-phase-d` |
| IMP root | `{repo}/.imp-actual-01-phase-d/projects/integrated-market-platform` |
| **ITEM9_FROZEN_COLLECTOR** | `fed2d9f7e183aecfcac61a7664df69aafc12ea25` |
| Verify | `git -C .imp-actual-01-phase-d rev-parse HEAD` must equal that SHA |
| Sep 18 stop | Collector **stopped** `2026-09-18T16:00:11` ET; **`ACTIVE_COLLECTORS=0`** at close |

Governed Mode B `--poll` runs **only** from this checkout. Software worktrees (including this docs branch and `origin/main`) are **WRONG_RUNTIME** for collection. Do **not** `git checkout` a newer SHA in `.imp-actual-01-phase-d`. Do **not** restart a collector process against this worktree off-hours or because a software merge landed.

## This weekend (2026-09-19 / 20) — wait, do not collect

| Token | Meaning |
|-------|---------|
| **WAIT** | Off-hours, OpenD down, Live not OFF, duplicate `--poll`, wrong SHA, already-admitted session date, stale OpenD session, or any refusal below |
| **READY_TO_COLLECT** | Preflight JSON from the **frozen** checkout during **Monday RTH**, all gates green. Operator still starts `--poll` **manually**. This docs PR never starts it |

Expected now (weekend / software checkout): `calendar.rth_active=false`, `session_date_et=2026-09-19` (Saturday). Software CLI disposition **`WRONG_RUNTIME`** (exit 1). Frozen `imp.py` has no `item9` group — do not retarget the collector to obtain it. **Neither authorizes `--poll`.**

Item 9 corpus: **2/3** distinct admitted RTH dates → operator **IDLE** (awaiting eligible RTH), **not** platform **DEGRADED**, **not** `CALIBRATED`. Calibration remains **FORBIDDEN**. Full30 **not** run. Live **OFF**. [#222](https://github.com/AdamEddahmouni/market-trading-platform/pull/222) **do not merge**.

## Preflight command (read-only)

`python tools/imp.py item9 next-rth-preflight` exists on **CURRENT_MAIN** (and this docs branch), **not** on frozen `fed2d9f7` (`imp.py` there has no `item9` group). Do **not** upgrade the frozen worktree to get the CLI.

Run preflight from a **software** IMP root that has the command (CPython 3.11 `.venv`):

```powershell
cd projects\integrated-market-platform
python tools\imp.py item9 next-rth-preflight --json
```

Equivalent:

```powershell
python tools\item9_next_rth_preflight.py next-rth-preflight --json
```

Never pass `--poll`. Never invoke `opend_bar_1m_prospective_proof.py prospective` from this docs PR. Preflight **does not** write receipts (`does_not_start_collector=true`).

Because the CLI runtime SHA is **CURRENT_MAIN**, disposition is **`WRONG_RUNTIME`** (`current_runtime_sha_not_frozen_authority`) even when `.imp-actual-01-phase-d` @ `fed2d9f7` is present. That is **honest WAIT** for starting `--poll` from a software worktree. It does **not** mean the frozen pin is missing — check `runtime.frozen_collector_git_sha` and `runtime.frozen_collector_available`.

**READY_TO_COLLECT vs wait (operator composition):** treat collection as allowed only when **all** of the following are true. The software CLI may still print `WRONG_RUNTIME`; do not “fix” that by retargeting the collector.

| Gate | Weekend 2026-09-19/20 | Monday RTH 2026-09-21 |
|------|------------------------|------------------------|
| `calendar.rth_active` | false → **WAIT** | true, `session_date_et=2026-09-21` |
| Frozen SHA | `fed2d9f7…` available | same; **do not restart** |
| `active_collector.detected` | false (`ACTIVE_COLLECTORS=0`) | still 0 before start |
| OpenD `loopback`+`reachable` | may be true; still **WAIT** (not RTH) | required |
| Live OFF | required | required |
| Software CLI disposition | `WRONG_RUNTIME` or `NOT_RTH` → **WAIT** | still `WRONG_RUNTIME` from main; start `--poll` only from frozen checkout after the composed gates pass |

Mode B start (Monday only, **not this PR**): from **frozen** IMP root, `opend_bar_1m_prospective_proof.py prospective --poll` (that script **does** exist at `fed2d9f7`).

Inspect:

- `disposition`
- `calendar.session_date_et` / `calendar.rth_active`
- `provider.loopback` / `provider.reachable`
- `runtime.current_git_sha` / `runtime.runtime_matches_frozen_authority`
- `active_collector.detected` / `active_collector.process_probe_status`
- `receipt_dir`

## ACTIVE_COLLECTORS=0

Before any Monday `--poll`:

1. Preflight `active_collector.detected` must be **false** (`process_probe_status=COMPLETED` on the tools CLI).
2. If `disposition=ACTIVE_COLLECTOR_EXISTS` → **refuse**. Do not start a second `--poll`. Do not kill and restart the frozen checkout “to get a clean SHA.”
3. Post–Sep 18 close recorded **`ACTIVE_COLLECTORS=0`**. Weekend validation must keep that true (inspect only).

## OpenD reachability

Preflight `provider`: `provider_id=moomoo.opend`, loopback host/port, `loopback=true`, `reachable=true`.

Optional extra (still not collection):

```powershell
python tools\moomoo\opend_bar_1m_prospective_proof.py readiness
python tools\provider_readiness.py --probe-local
```

`--probe-local` is loopback TCP only. Yahoo overlay is **not** Item 9 hop L1 and **must not** substitute for OpenD.

## Live OFF

Confirm before Monday collection:

- `LIVE_EXECUTION=OFF` in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md)
- FTEP **not** `EMPIRICAL_ACTIVE`; empirical locks **0**
- Mode B receipts stamp `orders_placed=false`, `calibrated=false`, `empirical_active=false`
- Do not set broker live env; do not merge Live-enabling PRs for this lane

Observational OpenD ≠ live broker execution.

## Corpus-status (frozen `$rcpt`)

Do **not** point `corpus-status` at a software-worktree `artifacts/` copy (often empty). Use the frozen collector directory:

```powershell
# Linked worktrees: --show-toplevel is the worktree, not the primary checkout.
# --git-common-dir is <primary>/.git even from .worktrees/*.
$repo = (Resolve-Path (Join-Path (git rev-parse --path-format=absolute --git-common-dir) "..")).Path
$rcpt = Join-Path $repo ".imp-actual-01-phase-d\projects\integrated-market-platform\artifacts\ftep-v1-002\item9-prospective-proof-receipts"
python tools\item9_corpus_status.py corpus-status --receipt-dir $rcpt
```

Read-only. **No** calibration fit. Expect **`distinct_rth_dates=2/3`** until Monday earns a third **admitted** date.

## Expected receipt path

Governed prospective JSON:

`{repo}/.imp-actual-01-phase-d/projects/integrated-market-platform/artifacts/ftep-v1-002/item9-prospective-proof-receipts/<experiment_id>.json`

Contract `item9.bar-ohlcv-prospective-proof/1.1.0`. Monday `--receipt-out` must stay under that frozen IMP tree. Empty `raw_provenance_hash` is path-proof only and is **not** corpus-admissible.

## Expected date handling (do not admit `121031`)

| Date / token | Treatment |
|--------------|-----------|
| **2026-09-17**, **2026-09-18** | Already **admitted**. Duplicate-date: do not run a second Mode B session to “re-collect” these days |
| **2026-09-14…16** | **NOT_ADMITTED** (RTH activity ≠ admission) |
| **2026-09-21** | Next **eligible** US cash RTH date for a third distinct admitted date — only if calendar + admission rules pass **that day** |
| Epoch **`121031`** | Operator tag for Sep 18 outage `item9-prospective-20260918-epoch-fed2d9f7-aapl-121031`. Receipt **NONE**. **Not** a session date. **Not** an admitted RTH date. **Do not backfill** |

`calendar.session_date_et` must be ISO `YYYY-MM-DD` in `America/New_York`. Refuse any attempt to treat `121031` as `session_date_et` or as a third distinct RTH date.

## Refusal conditions (fail closed)

Do **not** start `--poll` when any of these hold:

| Disposition / condition | Action |
|-------------------------|--------|
| `NOT_RTH` | **WAIT** — off-hours / weekend / before 09:30 ET |
| `WRONG_RUNTIME` | **WAIT** — leave frozen worktree at `fed2d9f7`; run preflight there, never retarget |
| `PROVIDER_UNAVAILABLE` | See [OpenD unavailable](#opend-unavailable) |
| `ACTIVE_COLLECTOR_EXISTS` | **Refuse duplicate**; inspect; do not restart frozen collector |
| `OUTPUT_PATH_INVALID` | Fix governed receipt dir under frozen IMP root; do not write elsewhere |
| Session date already admitted (17/18) | **WAIT** for a new distinct date |
| `121031` backfill / gap fill | **Forbidden** |
| Calibration / Full30 / Live / merge #222 | **Forbidden** this lane |

`READY_TO_COLLECT` without a human operator start is still **no collection**.

## Duplicate-date protection

1. Confirm `calendar.session_date_et` is **2026-09-21** (Monday) before `--poll`.
2. Confirm corpus-status admitted dates remain **only** 2026-09-17 and 2026-09-18.
3. One governed `--poll` session per eligible RTH date. Do not launch a second `--poll` because the first timed out without a corpus-admissible receipt unless preflight again shows `ACTIVE_COLLECTORS=0` and the operator documents a **new** bounded run (new experiment id). Never reuse the `121031` experiment id.

## Restart safety

- Do **not** restart, rebase, or retune `.imp-actual-01-phase-d` @ `fed2d9f7`.
- Do **not** start `--poll` to “warm” OpenD on the weekend.
- Stale **software** UI/API processes (`:8766` / `:5173` / `:8767`) may be stopped with `STOP_PLATFORM.cmd`; that is **not** permission to restart Item 9 collection.
- If a leftover `--poll` is found: **inspect**. Do not SIGKILL-and-relaunch to manufacture a passing window.

## Post-close verification (Monday 16:00 ET, after collection if it ran)

1. Confirm collector process gone → **`ACTIVE_COLLECTORS=0`**.
2. Frozen HEAD still `fed2d9f7e183aecfcac61a7664df69aafc12ea25`.
3. Corpus-status on **`$rcpt`** (frozen path).
4. If 2026-09-21 admitted: **3/3** distinct dates is the **sample-date floor only** — still **`NOT_CALIBRATED`**, still **`ITEM9_CALIBRATION_RUN=FORBIDDEN`**. Progress truth **HEALTHY** for that floor is **not** calibration.
5. Do not rewrite failed receipts; do not fill `121031`.
6. `python tools\rth_empirical_ops.py --json summarize` optional. Live still OFF. Do not merge #222.

## OpenD unavailable

If `PROVIDER_UNAVAILABLE` / `opend_unreachable` / `opend_not_loopback`:

1. **WAIT.** Do not collect.
2. Do not swap Yahoo delayed quotes into Mode B.
3. Do not backfill the gap later as prospective evidence.
4. Do not invent a `121031`-class receipt.
5. Log the disposition; retry preflight when loopback OpenD is actually reachable **during RTH**.

## Stale session

If OpenD TCP looks up but session is leftover (overnight login, Sep 18 quote context, `MOOMOO_PROTOCOL_ERROR` / empty kline, Control “healthy” while preflight is not):

1. Treat as **not READY_TO_COLLECT** until a **fresh** authenticated loopback session exists **on Monday RTH**.
2. Do **not** restart the **frozen collector git worktree**.
3. Do **not** relabel a failed observation as success.
4. Empty or pre-signal bars stay fail-closed (`PROSPECTIVE_NO_POST_SIGNAL_BAR` is honest).

State-path split (`WORKTREE_STATE_MISMATCH`): use canonical `IMP_STATE_DIR` from `python tools\state_path_diagnostic.py`. Empty worktree `.local` is not proof FTEP state is absent.

## Explicit prohibition: `121031` backfill

**Forbidden:** creating, renaming, or admitting `item9-prospective-20260918-epoch-fed2d9f7-aapl-121031` (or any receipt whose identity is that outage epoch); hashing later-known kline into that gap; counting `121031` as a distinct RTH date.

First recovery after the gap remains `item9-prospective-20260918-epoch-fed2d9f7-aapl-135512.json` (historical, already on disk). Leave it.

## Item 9 status heading

**2/3 IDLE** — awaiting eligible RTH (Monday 2026-09-21 if gates pass). **Not DEGRADED.** **Not CALIBRATED.** Sample gate `INSUFFICIENT_CALIBRATION_EVIDENCE` until floors are met (**20** observations, **3** distinct admitted dates, **5** eval rows) **and** a separate governed calibration run is authorized — that run is **out of scope** for Monday collection.

## Monday mechanical sequence (operator; not this PR)

Only when **WAIT** is cleared:

1. Frozen SHA check.
2. `ACTIVE_COLLECTORS=0`.
3. Live OFF.
4. Preflight from frozen IMP root → **`READY_TO_COLLECT`**.
5. Session date **2026-09-21**.
6. Manual Mode B `--poll` from frozen checkout (see [ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md](ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md)).
7. After receipt: corpus-status on **`$rcpt`**.
8. Post-close verification.

This repository change **stops at step 4 documentation**. No Item 9 collection, no calibration, no Full30, no Live, no #222 merge.
