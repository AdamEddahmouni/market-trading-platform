# IMP-REBASE-01 acceptance report

## Implementation identity

| Field | Value |
|---|---|
| Milestone | `IMP-REBASE-01` |
| Implementation base | `44800d2e210e58ff5759c44cc343dd4578c0b821` |
| Base subject | `docs(architecture): finalize IMP-REBASE-01 implementation spec` |
| Implementation worktree | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform/.worktrees/imp-rebase-01-canonical` |
| Implementation branch | `docs/imp-rebase-01-canonical` |
| Intended commit subject | `docs(architecture): establish canonical IMP program architecture` |
| Original worktree | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Original branch / HEAD | `cloud/build-35-release-governance-operational-acceptance` / `44800d2e210e58ff5759c44cc343dd4578c0b821` |
| Premature protected worktree / HEAD | `C:/Users/adame/Documents/Codex/2026-08-27/files-pasted-by-the-user-imp/work/imp-rebase-01` / `6d365031d36a4d1b2f14a80d2690c28cff9c9713` |
| Push / merge | Not performed |

The implementation lineage is:

```text
020b64377393c3af1e085b9906e74552a2ca08b9
-> 9ee96817a1ae4d6ec514804dfb830766145095b2
-> 37326d682e48d74285b47dfdf870e71e6433af70
-> c318fef48e994dbaf2a2dfd7e00198bd4f79f949
-> eb36f7ee9b25344f61977fbffedfb1dad8e4e0cc
-> 44800d2e210e58ff5759c44cc343dd4578c0b821
-> REBASE-01 implementation commit
```

The final commit SHA is intentionally recorded in the external execution
report, not in this hash-bound report.

## Specification verification

| Item | Value |
|---|---|
| Path | `docs/superpowers/specs/2026-08-27-imp-rebase-01-canonical-program-architecture-implementation-spec.md` |
| Expected SHA-256 | `c0a31dd8f6b1956068cf5e62536046eeb02977c4b138b38f3ed45fdc3d59c710` |
| Observed SHA-256 | `c0a31dd8f6b1956068cf5e62536046eeb02977c4b138b38f3ed45fdc3d59c710` |
| Result | `PASS` |

## Canonical document map

| Path | Canonical subject |
|---|---|
| `docs/platform/README.md` | Documentation front door, reading order, and truth-class routing |
| `docs/platform/MASTER_ARCHITECTURE.md` | Whole-program composition and architectural relationships |
| `docs/platform/PROGRAM_STATUS.md` | Mutable current program state and material limitations |
| `docs/platform/MASTER_ROADMAP.md` | Post-core milestone ownership and dependency graph |
| `docs/platform/CANONICAL_TRUTH_MAP.md` | Topic-to-authority routing and conflict disposition |
| `docs/platform/SYSTEM_BOUNDARIES.md` | Subsystem responsibilities, dependency direction, and authority stops |
| `docs/platform/AUTHORITY_MODEL.md` | Information, permission, authorization, execution, and reconciliation relationships |
| `docs/platform/DATA_AND_EPISTEMIC_MODEL.md` | Evidence, claim, inference, narrative, and hypothesis method |
| `docs/platform/DOCUMENTATION_STANDARD.md` | Prospective classification, metadata, precedence, and drift control |
| `docs/platform/GLOSSARY.md` | Controlled program terminology |

The subjects are deliberately non-overlapping. Program documentation remains
explanatory; executable sources continue to control behavior within their
scopes.

## Migration and touched-path analysis

| Path | Change | Original dirty overlap | Disposition |
|---|---|---|---|
| `README.md` | Replace stale whole-program status/next-step block with compact canonical routing; preserve setup and developer entry points | Yes | `REQUIRES_LATER_RECONCILIATION` |
| `AGENTS.md` | Add repository recovery, scoped precedence, historical/EVIDENCE protection, authority, isolation, and staged-review rules | No | `NO_OVERLAP` |
| `docs/roadmap/REVISION_3_ROADMAP.md` | Add one separated navigation notice to the current master roadmap | Yes | `REQUIRES_LATER_RECONCILIATION` |
| `docs/platform/README.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/MASTER_ARCHITECTURE.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/PROGRAM_STATUS.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/MASTER_ROADMAP.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/CANONICAL_TRUTH_MAP.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/SYSTEM_BOUNDARIES.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/AUTHORITY_MODEL.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/DATA_AND_EPISTEMIC_MODEL.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/DOCUMENTATION_STANDARD.md` | Create | No; new path | `NO_OVERLAP` |
| `docs/platform/GLOSSARY.md` | Create | No; new path | `NO_OVERLAP` |
| `artifacts/imp-rebase/REBASE01/README.md` | Create acceptance package index | No; new path | `NO_OVERLAP` |
| `artifacts/imp-rebase/REBASE01/REBASE01_ACCEPTANCE_REPORT.md` | Create combined document map, migration, consistency, and validation record | No; new path | `NO_OVERLAP` |
| `artifacts/imp-rebase/REBASE01/REBASE01_KNOWN_LIMITATIONS.md` | Create separated limitations record | No; new path | `NO_OVERLAP` |
| `artifacts/imp-rebase/REBASE01/REBASE01_FILE_HASHES.json` | Create full accepted-surface manifest | No; new path | `NO_OVERLAP` |

The original checkout snapshot contained 9 tracked modifications and 16
untracked paths. Neither the original dirty `README.md` nor roadmap content was
copied into this implementation. Their later integration requires deliberate
reconciliation.

No `CONTRIBUTING.md`, root `ROADMAP.md`, ADR, separate document-map artifact,
separate migration artifact, permanent validator, or runtime file was created.

## Canonical consistency matrix

| Topic | Accepted statement | Source | Result |
|---|---|---|---|
| BUILD01-35 | BUILD35 historical disposition is `FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS` for its recorded candidate; it does not prove current production readiness | `artifacts/full-system-acceptance/BUILD35_FULL_ACCEPTANCE_REPORT.json` | `CONSISTENT` |
| Repository closure | Historical closure completed for its recorded source and is not the current roadmap endpoint | `docs/engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md` | `CONSISTENT` |
| EVIDENCE-01 / 01A | Policy/assessment machinery and campaign framework are complete within their scopes | EVIDENCE engineering documents and frozen artifacts | `CONSISTENT` |
| EVIDENCE-01B / 01C | 01B is implemented operationalization; 01C is next and lacks accepted operational disposition | `docs/engineering/EVIDENCE_01B_REAL_PROVIDER_RUNTIME_OPERATIONALIZATION.md` and REBASE-00 | `CONSISTENT` |
| Autonomous execution | Disabled; no information or automation output grants order authority | Live-safety, authorization, confirmation, and authority sources | `CONSISTENT` |
| Production broker transport | Accepted production live broker transport is absent; mock/paper abstractions and reconciliation exist | `live_canary/runner.py`, `submission.py`, and broker inventory | `CONSISTENT` |
| Operating Fabric | `PARTIAL` with reusable operations; universal run/operation/artifact authority is missing | REBASE-00 `04` and `06` | `CONSISTENT` |
| Real-Time Opportunity Fabric | `PARTIAL`; existing callback/state/feature/routing foundations lack accepted end-to-end trace/benchmark | REBASE-00 `05` and `06` | `CONSISTENT` |
| Cross-Asset | `PARTIAL`; shared identity/relationship/source extension remains `IMP-XA-01` work | REBASE-00 `05` and `06` | `CONSISTENT` |
| Narrative/Motive | `PARTIAL`; uncertain motive/thesis method and admitted runtime are missing | REBASE-00 `05` and `06` | `CONSISTENT` |
| AI/Agents | `PARTIAL`; read-only assistant foundations exist, universal attribution/evaluation/workflow governance does not | REBASE-00 `05` and `06` | `CONSISTENT` |
| Truth classes | `HISTORICAL_TRUTH`, `CURRENT_CANONICAL_TRUTH`, `APPROVED_FUTURE_DESIGN` remain distinct | `DOCUMENTATION_STANDARD.md` | `CONSISTENT` |
| Document classes | Eight reviewed classes are used; `STALE` remains an audit finding | `DOCUMENTATION_STANDARD.md` | `CONSISTENT` |
| Implementation maturity | `PLANNED` through `DEPRECATED` are capability terms, not document or milestone state | `DOCUMENTATION_STANDARD.md` | `CONSISTENT` |
| Family consolidation | `ABSENT`, `PARTIAL`, and `CONSOLIDATED` are architecture assessments; `PARTIAL` is not a percentage | `PROGRAM_STATUS.md` and `DOCUMENTATION_STANDARD.md` | `CONSISTENT` |
| Milestone disposition | `COMPLETE`, `COMPLETE_WITH_LIMITATIONS`, `IN_PROGRESS`, `BLOCKED`, and `AWAITING_EXTERNAL_EVIDENCE` apply to named milestones/tracks | `DOCUMENTATION_STANDARD.md` | `CONSISTENT` |
| Roadmap | Canonical milestone names, hard/per-operation/later-integration edges, parallel-safe branches, and EVIDENCE independence match the final spec | `MASTER_ROADMAP.md` | `CONSISTENT` |
| Authority | Behavioral, explanatory, historical, and future-design authorities are subject/time scoped; prohibited shortcuts remain prohibited | `CANONICAL_TRUTH_MAP.md` and `AUTHORITY_MODEL.md` | `CONSISTENT` |

## Protected-history verification

Protected surfaces were derived mechanically from all 262
`KEEP_IMMUTABLE_AND_INDEX` rows in
`artifacts/imp-rebase/REBASE00/REBASE00_DOCUMENTATION_INVENTORY.json` and
augmented by the final specification's explicit code/policy families:

- accepted BUILD, Phase, and EVIDENCE reports, manifests, hashes, validation
  evidence, policies, known-limitations registers, and release candidates;
- `artifacts/imp-rebase/REBASE00/**`;
- repository-closure evidence and classification;
- EVIDENCE policy, campaign, observation, session, checkpoint, source,
  configuration, settlement, and exclusion semantics;
- prediction, settlement, qualification, provider admission, risk, execution,
  live-safety, authorization, confirmation, reconciliation, deployment, and
  release-governance authorities.

The Revision 3 roadmap is excluded only for its approved navigation notice,
consistent with REBASE-00's `STALE` / `REQUIRES_RECONCILIATION` finding.

| Check | Result |
|---|---|
| Protected inventory surfaces examined | 262 |
| Explicit protected code/policy families examined | All families listed above |
| Prohibited changed paths | 0 |
| Result | `PASS` |

## Validation attempt history

| Command or check | Attempt | Exit | Result | Tests / pass / skip / fail / error | `full_suite_required` |
|---|---:|---:|---|---|---|
| Specification SHA-256 | 1 | 0 | `PASS` | Not applicable | Not applicable |
| `tools/validate.py changed --explain` on clean base | 1 | 0 | `PASS` | 0 / 0 / 0 / 0 / 0 | `false` |
| `tools/validate.py changed --explain` after canonical/entry-point draft | 1 | 0 | `PASS` | 0 / 0 / 0 / 0 / 0 | `false` |
| Temporary local Markdown link/path audit before acceptance report existed | 1 | 1 | `TEST_FAILURE`: one expected target, `REBASE01_ACCEPTANCE_REPORT.md`, had not yet been created | 1 broken link | Not applicable |
| Temporary local Markdown link/path and fragment audit after acceptance report creation but before hash manifest generation | 2 | 1 | `TEST_FAILURE`: the package index's intended `REBASE01_FILE_HASHES.json` target did not yet exist | 1 broken link | Not applicable |
| Temporary local Markdown link/path and fragment audit on frozen surface | 3 | 0 | `PASS` | 0 broken links/fragments | Not applicable |
| Allowed-path and exact-surface audit | 1 | 0 | `PASS` | 17 intended changed paths; 0 outside contract | Not applicable |
| Canonical consistency and contradiction/overclaim/mutable-value audit | 1 | 0 | `PASS` | 18 matrix topics; 0 material contradictions | Not applicable |
| REBASE-00-derived protected-history audit | 1 | 0 | `PASS` | 262 inventory surfaces plus explicit families; 0 prohibited changes | Not applicable |
| `git diff --check 44800d2e210e58ff5759c44cc343dd4578c0b821 --` | 1 | 0 | `PASS` | 0 whitespace errors | Not applicable |
| JSON parse and accepted-surface hash-schema/coverage verification | 1 | 0 | `PASS` | 17 entries; 0 mismatches | Not applicable |
| Final `tools/validate.py changed --explain` | 1 | 0 | `PASS` | 21 / 21 / 0 / 0 / 0 | `false` |
| Full validation | Not run | Not applicable | `NOT_REQUIRED` | Documentation/acceptance selection only | `false` |
| Complete staged-diff inspection and `git diff --cached --check` | 1 | 0 | `PASS` | 17 intended paths; 0 whitespace errors | Not applicable |

The repository validator selected the documentation suite: 21 documentation
checks and no runtime tests. This is reported as documentation validation, not
as a full regression pass. No live-provider validation was warranted or run.

## Hash verification

`REBASE01_FILE_HASHES.json` covers all ten canonical documents, the three
modified entry points, the final implementation specification, and the three
other acceptance files. It is sorted by repository-relative POSIX path and
excludes itself.

| Measure | Result |
|---|---:|
| Entries | 17 |
| Missing or extra paths | 0 |
| Duplicate paths | 0 |
| Byte-length mismatches | 0 |
| SHA-256 mismatches | 0 |
| Accepted surface fully covered | Yes |

## Git disposition

- One documentation-only implementation commit is created with parent
  `44800d2e210e58ff5759c44cc343dd4578c0b821`.
- The exact final commit SHA is reported externally after commit.
- The original dirty checkout is not reset, cleaned, stashed, staged, or
  overwritten.
- The premature `docs/imp-rebase-01` worktree/commit is not reused, copied,
  cherry-picked, or modified.
- No push, merge, force-push, or `main` update is performed.

## Acceptance criteria

All final-spec criteria pass:

1. Ten separate canonical documents exist and satisfy their contracts.
2. Current implementation, historical truth, and future design are distinct.
3. Truth, classification, maturity, consolidation, and disposition are not
   conflated.
4. Every `PARTIAL` family identifies foundations, missing capability, and next
   owner.
5. Mutable executable subjects are linked, not shadowed.
6. Live-readiness layers and broker-transport state are precise.
7. Composition, boundaries, and authority are non-duplicative and consistent.
8. The epistemic model uses `REPORTED_CLAIM`, competing hypotheses, and separate
   narrative factual-support/market-impact dimensions.
9. Roadmap dependency types and safe parallelism are explicit.
10. EVIDENCE-01C remains semantically independent.
11. Root navigation preserves onboarding and avoids duplicate program truth.
12. No ADR or principal authorization is manufactured.
13. Protected historical changes equal zero.
14. Original dirty state is preserved and both overlaps are recorded.
15. The four-file package contains the required merged evidence.
16. Local links, JSON, hashes, consistency, whitespace, and repository
    validation pass.
17. The implementation commit contains only allowed paths and descends directly
    from the review-complete base.

## Limitations and disposition

[Known limitations](REBASE01_KNOWN_LIMITATIONS.md) separates current program
limitations from REBASE-01 execution limitations. REBASE-01 has no remaining
acceptance-output limitation.

Final milestone state:

```text
IMP_REBASE_01_COMPLETE
```
