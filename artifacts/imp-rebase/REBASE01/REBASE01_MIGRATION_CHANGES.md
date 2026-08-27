# IMP-REBASE-01 migration changes

No file was moved or deleted. Historical content was preserved in place.
`Original dirty overlap` refers to the source worktree captured before the clean
implementation worktree was created.

| Path | Old role | New role | Classification | Why changed | Historical content preserved? | Original dirty overlap? |
|---|---|---|---|---|---:|---:|
| `README.md` | Mixed onboarding, status, history, and roadmap | Concise repository entry point linked to canonical current truth while retaining onboarding/local-run content | `ACTIVE_SUPPORTING` | Remove stale “repository closure is next” framing and state current safety limits | Yes | Yes — `REQUIRES_LATER_RECONCILIATION` |
| `AGENTS.md` | Validation and environment instructions | Existing instructions plus canonical truth, history, EVIDENCE, authority, dirty-tree, validation, and staged-diff rules | `CANONICAL` repository instruction | Make future changes respect REBASE-01 governance | Yes | No |
| `docs/roadmap/REVISION_3_ROADMAP.md` | Revision 3 navigational projection | Historical/supporting roadmap with pointer to current master roadmap | `HISTORICAL` / `ACTIVE_SUPPORTING` | Prevent historical projections from becoming current post-core authority | Yes | Yes — `REQUIRES_LATER_RECONCILIATION` |
| `docs/platform/README.md` | Absent | `NEW_CANONICAL`: documentation front door | `CANONICAL` | Establish current navigation and truth-class distinction | N/A | N/A |
| `docs/platform/MASTER_ARCHITECTURE.md` | Absent | `NEW_CANONICAL`: whole-program architecture | `CANONICAL` | Distinguish implemented, partial, and approved future architecture | N/A | N/A |
| `docs/platform/PROGRAM_STATUS.md` | Absent | `NEW_CANONICAL`: maintainable current status | `CANONICAL` | Repair the highest-impact status drift | N/A | N/A |
| `docs/platform/MASTER_ROADMAP.md` | Absent | `NEW_CANONICAL`: post-core dependency roadmap | `CANONICAL` | Preserve EVIDENCE independence and define program handoffs | N/A | N/A |
| `docs/platform/CANONICAL_TRUTH_MAP.md` | Absent | `NEW_CANONICAL`: topic-to-authority map | `CANONICAL` | Route prose to executable/frozen authority | N/A | N/A |
| `docs/platform/SYSTEM_BOUNDARIES.md` | Absent | `NEW_CANONICAL`: responsibility map | `CANONICAL` | Explain subsystem ownership and attachment points | N/A | N/A |
| `docs/platform/AUTHORITY_MODEL.md` | Absent | `NEW_CANONICAL`: authority and safety flow | `CANONICAL` | Make information/quality/prediction/evidence/risk/human/execution/release/broker distinctions explicit | N/A | N/A |
| `docs/platform/DATA_AND_EPISTEMIC_MODEL.md` | Absent | `NEW_CANONICAL`: evidence and inference method | `CANONICAL` | Formalize evidence classes without runtime schemas | N/A | N/A |
| `docs/platform/DOCUMENTATION_STANDARD.md` | Absent | `NEW_CANONICAL`: lifecycle, precedence, and anti-drift standard | `CANONICAL` | Prevent future authority drift | N/A | N/A |
| `docs/platform/GLOSSARY.md` | Absent | `NEW_CANONICAL`: controlled program terminology | `CANONICAL` | Resolve ambiguous status and authority language | N/A | N/A |
| `artifacts/imp-rebase/REBASE01/README.md` | Absent | New acceptance-package index | `HISTORICAL` after acceptance | Navigate accepted evidence without copying canonical docs | N/A | N/A |
| `artifacts/imp-rebase/REBASE01/REBASE01_ACCEPTANCE_REPORT.md` | Absent | New acceptance report | `HISTORICAL` after acceptance | Record exact state, validation, preservation, and disposition | N/A | N/A |
| `artifacts/imp-rebase/REBASE01/REBASE01_DOCUMENT_MAP.md` | Absent | New accepted-scope document map | `HISTORICAL` after acceptance | Bind canonical subjects to milestone scope | N/A | N/A |
| `artifacts/imp-rebase/REBASE01/REBASE01_MIGRATION_CHANGES.md` | Absent | New migration ledger | `HISTORICAL` after acceptance | Record every role change and dirty overlap | N/A | N/A |
| `artifacts/imp-rebase/REBASE01/REBASE01_KNOWN_LIMITATIONS.md` | Absent | New bounded limitation register | `HISTORICAL` after acceptance | Preserve genuine unresolved limits | N/A | N/A |
| `artifacts/imp-rebase/REBASE01/REBASE01_FILE_HASHES.json` | Absent | New complete-surface SHA-256 manifest | `GENERATED` / `HISTORICAL` | Prove accepted documentation bytes | N/A | N/A |
