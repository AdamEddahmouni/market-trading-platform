# ADR 0010: Preserve Compatible Evidence Conflicts

## Context

Different sources or duplicate records can disagree on the same semantic value. Averaging or selecting a winner would discard evidence and embed an unsupported source policy.

## Decision

Compare only explicitly compatible semantic fields. Preserve value conflicts, duplicate/source inconsistencies, and temporal differences as deterministic conflict objects while leaving observations unchanged. Keep source priority metadata informational.

## Consequences

Bundles expose disagreement without resolving it. Finviz short-float percentage, IBKR borrow fee, and IBKR availability are complementary and never treated as competing values.

## Rejected alternatives

Averaging hides provenance and may create a value no provider published. Silent winner selection embeds trust policy. Comparing fields solely because their numeric units resemble each other conflates financial meanings.
