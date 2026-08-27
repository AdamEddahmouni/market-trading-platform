# IMP-REBASE-01 acceptance report

Final milestone status: `IMP_REBASE_01_COMPLETE_WITH_LIMITATIONS`

## Repository state and isolation

| Field | Recorded value |
|---|---|
| Original repository | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Original branch | `cloud/build-35-release-governance-operational-acceptance` |
| Original HEAD | `eb36f7ee9b25344f61977fbffedfb1dad8e4e0cc` |
| Original upstream | `origin/cloud/build-35-release-governance-operational-acceptance` |
| Original ahead/behind | `4/0` |
| Remote branch HEAD | `020b64377393c3af1e085b9906e74552a2ca08b9` |
| Remote symbolic HEAD | `refs/heads/main` at `c2c0a719255117fe6f28b03cdf18734a2178ab9e` |
| Implementation worktree | `C:/Users/adame/Documents/Codex/2026-08-27/files-pasted-by-the-user-imp/work/imp-rebase-01` |
| Implementation branch | `docs/imp-rebase-01` |
| Implementation base | `eb36f7ee9b25344f61977fbffedfb1dad8e4e0cc` |
| Final commit | The commit containing this report; its exact SHA is recorded by Git and the external execution report because a commit cannot embed its own content-derived identity |
| Implementation upstream | None; target comparison remains the original upstream branch |
| Push | None |
| Original dirty state | Captured before isolation and preserved without reset, clean, stash, move, staging, or merge |

The worktree was created clean under the repository's ignored `.worktrees/`
convention and then moved with `git worktree move` to the task's writable
`work/` directory. Branch, base commit, and isolation did not change. This path
adjustment was required by the execution sandbox and is the only worktree-path
deviation from the preferred repository-local placement.

The original worktree contained these unrelated changes:

```text
 M README.md
 M artifacts/supervised-production-pilot/BUILD33_CONTROL_PLANE_MANIFEST.json
 M artifacts/supervised-production-pilot/BUILD33_FILE_HASHES.json
 M artifacts/supervised-production-pilot/BUILD33_PILOT_REPORT.json
 M artifacts/supervised-production-pilot/BUILD33_PILOT_RUN_MANIFEST.json
 M artifacts/supervised-production-pilot/BUILD33_PILOT_SNAPSHOT.json
 M docs/roadmap/REVISION_3_ROADMAP.md
 M evidence/ui1/assistant-audit/conversations.json
 M evidence/ui1/assistant-audit/messages.json
?? .cursor/settings.json
?? .superpowers/
?? docs/superpowers/governance/2026-08-14-foundation-revision-3-effectivity-notice.md
?? reports/build26-changed.json
?? reports/postbuild35-closure-changed.json
?? reports/postbuild35-closure-domain-core.json
?? reports/postbuild35-closure-full.json
```

## Recovered lineage

```text
020b643  EVIDENCE-01B runtime operationalization
  -> 9ee9681  mode-launcher design
  -> 37326d6  mode-launcher implementation plan
  -> c318fef  IMP-REBASE-00 repository truth audit
  -> eb36f7e  IMP-REBASE-01 approved design / planning-complete base
  -> REBASE-01 implementation commit
```

The two mode-launcher commits remain frontend design/planning records. They do
not change REBASE-01 program architecture, status, or execution authority.

## Accepted outputs

The following canonical documents were created:

- `docs/platform/README.md`
- `docs/platform/MASTER_ARCHITECTURE.md`
- `docs/platform/PROGRAM_STATUS.md`
- `docs/platform/MASTER_ROADMAP.md`
- `docs/platform/CANONICAL_TRUTH_MAP.md`
- `docs/platform/SYSTEM_BOUNDARIES.md`
- `docs/platform/AUTHORITY_MODEL.md`
- `docs/platform/DATA_AND_EPISTEMIC_MODEL.md`
- `docs/platform/DOCUMENTATION_STANDARD.md`
- `docs/platform/GLOSSARY.md`

Entry points modified:

- `README.md` now routes current program interpretation to `docs/platform/`,
  reports post-core status, and preserves onboarding/local-run material.
- `AGENTS.md` retains validation/environment instructions and adds canonical
  truth, history, EVIDENCE, safety, dirty-tree, and diff rules.
- `docs/roadmap/REVISION_3_ROADMAP.md` retains its historical projection and
  adds only a current-roadmap notice.

The complete accepted path-by-path disposition is in
[`REBASE01_MIGRATION_CHANGES.md`](REBASE01_MIGRATION_CHANGES.md).

## Original dirty-entry-point overlap

| Path | REBASE-01 modified? | Original worktree dirty? | Later reconciliation required? |
|---|---:|---:|---:|
| `README.md` | Yes | Yes | `REQUIRES_LATER_RECONCILIATION` |
| `AGENTS.md` | Yes | No | No |
| `docs/roadmap/REVISION_3_ROADMAP.md` | Yes | Yes | `REQUIRES_LATER_RECONCILIATION` |

The preserved local README and roadmap edits were not copied into the clean
milestone. Reconciliation is separate from this acceptance.

## Program status established

| Area | State |
|---|---|
| Core architecture | Historical `COMPLETE_WITH_LIMITATIONS` |
| Repository closure | `COMPLETE` |
| Evidence | `IN_PROGRESS`; EVIDENCE-01C next and not accepted |
| Program re-baseline | `IMP-REBASE-01` |
| Operating Fabric | `PARTIAL` |
| Cross-Asset | `PARTIAL` |
| Real-Time Opportunity Fabric | `PARTIAL` |
| Narrative/Motive | `PARTIAL` |
| AI/Agents | `PARTIAL` |
| Autonomous execution | `DISABLED` |
| Production live broker transport | `ABSENT` |

## Historical preservation proof

Changed paths were mechanically compared with the protected path families
below. Patterns are repository-relative.

| Protected family | Path pattern | Changed paths found | Result |
|---|---|---:|---:|
| BUILD acceptance/history | `artifacts/{system-acceptance,paper-execution-qualification,live-execution-safety,live-canary,supervised-live-operations,operator-control-plane,operational-reliability,supervised-production-pilot,deployment-qualification,full-system-acceptance}/**`; `artifacts/cloud-handoff/CLOUD_POST_BUILD*` | 0 | `PASS` |
| Phase historical artifacts | `manifests/phase*/**`; `evidence/phase*/**` | 0 | `PASS` |
| EVIDENCE historical artifacts | `artifacts/forward-qualification/**`; `docs/engineering/EVIDENCE_01*` | 0 | `PASS` |
| Prediction-ledger evidence | `docs/engineering/PREDICTION_LEDGER_OUTCOME_SETTLEMENT_V1.md`; `src/market_platform_foundation/intelligence/contracts/prediction_ledger.py` | 0 | `PASS` |
| Settlement evidence | `src/market_platform_foundation/intelligence/outcomes/**` | 0 | `PASS` |
| Release acceptance evidence | `artifacts/full-system-acceptance/**`; `src/market_platform_foundation/intelligence/live_canary/release_governance/**` | 0 | `PASS` |
| Repository closure evidence | `artifacts/repository-closure/**`; closure audit and validation reports | 0 | `PASS` |
| CLEANUP evidence | Repository-closure/CLEANUP accepted history | 0 | `PASS` |

Result: `0 changed protected historical paths — PASS`.

No path under `src/`, `tests/`, `tools/`, `ui/`, `pipelines/`, `manifests/`, or
`.github/` changed. Runtime, policy, validation, EVIDENCE, risk, execution,
settlement, prediction, and release semantics are unchanged.

## Documentation and epistemic governance

REBASE-01 establishes three truth classes, eight lifecycle classes, eight
maturity states plus three qualifiers, canonical metadata, executable-authority
precedence, the historical-cutoff nuance, same-level conflict handling, and the
anti-drift rule. The epistemic model separates observed/reported fact, stated
rationale, inferred behavior/motive, narrative, hypothesis, and model output;
it preserves support, contradiction, alternatives, falsifiers, source
incentives, timing, revisions, and methodological limits.

## Roadmap and REBASE-02 handoff

EVIDENCE continues independently from EVIDENCE-01B to EVIDENCE-01C and later
milestones. The program-platform track proceeds from REBASE-01 to REBASE-02,
then to OF-01/OF-02 while RT-01 and XA-01 can proceed dependency-aware in
parallel. OF-03 follows ledger/adapters; AI-01 depends on OF-01; AI-02 depends
on OF-03 and AI-01.

REBASE-02 must define universal run attribution, artifact identity,
code/data/model/config provenance, retry/attempt preservation, structured
logging and metrics, trace/correlation identity, evaluation classes, benchmark
reproducibility, and documentation validation. It does not implement the full
Operating Fabric.

## Validation record

| Sequence | Command/check | Result |
|---:|---|---|
| Baseline | `tools/validate.py changed` using the repository CPython 3.11 venv | `PASS`: 0 tests, 0 skipped, 0 failures, 0 errors |
| Draft checkpoint | Same changed selector after canonical document drafting | `PASS`: 0 tests, 0 skipped, 0 failures, 0 errors |
| A | Relative Markdown links and repository paths across the accepted surface | `PASS`: zero broken links |
| B | Parse `REBASE01_FILE_HASHES.json` | `PASS` |
| C | Recompute every SHA-256 manifest entry | `PASS`: zero mismatches |
| D | Canonical consistency matrix and status/authority/anti-shadowing scans | `PASS`: zero contradictions or blocking overclaims |
| E | Protected-history changed-path comparison | `PASS`: zero protected changes |
| F | `git diff --check` and staged equivalent | `PASS` |
| G | `tools/validate.py changed --json <external-work-path>` after explicit staging | `PASS`: 21 tests, 0 skipped, 0 failures, 0 errors; `full_suite_required=false` |
| H | Full validation | `NOT_RUN`: changed-path policy did not require it |

No provider/live suite was applicable. There was no failed repository
validation attempt and therefore no retry disposition. The pre-existing
REBASE-00 inventory-manifest line-ending behavior is recorded in known
limitations: normalized LF bytes differ, while CRLF reconstruction reproduces
the recorded byte count and hash exactly.

## Git disposition and material deviations

One coherent local commit is used with subject
`docs(architecture): establish canonical IMP program architecture`. Nothing is
pushed, merged, force-pushed, or applied to `main`.

The acceptance report cannot embed the exact SHA of the commit that contains
itself because the SHA is derived from these bytes. Git history and the final
execution report provide that exact identity. The hash manifest excludes only
itself, as required, and covers this report.

## Known limitations and judgment

The bounded limitations are recorded in
[`REBASE01_KNOWN_LIMITATIONS.md`](REBASE01_KNOWN_LIMITATIONS.md). They concern
future evidence, live transport, run attribution, tracing/benchmarks, AI
attribution, Operating Fabric, Cross-Asset, and historical line-ending
materialization. They do not make the canonical documentation layer
untrustworthy.

Final status: `IMP_REBASE_01_COMPLETE_WITH_LIMITATIONS`
