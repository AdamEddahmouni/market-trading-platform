# Why RTH-OBS-NEWS-20260924 was not armed

**Evidence class:** `OPERATIONAL_ONLY`. This note does not arm a campaign and does not backfill.

Session record: [RTH_OBS_NEWS_20260924_SESSION.md](RTH_OBS_NEWS_20260924_SESSION.md).

## Root cause

The freeze existed and `arm_performed` stayed false. No operator ran `campaign_supervisor.py arm` before 09:30 ET. By 14:21 ET the campaign state directory, supervisor, poller, and API listener were absent. The window was already missed. A late arm was not performed.

## Contributing factors

- `environment-preflight` could return `ready_to_arm: true` while the Finviz credential was only a warning, unless `--require-finviz-live-ingress` was passed. The Sep 24 launch sequence did not pass that flag.
- `arm` did not load the freeze. It did not refuse a wrong SHA, a dirty tree, a wrong campaign id, a clock outside the pre-open window, Live, or calibration.
- The arm procedure was a long manual sequence. Nothing failed closed when that sequence was never started.
- Control can show `NOT_ARMED` only after the API is up. The API was not started, so the UI alert never appeared.
- The primary checkout was not a clean `origin/main` worktree. Launching from the wrong tree was possible.

## Non-causes

- Radar action convergence did not arm or block the campaign.
- Sep 23 `PARTIAL_LATE_ARM` was not reused.
- No provider outage was observed, because no poller ran.

## External dependency

A Finviz credential must be visible to the ingress resolver in the launch shell. The check reports presence only. It does not print the secret. On 2026-09-24 the observation shell did not have that credential.

## Correction

`campaign_supervisor.py go-no-go --freeze <file>` is the pre-open contract. `arm --freeze <file>` refuses unless that contract returns `READY_FOR_PRE_RTH_ARM`. The next campaign is `RTH-OBS-NEWS-20260925`. It is not armed by this note.
