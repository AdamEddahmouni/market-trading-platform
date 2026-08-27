# IMP glossary

| Field | Value |
|---|---|
| Document ID | `IMP-GLOSSARY` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Controlled program terminology |
| Owner Role | IMP program architecture owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | Uncontrolled whole-program usage of these terms |
| Superseded By | None |

These definitions control program-level prose. They do not rename existing code
or alter the scope of executable contracts.

## Operational and analytical terms

| Term | Controlled meaning |
|---|---|
| live | Connected to a current external environment or source. The term must be qualified as observational, paper, or execution; it does not itself grant authority. |
| observational | Read-only receipt or inspection of real external data with no order-submission authority. |
| paper | Governed non-production execution using simulation or an explicitly sandboxed broker environment. |
| simulation | Synthetic or modeled execution or market behavior under declared assumptions. |
| replay | Deterministic processing of previously captured, cutoff-bounded inputs. |
| signal | A computed directional or descriptive output; not an opportunity, prediction, or authorization by itself. |
| candidate | An item eligible for evaluation by the next declared gate; not accepted merely by selection. |
| opportunity | A governed, economically evaluated action candidate produced by the opportunity boundary; not order authority. |
| prediction | An immutable, cutoff-bound forecast record whose outcome is settled separately. |
| campaign | A bounded, identified sequence of observations or runs governed by a frozen scope or policy. |
| session | A bounded runtime or authorization interval with its own identity and lifecycle. |
| qualification | Evidence-based disposition against an explicitly scoped policy; not trading authorization. |
| provider | An external or internal source/transport implementation. Availability does not imply entitlement, admission, quality, or execution capability. |
| capability | A bounded, evidence-backed statement of supported behavior and state. |
| quality | A multidimensional assessment of data or evidence fitness; not a universal score or authority grant. |
| authority | The explicit right of a named gate, policy, role, or implementation to decide within a defined scope. |
| risk authority | The authority to accept, reject, size, or constrain risk within executable policy. It does not submit orders. |
| execution authority | The narrow authority to advance a confirmed order through the execution state machine after all required gates. |
| release approval | A software candidate’s governed release disposition. It is not live-session or order authorization. |

## Truth classes

- `HISTORICAL_TRUTH`: authoritative for an accepted historical subject and
  cutoff.
- `CURRENT_CANONICAL_TRUTH`: authoritative current program interpretation.
- `APPROVED_FUTURE_DESIGN`: accepted direction, not current implementation.

## Lifecycle classes

`CANONICAL`, `HISTORICAL`, `ACTIVE_SUPPORTING`, `RUNBOOK`, `REFERENCE`,
`GENERATED`, `EXPERIMENTAL`, and `SUPERSEDED` describe a document's lifecycle.
`STALE` is an audit finding rather than a target lifecycle.

## Maturity states

`PLANNED`, `DESIGNED`, `IMPLEMENTED`, `VALIDATED`, `OPERATIONALLY_ACCEPTED`,
`QUALIFIED`, `PRODUCTION_ELIGIBLE`, and `DEPRECATED` describe implementation
maturity. `WITH_LIMITATIONS`, `BLOCKED`, and `AWAITING_EXTERNAL_EVIDENCE` are
qualifiers. `PARTIAL` is a program-family status meaning reusable foundations
exist but the universal abstraction named by the family does not.
