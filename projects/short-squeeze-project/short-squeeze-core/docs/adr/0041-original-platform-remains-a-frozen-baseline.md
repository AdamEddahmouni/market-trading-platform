# ADR 0041: The original platform remains a frozen baseline

## Status

Accepted (Phase 2V).

## Context

Phase 2V must describe why the original screener surfaced a candidate. The archived
repositories are the only record of that behaviour, and they are also forensic evidence
in an ongoing reconstruction.

Two temptations present themselves. The first is to run the archived platform to see what
it produces — which would produce today's answer from today's data, not the historical
one. The second is to fix obvious defects while documenting them, which would destroy the
evidence of what was actually running.

A third, subtler problem emerged during the work. The archived `ScreenerProject` checkout
(`6dbefd1a`) includes a Prime/Subprime redesign committed at 15:39:27 on 2026-07-17 —
**2h53m after** the review meeting in which the candidate was observed. Reconstructing
"the original rules" from the checked-out tree would attribute `classify_tier()` to the
event. Verified by `git grep classify_tier b016d92f`, that function did not exist at
detection.

## Decision

The original platform is a **frozen historical baseline**. Phase 2V describes it and
never modifies, re-runs, reformats, or corrects it. No archived repository is reset,
checked out, cleaned, committed, amended, merged, or has its ACLs changed.

Rules are reconstructed **read-only from the commit that was current at detection**, not
from the archived working tree. For the BIYA case that is `b016d92f`
(2026-07-17T11:56:43 America/New_York), the last commit preceding the meeting. Every
`OriginalRuleDefinition` records its `source_commit`, and a test asserts all of them cite
that commit.

Where implementation contradicts documentation, both are recorded and the contradiction
is the finding. `OriginalRuleDefinition` carries `documented_but_not_implemented` and
`implemented_but_not_documented` for exactly this.

## Consequences

Rule reconstruction requires `git show`/`git grep` against a specific commit rather than
reading files from disk — slightly more work, and the only way to describe the right
code.

Descriptive fidelity outranks tidiness: `original_rules.py` names `core/squeeze_score.py`
and "Prime / Subprime" because those are the platform's real identifiers. The Phase 1
strategy-term guard was adjusted to accommodate this, compensated by a stricter
AST-based identifier scan covering every module.

Anyone re-running this analysis against the archived HEAD will get different rules. That
is not a reproducibility failure; it is why `source_commit` is recorded.
