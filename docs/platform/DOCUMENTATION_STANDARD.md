# IMP documentation standard

| Field | Value |
|---|---|
| Document ID | `IMP-DOCUMENTATION-STANDARD` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Prospective documentation classification, metadata, precedence, and drift control |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | Fragmented program-level documentation conventions |
| Superseded By | None |

This standard applies prospectively to new canonical and supporting program
documents. It does not retrofit, relabel, or rewrite historical artifacts.

## Independent dimensions

Truth class, document classification, implementation maturity, family
consolidation, and milestone disposition answer different questions. Never
collapse them into one `status` field or infer one from another.

### Truth class

| Value | Meaning |
|---|---|
| `HISTORICAL_TRUTH` | Accepted evidence about a named subject at a recorded cutoff. It remains authoritative for that cutoff, not automatically for current behavior. |
| `CURRENT_CANONICAL_TRUTH` | Current program-level explanation accepted through the canonical layer and constrained by controlling sources. |
| `APPROVED_FUTURE_DESIGN` | Accepted direction or requirement not represented as implemented; it grants no runtime or safety authority. |

A document containing multiple truth classes must label the relevant sections
or rows.

### Document classification

Use exactly one:

| Value | Meaning |
|---|---|
| `CANONICAL` | Current explanatory authority for a declared subject |
| `HISTORICAL` | Preserved evidence or account of a past cutoff |
| `ACTIVE_SUPPORTING` | Current supporting material without canonical subject ownership |
| `RUNBOOK` | Environment-scoped operational procedure constrained by executable gates |
| `REFERENCE` | Lookup material that does not independently govern behavior |
| `GENERATED` | Mechanically produced view or evidence; authority depends on its source and contract |
| `EXPERIMENTAL` | Proposal or research material without current canonical authority |
| `SUPERSEDED` | Displaced as current explanation but retained for historical value |

`STALE` is an audit finding, not an intended stable classification.
Supersession does not erase historical value.

### Implementation maturity

Use only for a named implementation or capability with supporting evidence:

```text
PLANNED
DESIGNED
IMPLEMENTED
VALIDATED
OPERATIONALLY_ACCEPTED
QUALIFIED
PRODUCTION_ELIGIBLE
DEPRECATED
```

These labels do not imply one another unless the controlling subsystem contract
says so. In particular, `IMPLEMENTED` does not mean `VALIDATED`, `QUALIFIED`, or
`PRODUCTION_ELIGIBLE`. Do not mechanically rewrite historical milestone
terminology.

### Family consolidation

Use:

```text
ABSENT
PARTIAL
CONSOLIDATED
```

`PARTIAL` means reusable foundations exist but the universal program authority
or consolidation primitives are incomplete. It does not mean half complete,
nearly ready, or production capable. Every `PARTIAL` entry must identify the
existing foundations, missing consolidation capability, and next owning
milestone.

### Milestone disposition

| Value | Meaning |
|---|---|
| `COMPLETE` | The named milestone's acceptance criteria passed with no unresolved milestone-execution limitation |
| `COMPLETE_WITH_LIMITATIONS` | The milestone passed but retains an explicit nonblocking limitation in its own execution or accepted output |
| `IN_PROGRESS` | Work or required evidence for the named track remains open |
| `BLOCKED` | An identified prerequisite prevents safe progress or acceptance |
| `AWAITING_EXTERNAL_EVIDENCE` | Completion depends on evidence that documentation or offline validation cannot manufacture |

Program limitations do not automatically turn an otherwise complete
documentation milestone into `COMPLETE_WITH_LIMITATIONS`.

## Canonical metadata

The ten `docs/platform/` documents use a compact table with these fields:

| Field | Rule |
|---|---|
| `Document ID` | Stable semantic navigation identifier, not executable authority |
| `Classification` | One document classification |
| `Primary Truth Class` | The document's primary truth class |
| `Canonical Subject` | Narrow subject the document owns |
| `Establishing Milestone` | Accepted milestone that established the document |
| `Version` | Starts at `1.0`; increment for accepted semantic change, not formatting or link repair |
| `Last Verified` | Date current source alignment was checked |
| `Supersedes` | Prior current explanatory source or `None` |
| `Superseded By` | Replacement or `None` |

`Owner Role` is not mandatory because IMP does not yet have a truthful governed
organization-wide ownership taxonomy. A `Maintainer` may be added only when a
current governed role or path owner supports it. Do not name a personal owner
or invent an organization. Do not put transient HEAD SHAs in canonical
metadata; acceptance evidence records Git and hash identity.

A redundant mandatory lifecycle-status field is prohibited. Classification
already supplies document lifecycle.

## Scoped precedence

There is no universal numeric precedence list:

1. Current executable sources control the behavior they implement.
2. Canonical `docs/platform/` documents control current explanation for their
   declared subject, constrained by executable truth and accepted evidence.
3. Immutable accepted milestone artifacts control what happened at their own
   cutoff.
4. Accepted designs and the roadmap control future direction only.
5. Runbooks control scoped procedures but may never bypass a gate or policy.

A current architecture cannot rewrite historical acceptance, and an immutable
historical artifact cannot override current architecture outside its cutoff.
Recency alone cannot override a frozen policy.

## Anti-shadowing and links

- Link to mutable executable values instead of copying them into prose,
  including thresholds, risk limits, provider states, quality enums, policy and
  model identities, capability matrices, test inventories, validation counts,
  and gate logic.
- Historical examples must name their source and cutoff.
- Local links should use repository-relative paths and resolve at acceptance.
- Generated current reference views are permitted only when an implemented tool
  owns their derivation and drift behavior.
- A broken critical link to a controlling source blocks acceptance.

Program documentation should use this concise disclaimer where its subject
could be confused with executable control:

> Program documentation is canonical for its defined explanatory subject. Where
> executable behavior is governed by a designated schema, policy, gate,
> registry, manifest, frozen policy, or implementation authority, that
> executable authority controls within its scope.

## Supersession and history

- Supersede by adding a new accepted source and reciprocal metadata; do not
  delete evidence needed to understand an earlier cutoff.
- Preserve BUILD, Phase, closure, and EVIDENCE artifacts and their hashes.
- Do not retrofit current vocabulary into frozen historical milestone records.
- `SUPERSEDED` ends current explanatory authority but does not erase historical
  value.
- A narrow navigation notice may point an active supporting document to its
  canonical successor without modernizing the preserved content.

## Material status updates

Update [Program Status](PROGRAM_STATUS.md) only when a material accepted state
changes: milestone acceptance/invalidation, family consolidation or maturity,
material authority ownership, a major limitation, or qualification/production
eligibility. Routine commits and ordinary validation-count changes do not
trigger an update.

Any material canonical change must update all affected documents in one
coherent change, validate local links and terminology, inspect the staged diff,
and regenerate the accepted-surface hash manifest when the milestone contract
includes one.

## Required future standard

The following are `REQUIRED FUTURE STANDARD`, not implemented REBASE-01
capabilities:

- automatic canonical metadata enforcement;
- generated current policy, capability, model, and validation reference views;
- automated canonical drift and contradiction checks;
- repository-wide documentation link validation in CI;
- documentation change/evidence workflow integrated with the future run ledger.

Until implemented, maintainers perform the corresponding review and validation
explicitly.
