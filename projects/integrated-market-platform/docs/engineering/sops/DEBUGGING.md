# SOP: Debugging

## 1. Reproduce

Minimal steps; note mode (Demo/Paper/Live) and authority state.

## 2. Isolate frontend / backend

Network tab vs API direct (`curl`/browser). Which layer wrong?

## 3. Inspect API payload

Compare response to Zod schema and backend projection.

## 4. Inspect React Query cache

DevTools — query key, stale data, shared cache (canary).

## 5. Inspect authority state

`ModeEnvironmentBar`, `evaluateModeContext`, backend `/context`.

## 6. Inspect domain projection

Python unittest or log projection output for ledger record.

## 7. Inspect logs / events

`.local/platform-backend.log`, execution trace, ledger events.

## 8. Reduce failing test

Minimal vitest/unittest case.

## 9. Add regression test

Required for real bugs.

## 10. Document invariant

Update architecture doc if new rule discovered.

## Common IMP failure classes

| Class | Check |
|-------|-------|
| Query-key collision | Same key, different `queryFn`/shape |
| Stale lazy-route test | Import path after code split |
| Authority mismatch | Mode vs backend context |
| Schema drift | Zod vs API vs JSON schema |
| Fixture mismatch | Admitted fixture shape |
| Time unit mismatch | ns vs ms in formatters |
| Route-state loss | Handoff missing on refresh |
| Partial historical records | Optional field handling |

See [RUNBOOK.md](../../operations/RUNBOOK.md).
