# short-squeeze history

Complete chronological commit index for `short-squeeze`.
The full commit body and changed paths are preserved in the JSONL ledger.

## 2026-07-26

- `2a9277a5e196` — feat: complete research screener with live data, multi-provider enrichment, and Finviz discovery
  - Author: AdamEddahmouni (2026-07-26T15:10:00-04:00)
  - Rationale (commit-subject-and-body): - Scanner UI with FROZEN/LIVE mode toggle, classification legend, countdown timer
- Multi-source fallback chains: price (IBKR → Finviz → Finnhub), change % (IBKR → Finviz → computed), rel volume (IBKR/Finviz → Finviz provider)
- Finviz Elite screener as parallel discovery source alongside IBKR scanner
- Live news feed from Finnhub News + SEC EDGAR with ticker classification filtering
- Provider status bar showing IBKR, Finviz Elite, Finnhub, SEC EDGAR connectivity
- Real-time auto-refresh with configurable intervals
- Export, detail drawer, filter/sort with full fallback chain support
- Archived project code and reconstruction documentation
- `262e3f136c0d` — fix: bugs + strip verbose disclaimers + harden Railway deployment
  - Author: AdamEddahmouni (2026-07-26T15:35:09-04:00)
  - Rationale (commit-subject-and-body): - Fix _finviz_fields() overwriting float_shares metadata from short_pressure_fields()
- Fix provider_health() using global sentiment analyzer instead of runtime's
- Fix test assertions for new FINVIZ_SCREENER discovery profile (5 profiles)
- Strip verbose disclaimer/yapping text from 11 files (discovery, snapshot,
  session_state, frozen, frozen_demo, api_contract, scanner.html, index.html,
  app.js, __init__.py)
- Harden railway.toml with explicit service config and health check timeout
- Cloud mode verified: health/ready endpoints, frozen demo data all serving
- `5516c5392ad7` — feat: add root-level Railway deployment configuration
  - Author: AdamEddahmouni (2026-07-26T15:38:32-04:00)
  - Rationale (commit-subject-and-body): - Root railway.toml points to short-squeeze-core/Dockerfile
- Root .railwayignore excludes non-deployment files
- Cloud mode verified: health/ready endpoints, frozen demo serving
- Railway auto-detects config, no dashboard setup needed beyond connecting repo
- `d64fa1373060` — fix: Railway root now renders live scanner — parallel frozen+live init
  - Author: AdamEddahmouni (2026-07-26T15:42:57-04:00)
  - Rationale (commit-subject-and-body): Reversed loadScanner() to try live discovery in parallel with frozen
rendering, so the page shows data instantly (frozen demo) while live
discovery runs in the background. Live data swaps in automatically when
ready. Clean live-mode banner. Cloud deployments now go straight to the
live scanner view with no frozen-first flicker.
- `68550e9a4394` — docs: add Railway deploy button badge to README
  - Author: AdamEddahmouni (2026-07-26T15:44:03-04:00)
  - Rationale (commit-subject-and-body): Prominent one-click deploy button below the description so the
professor can launch directly to Railway from the repo. Also
expanded the Containers section with Railway-specific env vars
and deployment notes.
- `080a321ef503` — feat: add Railway deploy CI workflow with source sync and deployment status polling
  - Author: AdamEddahmouni (2026-07-26T17:26:45-04:00)
  - Rationale (commit-subject-and-body): GitHub Actions workflow that auto-deploys short-squeeze-core/.railway-deploy/
to Railway on pushes to main:
- Triggers on changes to apps/, src/, scripts/, pyproject.toml, or .railway-deploy/
- Rsyncs latest source into .railway-deploy/ before deploying
- Runs `railway up --detach --environment production` for fast upload
- Polls Railway GraphQL API every 30s tracking BUILDING/DEPLOYING/SUCCESS/FAILED
- Surfaces build logs on failure and deployment URL on success
- 10-minute timeout with ::error:: annotation
- `43028c310df8` — chore: absorb short-squeeze-core nested repo into parent, remove duplicate .git/
  - Author: AdamEddahmouni (2026-07-26T17:35:56-04:00)
  - Rationale (commit-subject-and-body): The short-squeeze-core/ directory had its own .git/ making it an independent
nested repository. This made it impossible to track changes from a single
source and prevented CI workflows (e.g. Railway deploy) from seeing all files.
- `78b38b7e8ba1` — feat: set GitHub commit status with Railway deploy URL on success
  - Author: AdamEddahmouni (2026-07-26T17:37:59-04:00)
  - Rationale (commit-subject-and-body): Adds a `permissions: statuses: write` block and a `gh api` call inside
the SUCCESS polling case that annotates the commit with a direct link
to the live Railway deployment, visible in the GitHub PR / commit list.
- `7eb3c0b90ad2` — feat: add make deploy and make deploy-sync targets
  - Author: AdamEddahmouni (2026-07-26T17:39:35-04:00)
  - Rationale (commit-subject-and-body): - deploy-sync: rsyncs source directories into .railway-deploy/ (dry-run)
- deploy: depends on deploy-sync, installs Railway CLI if needed, runs
  `railway up --detach --environment production` mirroring the CI workflow
- Both added to .PHONY and make help output
- `f31a5dfcb1b4` — docs: add Railway deploy workflow documentation
  - Author: AdamEddahmouni (2026-07-26T17:41:11-04:00)
  - Rationale (commit-subject-and-body): Covers the full CI/CD pipeline end-to-end:
- How the GitHub Actions workflow works (sync, deploy, poll, commit status)
- Prerequisites: creating a Railway deploy token and adding RAILWAY_TOKEN secret
- Trigger paths and how to test a deploy locally via make deploy
- Environment variables required at runtime
- Troubleshooting common failures
- `f392e48e8baa` — feat: add post-deploy health check to Railway CI workflow
  - Author: AdamEddahmouni (2026-07-26T17:46:05-04:00)
  - Rationale (commit-subject-and-body): After a successful deploy, curls the /health endpoint with a retry loop
(3 attempts × 10s timeout, 5s between retries) and fails the workflow
if it doesn't return 200. Prevents deploying a broken container.
- `a934dededd22` — chore: add **/.git/ to .gitignore to prevent future nested repos
  - Author: AdamEddahmouni (2026-07-26T18:01:56-04:00)
  - Rationale (commit-subject-and-body): The short-squeeze-core/ directory had its own .git/ making it an
independent nested repository. The **/.git/ pattern prevents this
from happening again by matching .git/ at any directory depth.
- `5c3cf5942aed` — chore: gitignore *.log and data/ to keep generated runtime files out of version control
  - Author: AdamEddahmouni (2026-07-26T18:07:08-04:00)
  - Rationale (commit-subject-and-body): Adds `data/` (Chroma DB cache, brain index) and `*.log` (server startup logs)
to the parent .gitignore so they no longer appear as untracked files in git status.
- `ce2b60d32f67` — chore: gitignore docs/reconstruction/ — agent-generated reference docs
  - Author: AdamEddahmouni (2026-07-26T18:08:26-04:00)
  - Rationale (commit-subject-and-body): These reconstruction documents are useful for reference but should not
be committed to the main repo history.
- `f02dcf828a9a` — feat: add make tidy target for git garbage collection and cleanup
  - Author: AdamEddahmouni (2026-07-26T18:09:38-04:00)
  - Rationale (commit-subject-and-body): Runs `git gc --aggressive --prune=now` followed by `git remote prune origin`
to compact the repository and remove stale remote-tracking branches.
- `8eaed57a5564` — feat: add make precommit and make install-hooks targets
  - Author: AdamEddahmouni (2026-07-26T18:12:16-04:00)
  - Rationale (commit-subject-and-body): - precommit: runs Python import checks on all key modules (config,
  credentials, ibkr_gateway, __main__) and validates Makefile syntax
  via `make help`, exits 1 on any failure
- install-hooks: writes a .git/hooks/pre-commit script that cds to
  the correct subdirectory and runs `make precommit` on every commit
- Hook supports SKIP_CHECKS=1 env var and --no-verify to bypass
- `14726f22d563` — feat: add make precommit-quick target for fast import-only checks
  - Author: AdamEddahmouni (2026-07-26T18:15:23-04:00)
  - Rationale (commit-subject-and-body): Refactors the precommit flow:
- precommit-quick: runs Python import checks only (config, credentials,
  ibkr_gateway, __main__) — skips the `make help` syntax validation
- precommit: now depends on precommit-quick, then runs `make help` check
- Follows the same dependency pattern as deploy: deploy-sync
- `a1eadd5c11bb` — feat: add make test-quick target for fast import checks and smoke tests
  - Author: AdamEddahmouni (2026-07-26T18:16:54-04:00)
  - Rationale (commit-subject-and-body): Depends on precommit-quick (import checks), then runs pytest on the
two fastest test files (test_serialization.py, test_contract_validation.py)
for a rapid sanity check before pushing.
- `5486d03f3a1a` — feat: add pre-commit CI workflow for pull requests
  - Author: AdamEddahmouni (2026-07-26T18:17:56-04:00)
  - Rationale (commit-subject-and-body): Runs `make precommit` (Python import checks + Makefile validation) on
every PR push touching apps/, src/, scripts/, pyproject.toml, or
Makefile. Catches import errors and syntax issues before they merge
to main.
- `2ffda300f723` — docs: preregister Phase 3E systematic historical evidence construction
  - Author: AdamEddahmouni (2026-07-26T20:50:22-04:00)
  - Rationale (commit-subject-and-body): Preregisters Phase 3E on branch phase/3e-systematic-historical-acquisition
before any outcome data access. Stage 1 constructs outcome-blind point-in-time
evidence layers for the 13 registry-only Phase 3D pilot symbols using the
authenticated IBKR connection and existing public provider adapters. Stage 2
(outcome acquisition) requires a separate batch-level plan before execution.
- `c735a96a7f86` — docs: add Phase 3E evidence-readiness audit for 13 registry-only symbols
  - Author: AdamEddahmouni (2026-07-26T20:55:21-04:00)
  - Rationale (commit-subject-and-body): Audits all 13 Phase 3D pilot symbols (XNCR, PESI, SLS, ZNTL, GPRE, SSPC,
LBGJ, TRVI, LMNX, MGNX, BHVN, OBE, AVTX) for Phase 3A evidence-domain
availability. Identifies NORMALIZED_POINT_IN_TIME_EVIDENCE as the single
critical blocker, with IBKR bar-semantics resolution as the dependency.
- `3ed925f88842` — feat: accept honest UNKNOWN IBKR bar semantics with documented provenance (ADR 0066)
  - Author: AdamEddahmouni (2026-07-26T21:06:56-04:00)
  - Rationale (commit-subject-and-body): IBKR TRADES historical bars have honestly UNKNOWN volume_adjustment_semantics
and timestamp_semantics (official IBKR documentation is silent on these fields).
The existing intake contract treated any UNKNOWN as a fatal rejection, blocking
the 13 Phase 3D detection-context CSVs from normalization.
- `1fa2e4de04b0` — feat: normalize 13 IBKR detection-context CSVs through intake pipeline (ADR 0066)
  - Author: AdamEddahmouni (2026-07-26T21:14:27-04:00)
  - Rationale (commit-subject-and-body): All 13 Phase 3D pilot symbols' detection-context bar CSVs now pass the intake
pipeline and reach READY_FOR_FUTURE_ASSOCIATION. The ColumnMappingProfile maps
the IBKR CSV columns (timestamp_utc, open, high, low, close, volume, wap,
requested_symbol). IntakeManifests declare price=SPLIT_ADJUSTED,
volume=UNKNOWN, timestamp=UNKNOWN per ADR 0066, with provider_name="Interactive
Brokers" triggering the IBKR-specific UNKNOWN acceptance.
- `2b0a978fefc2` — feat: add evidence-bundle construction script for 13 IBKR pilot symbols (Phase 3E Stage 1)
  - Author: AdamEddahmouni (2026-07-26T21:41:40-04:00)
  - Rationale (commit-subject-and-body): Constructs PointInTimeEvidenceBundles combining normalized detection-context
bars (via phase3a_freeze.evidence_adapter) with scanner-snapshot metadata
(batch01_discovery_rows.json). Performs O(n²) conflict detection (~30-60s per
symbol). Each bundle is saved incrementally to
build/acquisition/evidence-bundles/{symbol}/ with resume support.
- `8ade7af49c77` — feat: add multiprocessing, profiling, and preflight-regeneration scripts — refs: `refs/heads/phase/3e-systematic-historical-acquisition`
  - Author: AdamEddahmouni (2026-07-26T23:41:34-04:00)
  - Rationale (commit-subject-and-body): - build_evidence_bundles.py: add parallel execution via ProcessPoolExecutor
  (--workers/--sequential flags), per-phase timing instrumentation, stdout
  capture to build-log.txt, and utf-8 encoding on all file writes
- profile_avtx.py: cProfile-based profiling script to measure actual O(n²)
  build_conflicts time per symbol
- regenerate_preflight_reports.py: diagnostic script to re-run preflight
  pipeline with current ADR 0066 IBKR exemption
- `19fd793b7d1b` — Merge phase/3e-systematic-historical-acquisition into main
  - Author: AdamEddahmouni (2026-07-26T23:44:22-04:00)
  - Rationale (commit-subject-and-body): Brings in 6 commits from the feature branch:
- feat: add evidence-bundle construction script for 13 IBKR pilot symbols (Phase 3E Stage 1)
- feat: normalize 13 IBKR detection-context CSVs through intake pipeline (ADR 0066)
- feat: accept honest UNKNOWN IBKR bar semantics with documented provenance (ADR 0066)
- docs: add Phase 3E evidence-readiness audit for 13 registry-only symbols
- docs: preregister Phase 3E systematic historical evidence construction
- feat: add multiprocessing, profiling, and preflight-regeneration scripts

## 2026-07-27

- `f2c60c896640` — docs: preregister Phase 3E Stage 2 acquisition plan
  - Author: AdamEddahmouni (2026-07-27T01:23:20-04:00)
  - Rationale (commit-subject-only): Rationale stated in commit subject only.
- `779242afca83` — feat: acquire forward outcome bars for 13 IBKR pilot symbols
  - Author: AdamEddahmouni (2026-07-27T01:28:51-04:00)
  - Rationale (commit-subject-and-body): Stage 2 forward bar collection using the adjusted Monday window
(2026-07-21 -> 2026-07-22) per the preregistered window adjustment rule.
- `6023dc264c39` — fix: optimize O(n^2) conflict detection and add Phase 3A freeze script
  - Author: AdamEddahmouni (2026-07-27T02:15:48-04:00)
  - Rationale (commit-subject-only): Rationale stated in commit subject only.
- `9a426813e714` — perf: parallelize Phase 3A freeze with ProcessPoolExecutor — refs: `refs/heads/phase/3e-stage2-outcome-acquisition`
  - Author: AdamEddahmouni (2026-07-27T03:15:39-04:00)
  - Rationale (commit-subject-and-body): Mirrors the multiprocessing pattern in scripts/acquisition/build_evidence_bundles.py to cut the 13-symbol freeze (Phase 3E Stage 2 Step 3) from ~20 min sequential to a few seconds per symbol on a multi-core box. Adds --sequential, --workers, --force flags; resume-on-existing-freeze preserves byte-exact prior output. Exit-code semantics preserved (0 = no exception; None returns are soft skips).
- `5dc592aad49e` — Merge phase/3e-stage2-outcome-acquisition: parallelize Phase 3A freeze
  - Author: AdamEddahmouni (2026-07-27T03:16:54-04:00)
  - Rationale (commit-subject-only): Rationale stated in commit subject only.
- `8a74d4f20e11` — feat: add Stage 2 Step 4 outcomes + leakage audit + Phase 3B publication
  - Author: AdamEddahmouni (2026-07-27T03:32:49-04:00)
  - Rationale (commit-subject-and-body): Implements Phase 3E Stage 2 Step 4 as a single consolidated script (scripts/acquisition/stage2_step4.py). Three sub-phases invoked by --step outcomes|audit|publish|all:
- `87d5d1206f3b` — fix: resolve 5 unrelated pytest failures + Windows WinError 5 cleanup
  - Author: AdamEddahmouni (2026-07-27T04:03:31-04:00)
  - Rationale (commit-subject-and-body): tests: 3 outcome-window tests reordered to populate-all-first, write-target-last; test_publish_produces_registry_batch_and_dataset reuses BASE_EVALUATION via model_copy and re-exported BatchEvaluationResult/ResearchDataset so step4.X resolves; outcome_label assertion corrected from INSUFFICIENT_DATA to UNKNOWN per label_outcome policy v1. script: audit check #5 now uses FREEZE_DIR.rglob("outcomes_manifest.json") recursive scan; deleted duplicate def main(); cleaned up walrus-misuse in sample_size. pyproject: addopts pyproject.toml -q --basetemp=.pytest-tmp -> -q -p no:cacheprovider to redirect working-area + cache from polluted project root to OS tempdir, eliminating Pytest WinError 5 on Windows cleanup. All 13 tests in tests/acquisition/test_stage2_step4.py now pass on Windows; tests/r...
- `0de44a243b3e` — docs: Phase 3E Stage 2 completion — 1/13 LBGJ empirical outcome, five Phase 3C standard-cohort analyses + reports
  - Author: AdamEddahmouni (2026-07-27T04:20:13-04:00)
  - Rationale (commit-subject-and-body): scripts/acquisition/run_stage2_phase_3c_analysis.py: Stage 2 Step 6 wrapper. Iterates the five Phase 3C standard cohorts on the 13-symbol IBKR pilot dataset (historical_case_boundary, historical_unique_symbol, synthetic, all_registered, partial_blocked). Uses the in-process squeeze_core.__main__:main entrypoint; catches SystemExit + Exception to keep the cohort iteration alive on per-cohort config errors; emits an empirical-coverage note (included=N, excluded=M) per cohort so the headline 1/13 LBGJ finding is visible in operator stdout.
- `2b04a38c069b` — feat(screener): cap current set and harden live resilience
  - Author: AdamEddahmouni (2026-07-27T06:07:05-04:00)
  - Rationale (commit-subject-and-body): Co-authored-by: Cursor <cursoragent@cursor.com>
- `e85fc72f1e08` — fix(contracts): restore config and disclosure test expectations
  - Author: AdamEddahmouni (2026-07-27T06:07:33-04:00)
  - Rationale (commit-subject-and-body): Co-authored-by: Cursor <cursoragent@cursor.com>
- `c71f2ffa701a` — feat(screener): live 50-ticker screen, collectors, and news/SI UX
  - Author: AdamEddahmouni (2026-07-27T07:02:00-04:00)
  - Rationale (commit-subject-and-body): Harden news orchestration and propagate headlines into the scanner. Prioritize up to 50 squeeze candidates with gap-driven refresh and continuous background collectors (FINRA, RSS, optional APIs) merged into supplemental fields without overwriting known provider evidence.
- `d7904ed9675b` — fix(deploy): harden Railway CI and cloud container startup
  - Author: AdamEddahmouni (2026-07-27T07:47:44-04:00)
  - Rationale (commit-subject-and-body): Add Railway CLI to GITHUB_PATH, require RAILWAY_TOKEN, and document monorepo root-directory and healthcheck fixes. Run production Docker CMD in CLOUD_PROVIDER_MODE with a longer health timeout.
- `741bc7b6e6ef` — fix(deploy): poll Railway status via CLI for project tokens
  - Author: AdamEddahmouni (2026-07-27T08:00:41-04:00)
  - Rationale (commit-subject-and-body): Project-scoped RAILWAY_TOKEN cannot query projects via GraphQL; wait on railway deployment list and smoke-test the known public URL instead.
- `719641f19d4c` — fix(deploy): pass GH_TOKEN so commit status updates work in CI
  - Author: AdamEddahmouni (2026-07-27T08:03:11-04:00)
  - Rationale (commit-subject-and-body): The wait step was exiting after a successful Railway deploy because gh lacked authentication.
- `6a8bb4fce783` — feat(scanner): declutter scan UI and align backend
  - Author: AdamEddahmouni (2026-07-27T09:01:51-04:00)
  - Rationale (commit-subject-and-body): Simplify scanner table and styling, extend session and provider wiring, and lock the scan contract with updated tests and deploy mirror.
- `8abb36bcbe04` — chore(deploy): sync .railway-deploy mirror with canonical source
  - Author: AdamEddahmouni (2026-07-27T09:09:12-04:00)
  - Rationale (commit-subject-and-body): Keep the Railway deploy tree aligned with apps, src, and scripts so git matches what CI rsyncs before railway up.
- `f44d6970b2f6` — fix(packaging): bundle evaluation policy JSON in wheel install
  - Author: AdamEddahmouni (2026-07-27T09:27:41-04:00)
  - Rationale (commit-subject-and-body): Live discovery and CURRENT screener load phase 3a policy from site-packages; include JSON policy assets in setuptools package-data so Railway images have the files.
- `87e5189a4c04` — Improve scanner evidence display, exports, and UI contrast.
  - Author: AdamEddahmouni (2026-07-27T11:40:18-04:00)
  - Rationale (commit-subject-and-body): Use field-based ADAM coverage in the methodology and show category plus field fraction in the scanner; add snapshot and CSV export on scanner and advanced views; fix low-contrast provider and news link styling.
- `040ae73df989` — feat(deploy): enable cloud IBKR and Railway ib-gateway sidecar
  - Author: AdamEddahmouni (2026-07-27T12:11:43-04:00)
  - Rationale (commit-subject-and-body): Opt-in IBKR for CLOUD_PROVIDER_MODE via env vars and remote gateway connections; add ib-gateway Railway service template, CI deploy job, and bundle tools/ in the screener image for IB API support.
- `3bdf9488d1e1` — fix(deploy): sync tools into Railway image and CI paths
  - Author: AdamEddahmouni (2026-07-27T12:12:50-04:00)
  - Rationale (commit-subject-and-body): Co-authored-by: Cursor <cursoragent@cursor.com>
- `b798e5de1094` — fix(deploy): include tools in Railway build context
  - Author: AdamEddahmouni (2026-07-27T12:19:23-04:00)
  - Rationale (commit-subject-and-body): Co-authored-by: Cursor <cursoragent@cursor.com>
- `f7444d4bae25` — fix(deploy): stop ignoring tools in Railway upload context
  - Author: AdamEddahmouni (2026-07-27T12:25:08-04:00)
  - Rationale (commit-subject-and-body): Co-authored-by: Cursor <cursoragent@cursor.com>
- `6591a9260716` — Fix live scoring correctness and ship professional reproducible docs.
  - Author: AdamEddahmouni (2026-07-27T13:41:37-04:00)
  - Rationale (commit-subject-and-body): Align catalyst age, Finviz conflict withholding, admissibility, and opt-in API locks with product intent; add Diátaxis docs, OpenAPI/csrf coverage, and CI pytest without rotating credentials.
- `bc771944072c` — Remove personal correspondence and local handoffs from the repo.
  - Author: AdamEddahmouni (2026-07-27T15:02:06-04:00)
  - Rationale (commit-subject-and-body): Drop advisor logs, demo transcripts, reconstruction source material, and internal session handoffs; extend .gitignore and redact local machine paths in batch docs so the private collaborator repo stays product-focused.
- `fcff96409160` — docs: drop removed reconstruction folder from root README
  - Author: AdamEddahmouni (2026-07-27T15:03:42-04:00)
  - Rationale (commit-subject-and-body): Co-authored-by: Cursor <cursoragent@cursor.com>
- `5cb46d0c24a0` — fix(deploy): repair Railway monorepo root builds and CI triggers
  - Author: AdamEddahmouni (2026-07-27T15:08:18-04:00)
  - Rationale (commit-subject-and-body): Add a repository-root Dockerfile with short-squeeze-core COPY paths for Railway
GitHub deploys, point railway.toml at it, include tools in the upload context,
and run the deploy workflow on every push to main.
- `2b24b7c53bb4` — fix(deploy): align Railway GitHub commit statuses with Actions deploys
  - Author: AdamEddahmouni (2026-07-27T15:18:00-04:00)
  - Rationale (commit-subject-and-body): Post success to Railway integration context when CLI deploy succeeds, and add workflow_dispatch backfill for recent main commits.

## 2026-07-31

- `f4f3947b5680` — docs: define video presentation package
  - Author: AdamEddahmouni (2026-07-31T14:30:23-04:00)
  - Rationale (commit-subject-only): Rationale stated in commit subject only.
- `17b39011f29d` — Prepare repository for public release.
  - Author: AdamEddahmouni (2026-07-31T20:43:46-04:00)
  - Rationale (commit-subject-and-body): Add MIT license, SECURITY.md, CONTRIBUTING.md, and a CI release-audit workflow.
Scrub hardcoded API keys from archived code, rename internal meeting docs, and
harden .gitignore for node_modules and pytest artifacts.
- `3f29c1e236c4` — Remove tracked __pycache__ bytecode from archived ScreenerPython.
  - Author: AdamEddahmouni (2026-07-31T21:13:17-04:00)
  - Rationale (commit-subject-and-body): Co-authored-by: Cursor <cursoragent@cursor.com>
- `20385e3d4309` — Strip academic archives and presentation artifacts; keep screener only.
  - Author: AdamEddahmouni (2026-07-31T22:06:29-04:00)
  - Rationale (commit-subject-and-body): Remove archived-project-code, batch/phase journals, operator kits, research
pipeline scripts, and presentation deliverables. Update docs, CI, and tests to
match the screener-focused repository layout.
- `c09e0dc35b65` — Fix release audit false positives for public CI.
  - Author: AdamEddahmouni (2026-07-31T22:31:47-04:00)
  - Rationale (commit-subject-and-body): Skip tests and deploy mirrors from audit scope and allowlist the backward-compatible /api/professor route documentation.

## 2026-08-15

- `ee4de9f09128` — Correct provider entitlement claims and restore BIYA acquisition CLI.
  - Author: AdamEddahmouni (2026-08-15T22:07:42-04:00)
  - Rationale (commit-subject-and-body): Remove unsupported Finnhub premium and IBKR tick-258 borrow-fee assertions, document provider capabilities accurately, and restore the outcome acquisition script removed during archive stripping.

## 2026-08-16

- `3fc639c78605` — feat: add Phase 3D counterfactual calibration layer
  - Author: AdamEddahmouni (2026-08-16T04:10:55-04:00)
  - Rationale (commit-subject-and-body): Introduce calibration experiments for detection ablation and outcome sensitivity, with governance policy, ADR-0067 findings, suite tooling, and generated reports on the expanded historical cohort.
- `7cc0a71aca06` — feat: expand IBKR historical cohort and BIYA short-pressure fixtures
  - Author: AdamEddahmouni (2026-08-16T04:16:26-04:00)
  - Rationale (commit-subject-and-body): Add Phase 3A evaluation fixtures for TRVI, LBGJ, KLRS, SG, and SLS, extend IBKR export tooling, regenerate research/analysis anchors, and update BIYA regression tests for acquired FINRA short-interest evidence.
- `a6b9877d9b3c` — feat: revive Phase 3E historical acquisition on rebased branch
  - Author: AdamEddahmouni (2026-08-16T04:17:26-04:00)
  - Rationale (commit-subject-and-body): Cherry-pick Phase 3E design docs, evidence readiness audit, Stage 2 preregistered plan, and acquisition scripts onto current main after Phase 3D and cohort expansion land.
- `17f4b6e04bf6` — fix: accept ADR-0066 IBKR unknown bar semantics at intake
  - Author: AdamEddahmouni (2026-08-16T04:21:25-04:00)
  - Rationale (commit-subject-and-body): Resolve Batch 05 preflight rejections by declaring official IBKR TRADES semantics, scoping UNKNOWN volume and timestamp acceptance to Interactive Brokers, and treating IBKR timestamps as bar-start when semantics are UNKNOWN.
- `883bc42932fe` — feat: add BIYA short-pressure acquisition plan runner
  - Author: AdamEddahmouni (2026-08-16T04:24:54-04:00)
  - Rationale (commit-subject-and-body): Execute the preregistered FINRA short-interest capture and honest IBKR borrow attempt without disturbing unrelated BIYA acquisition artifacts.
- `9a3fe4a9e7ca` — feat: integrate Phase 3E Stage 2 forward outcomes into cohort fixtures
  - Author: AdamEddahmouni (2026-08-16T04:31:17-04:00)
  - Rationale (commit-subject-and-body): Prefer stage2 forward-outcome bars in IBKR cohort generation, refresh research and analysis anchors from updated outcome observations, document cohort expansion progress toward n=30, and mark the Stage 2 acquisition plan executed.
- `0b408349ab62` — feat: complete Phase 3E Stage 2 pipeline and expand IBKR cohort fixtures
  - Author: AdamEddahmouni (2026-08-16T23:03:16-04:00)
  - Rationale (commit-subject-and-body): Wire run_stage2_pipeline orchestration (outcomes, post-outcome leakage audit, Phase 3B/3C outputs), expand fixture regen to all 15 IBKR symbols, add phase3e tests, and relax demo_readiness to accept any non-zero canonical case count.

## 2026-09-04

- `8a5e43e8b0ff` — feat: complete Phase 3F external cohort expansion and calibration findings
  - Author: AdamEddahmouni (2026-09-04T22:51:54-04:00)
  - Rationale (commit-subject-and-body): Phase 3F cohort expansion batches 01-05 (external discovery preregistration,
identity audit, BIYA bar intake, AACP forward-outcome retry) with intake
manifests and normalized discovery rows; ADAM weight-floor and classification
threshold calibration policies, live profiles, reviews, and ADR findings
0067-0070; batch 07 operation readiness tooling and report; causal
intelligence modules (evaluator, hysteresis, fuel, cross-lane, explanation)
with contracts and tests; stage 2 pipeline and phase 3a freeze regenerations
for the expanded cohort including evaluation anchors, research dataset, and
phase 3c analysis fixtures.

## 2026-09-05

- `d9354344d08e` — test: align Phase 3F tests with expanded cohort and owner-approved exemptions
  - Author: AdamEddahmouni (2026-09-05T00:13:15-04:00)
  - Rationale (commit-subject-and-body): Update stale test expectations for the expanded 29-symbol frozen cohort
(test_cohort BIYA, test_isolation allowlist), align the bootstrap-order test
with the warm-cycle contract, regenerate phase 3a/3b fixture metadata
(canonical generator output), and apply owner-approved exemptions for the
Finviz auto-refresh feature (curl_cffi/tools.provider_auth guards) and the
pre-existing squeeze_priority SUBPRIME vocabulary.
- `41f52bb07aa0` — test: align analysis/app expectations with expanded Phase 3F cohort
  - Author: AdamEddahmouni (2026-09-05T01:14:25-04:00)
  - Rationale (commit-subject-and-body): Update tests to the computed 29-symbol/43-case values (runner counts,
cohort memberships, BIYA's third row, sample-size LIMIted band, env-var
surfaces), regenerate the six stale phase-3d fixtures from the generator,
and move start_cloud's env/cwd side effects into the entry block so
importing it no longer leaks CLOUD_PROVIDER_MODE across the test session.
- `ae1e9e45ac67` — chore: allowlist reviewed code-terminology assignment matches in release audit — refs: `refs/heads/phase/3e-historical-acquisition`, `refs/remotes/origin/phase/3e-historical-acquisition`
  - Author: AdamEddahmouni (2026-09-05T03:01:22-04:00)
  - Rationale (commit-subject-and-body): The scanner's ACADEMIC_OR_PERSONAL signature matches "assignment" in
provider_session.py's mypy ignore code and evaluator.py's causal
state-machine docstring/notes. Review and allowlist these code-terminology
lines so the Public Release Audit gate passes on the Phase 3E/3F PR.
- `d520768f7f6f` — Merge pull request #1 from AdamEddahmouni/phase/3e-historical-acquisition
  - Author: AdamEddahmouni (2026-09-05T03:05:59-04:00)
  - Rationale (commit-subject-and-body): feat: complete Phase 3E/3F historical acquisition — Stage 2 outcomes, 29-symbol cohort expansion, calibration findings
- `8c255d2f21b6` — test: align frozen-cohort tests with expanded cohort and add demo fallback — refs: `refs/heads/fix/frozen-followups`, `refs/remotes/origin/fix/frozen-followups`
  - Author: AdamEddahmouni (2026-09-05T03:18:09-04:00)
  - Rationale (commit-subject-and-body): Retiring the stale local freeze surfaced five non-environmental failures
that were miscategorized as private-data gaps:
- `78b7467b7d5f` — Merge pull request #2 from AdamEddahmouni/fix/frozen-followups — refs: `refs/heads/main`, `refs/remotes/origin/main`
  - Author: AdamEddahmouni (2026-09-05T03:19:37-04:00)
  - Rationale (commit-subject-and-body): test: align frozen-cohort tests with expanded cohort and add demo research-summary fallback
