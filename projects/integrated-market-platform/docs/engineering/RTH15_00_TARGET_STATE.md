# RTH15-00 target state

**Status:** Authoritative target for this reconciliation increment.  
**Base:** `origin/main` `d06f1f4c1154913c561fc3c7c42aa46f452a2a15`  
**Branch:** `reconcile/rth15-00`

This is the intended end state of RTH15-00, not a claim that every item is
already landed. Empirical / prospective records remain frozen.

## Discovery / runtime

Keep the reconstructed launcher, Vite `/discover` bypass, and UI-api 8766
health path already on `main` (`#206`, `#211`). Do not merge the stale
`diagnosis/launcher-routing-20260915` snapshot.

## Opportunity Engine

Keep the live observational ranked-read path from `#205` / `#208`. Omit
leak-shaped public names (`instrument_key`, `decision_support.authority`) from
HTTP ranked cards so the fail-closed leak audit no longer 500s honest
observational payloads. Cards keep `instrument_id`. Fixture/replay attention
stays quarantined off the LIVE book.

## Provider / data flow

No new provider adapters. Finviz remains overlay/news ingress, never hop L1.
OpenD remains hop L1 when healthy.

## Evidence / provenance

Land the optional evidence capture-context sidecar (`#196` unique work).
Sidecar metadata must not mutate Finviz / Item 7 / Item 9 receipt contracts
or upgrade evidence class.

## FTEP / paper

Do not rewrite Sep 15 observations, including
`PROSPECTIVE_NO_POST_SIGNAL_BAR`. Software may improve future observations only.

## Heartbeat / scheduler

No `STAGE_2_APPLIED_AWAITING_NATURAL_CYCLE` artifact, branch, or scheduled
task is present in the repository or Windows task list. Do not retune
schedulers. Item 7 natural settlement (`#222`) stays isolated.

## Benchmark tooling

No integrable Intelligence Benchmark Protocol v1 branch was found. Do not
execute a benchmark in this increment.

## UI

Recover small, still-true operator UX on current contracts:

- duplicate Lab→Research nav link
- orphaned `ImpTopOpportunityCards`
- Discover investigation-only vs opportunity-contract boundary
- dead horizontal NavShell CSS
- unused UI test TypeScript

Keep `ui/operator-redesign-v2` implementation isolated. Recover the redesign plan
docs only.

## Documentation

Archive Sep 15 diagnosis/review notes as historical truth. Do not treat them
as current architecture.

## Deliberately deferred

- `item7/natural-settlement` (`KEEP_ISOLATED_PENDING_EVIDENCE`)
- UI redesign foundation/shell implementation
- Intelligence Benchmark Protocol execution
- Phase 2–5 merged-lane leftovers
- Open UX drafts after selective recovery (`#123`–`#128`, `#201`)
