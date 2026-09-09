# IMP Reconciliation Program — Audit Workspace

Canonical persistent workspace for the Integrated Market Platform (IMP)
reconciliation, audit, and recovery program (controller v2, 2026-09-06).

**Program state:** WS07 COMPLETE (2026-09-07) — see [00-program-state.md](00-program-state.md).
**Reconciliation status:** COMPLETE. **Remediation:** G0 (baseline), G1 (canonical multi-asset identity), and G2 (canonical multi-asset portfolio, BL-0105) executed 2026-09-07 — evidence in [15-validation-evidence.md](15-validation-evidence.md) (G0 + G1 + G2 sections); **next:** G3 (trading/risk correctness) per [19-goal-increment-plan.md](19-goal-increment-plan.md).

---

## Mission (from the controller)

Determine with evidence: original intended scope, authorized later additions,
legitimate vs mistaken donor material, what IMP actually implements today,
which implementations are correct/incomplete/broken/obsolete, which historical
completion claims remain valid, what legitimate functionality is still missing,
the canonical architecture, and the dependency-aware sequence that brings IMP
to a structurally complete state.

Current authorized scope is defined as:

```text
original requirements
+ legitimate later additions
+ legitimate professor/user-directed integrations
- known mistaken donor material
- accidental implementation drift
```

## Authority hierarchy (Tier A → E)

| Tier | Class | Meaning |
|---|---|---|
| A | ORIGINAL_PROJECT_SOURCE | Original project-goal screenshots/materials from Adam (pending supply) |
| B | AUTHORIZED_LATER_SCOPE | Work later requested/approved by Adam or Prof. Kaamran Raahemifar |
| C | AUTHORIZED_DONOR_SOURCE | External projects intentionally supplied by the professor/their authors |
| D | IMPLEMENTATION_EVIDENCE | Current code/tests/docs/git — establishes what was built, not what was authorized |
| E | UNVERIFIED_ADDITION | No Tier A–C evidence; investigate before any disposition |

Chronological lateness does NOT make a feature invalid. Removal is normally
restricted to `KNOWN_MISTAKEN_DONOR`, `ACCIDENTAL_SCOPE_DRIFT`, and
`OBSOLETE_SUPERSEDED_SCOPE` — each still requires per-capability provenance
and dependency analysis before any action.

## Evidence discipline

Every significant conclusion carries evidence (exact file path, symbol, test,
commit, branch, README, professor/user requirement, donor repo, runtime
behavior, or command result) and a confidence label:

`CONFIRMED` · `HIGH_CONFIDENCE` · `MODERATE_CONFIDENCE` · `LOW_CONFIDENCE` · `UNKNOWN`

Assumptions are never presented as facts. Unresolved matters are recorded in
[14-open-decisions.md](14-open-decisions.md) rather than blocking the audit.

## File manifest

| File | Status | Populated by |
|---|---|---|
| [00-program-state.md](00-program-state.md) | CURRENT | bootstrap + every workstream |
| [01-source-registry.md](01-source-registry.md) | COMPLETE (WS01) | bootstrap, WS01 |
| [02-scope-authority-ledger.md](02-scope-authority-ledger.md) | COMPLETE (WS02) | WS02 |
| [02a-original-scope-image-index.md](02a-original-scope-image-index.md) | COMPLETE (WS02) — Tier A image index | WS02 |
| [03-donor-integration-map.md](03-donor-integration-map.md) | COMPLETE (WS03) | WS03 |
| [04-current-state.md](04-current-state.md) | COMPLETE (WS04) — current-state verdict, runtime baseline, capability table, provider reality, fixture-vs-live, missing scope, KEEP_AS_IS, completion scores | WS04 |
| [05-capability-matrix.md](05-capability-matrix.md) | COMPLETE (WS04) — authoritative combined REQUIREMENT+PROVENANCE+IMPLEMENTATION+VERIFICATION+STATUS matrix | WS02–WS04 |
| [06-architecture-correctness.md](06-architecture-correctness.md) | **COMPLETE (WS05)** — architecture/safety/trading-correctness/multi-asset audit; ARCH-001..011, SAFE-001..004, TRD-001..009, MA-001..006; blockers AB-001..008; ADR-C-001..010; KEEP_AS_IS register | WS05 |
| [07-product-engineering.md](07-product-engineering.md) | **COMPLETE (WS06)** — full product/engineering audit: product-surface matrix, route/component/state/schema audits, API inventory + dead candidates, testing map + safety coverage, `validate changed` proof, dev-system friction, docs truth, deps, repo topology, performance (MEASURED), deletion/consolidation registers, KEEP_AS_IS, WS07 inputs | WS06 |
| [08-false-completion-register.md](08-false-completion-register.md) | COMPLETE (WS04) — 16 evidence-backed claim reconciliations | WS04 |
| [09-scope-drift.md](09-scope-drift.md) | WS02 classifications complete; WS03 traces origin | WS02–WS03 |
| [10-technical-debt.md](10-technical-debt.md) | WS03 provenance debt (TD-P1..P7) + WS04 current-state debt (TD-W1..W11) + WS05 architecture debt (TD-A1..A15) + **WS06 product/engineering debt (TD-UE1..OP1)** | WS03–WS06 |
| [11-target-architecture.md](11-target-architecture.md) | **FINAL (WS07)** — WS05 preliminary reconciled with WS06 evidence; §13 finalization + scope boundary + quality gate | WS05 + WS07 |
| [12-master-backlog.md](12-master-backlog.md) | **COMPLETE (WS07)** — 68 full-schema items owned by root causes, in waves | WS07 |
| [13-recovery-roadmap.md](13-recovery-roadmap.md) | **COMPLETE (WS07)** — dependency graph + 10 waves with closure gates | WS07 |
| [14-open-decisions.md](14-open-decisions.md) | CURRENT (WS07 final pass — engineering decisions resolved; product decisions explicit) | bootstrap + every workstream |
| [15-validation-evidence.md](15-validation-evidence.md) | CURRENT (WS07 planning-only evidence appended; WS04 baseline stands) | every workstream |
| [16-root-cause-register.md](16-root-cause-register.md) | **COMPLETE (WS07)** — 20 root causes collapsing all WS01–WS06 findings | WS07 |
| [17-deletion-consolidation-plan.md](17-deletion-consolidation-plan.md) | **COMPLETE (WS07)** — final dispositions for DEL-01..07 + CON-01..10 + repo cleanup + docs supersession | WS07 |
| [18-completion-scorecard.md](18-completion-scorecard.md) | **COMPLETE (WS07)** — 7 metrics, weighted model, structural/production criteria, demo path | WS07 |
| [19-goal-increment-plan.md](19-goal-increment-plan.md) | **COMPLETE (WS07)** — 11 ordered increments + exact copy/paste next /goal (G0) | WS07 |

## Relationship to existing governance (reused, not duplicated)

This workspace is the reconciliation PROGRAM record. It intentionally does not
re-write IMP's own authoritative docs, which remain canonical for behavior:

- IMP docs authority map: `projects/integrated-market-platform/docs/README.md`
- IMP safety model: `docs/architecture/MODE_AUTHORITY.md` (Demo/Paper/Live)
- IMP current program truth: `docs/platform/PROGRAM_STATUS.md`,
  `MASTER_ARCHITECTURE.md`, `MASTER_ROADMAP.md`, `CANONICAL_TRUTH_MAP.md`
- IMP donor index (authoritative donor boundary rules):
  `docs/research/donors/README.md` + `DONOR_REUSE_MATRIX.md` +
  `superpowers/governance/2026-08-14-donor-code-permissions.json`
- IMP existing per-lane audits to reuse at WS04/WS05: `docs/research/`
  `FUTURES_CURRENT_STATE_AUDIT.md`, `OPTIONS_CURRENT_STATE_AUDIT.md`,
  `MARKET_CONTEXT_CURRENT_STATE_AUDIT.md`, capability-gap analyses,
  discrepancy registers, `CROSS_LANE_BOUNDARY_MATRIX.md`
- Committed working plan derived from the professor brief:
  `docs/reviews/2026-09-04-hardening-task-plan.md`
- Parent workspace notes index: `PROJECT_NOTES_INDEX.md`; monorepo workflow:
  `docs/MONOREPO_WORKFLOW.md`; source mapping: `workspace-manifest.json`

## Workstream sequence

WS01 Source & Provenance → WS02 Scope Authority → WS03 Donor-to-IMP
Integration → WS04 Current State & Completion → WS05 Architecture/Correctness/
Safety → WS06 Product & Engineering → **WS07 Master Reconciliation (COMPLETE)** → WS08+
Remediation (one coherent increment at a time; exact next increment = G0 in
19-goal-increment-plan.md; see the remediation prompt template in the
controller).

## Execution discipline

1. Read canonical audit state first; do not rediscover settled facts.
1a. Tier A image evidence lives in `project-scope-images/` (indexed in 02a); treat later-supplied proposal screenshots as superseding the ORG-001/002 reconstruction.
2. Use bounded searches; persist findings before context grows large.
3. Separate evidence from interpretation; prefer structured tables.
4. Do not refactor during discovery; do not remediate during bootstrap.
5. Never infer authorization solely from code presence.
6. Preserve ALL later Adam/professor-directed work unless a newer explicit
   instruction supersedes it.
7. Treat `Claude Code News/` as a primary AUTHORIZED_FUTURE_DONOR reference;
   treat `DS-440-CAPSTONE-GridIQ-main/` material as the known mistaken donor;
   do not confuse Lucas Bichara (Future) with Lucas Heller (mistaken).