# SOP: Production Bug Fix

## 1. Reproduce

Steps, mode, data fixture.

## 2. Characterize impact

Safety (Paper/Live)? Data integrity? Display only?

## 3. Safety triage

If execution/authority — stop and use [PAPER_EXECUTION_CHANGE.md](PAPER_EXECUTION_CHANGE.md).

## 4. Find invariant

What rule was violated?

## 5. Regression test

Minimal failing test first (ideal TDD).

## 6. Minimal fix

Smallest correct change.

## 7. Targeted validation

Affected vitest/unittest modules.

## 8. Full appropriate validation

Paper safety → full + build; UI → vitest + build; backend → validate changed/full.

## 9. Work log

Entry with root cause and test proof.

## 10. Completion / incident doc

If significant user-facing or safety incident.

Template: [templates/BUG_REPORT.md](../templates/BUG_REPORT.md).
