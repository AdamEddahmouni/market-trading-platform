# Mode Authority Specification

**Status:** Authoritative safety model.  
**Applies to:** All Demo, Paper, and Live surfaces — frontend and backend.

> Frontend gating improves UX. **Backend authority and env gates are the only safety boundaries.**

## Demo

| Aspect | Rule |
|--------|------|
| Purpose | Exploration and replay on admitted fixtures |
| Reads | Fixture replay APIs, observational components (read-only) |
| Mutations | **Prohibited** — no order submit, no operator housekeeping mutations |
| Backend context | `data_mode` ∈ {`FIXTURE_REPLAY`, `HISTORICAL_CAPTURE`}; `execution_mode=NONE`, `execution_authority=BLOCKED` |
| Frontend | `evaluateModeContext("DEMO", ctx)` must be `compatible` for mode banner; pages are read-only by design |

## Paper

| Aspect | Rule |
|--------|------|
| Purpose | Internal simulated execution only |
| Authority | `execution_mode=INTERNAL_SIMULATION` AND `execution_authority=PAPER_ONLY` |
| Env gates | `IMP_PAPER_EXECUTION=1` (and related gates per [CONFIGURATION.md](../engineering/CONFIGURATION.md)) |
| Mutations | Preview, submit, cancel — **only** when `canUsePaperActions("PAPER", paperActionsPermitted, context)` |
| Fail-closed | Preview stale → revalidation required; authority loss → ticket hidden, observational UI remains |
| Preview | Accepted preview does **not** bypass revalidation when draft/market changes |
| Submit | Workspace is canonical decision boundary; Paper Command cannot submit directly |

### Paper authority loss behavior

- Portfolio history, trace, cockpit observability: **remain readable**
- Order ticket / submit controls: **hidden or disabled** with explicit warning
- Never degrade to Demo or Live execution paths

## Live

| Aspect | Rule |
|--------|------|
| Purpose | Broker-observed read-only monitoring |
| Reads | Live observational APIs, canary snapshot/reconciliation |
| Mutations | **Prohibited** — no order submission, no paper submit |
| Backend context | `data_mode` ∈ {`LIVE_OBSERVATIONAL`, `BROKER_DELAYED`}; `execution_mode=NONE`, `execution_authority=BLOCKED` |
| Canary | Operational visibility only — not execution authority |

**LIVE-001 production execution is blocked** in this repository.

## Frontend responsibilities

- Mode-specific page composition (`Mode*Route` → Demo/Paper/Live pages)
- `evaluateModeContext` / `canUsePaperActions` for control visibility
- Clear copy when authority unavailable
- Never invent authority or bypass preview/revalidation UX

## Backend responsibilities

- Enforce operating context on every mutating endpoint
- Reject paper mutations without authority (fail closed)
- Persist immutable audit trail (intents, events, snapshots)
- Env gates at process startup

## What frontend gating cannot do

- Prevent a malicious client from calling APIs directly
- Substitute for backend validation
- Authorize broker or live execution

## Broker paper (P4-4A/4B)

Separate sandbox adapter — requires explicit env gates (`IMP_TRADIER_PAPER`, `IMP_BROKER_PAPER_EXECUTION`, token, sandbox endpoint). Never mixed with internal Paper authority without explicit composition rules.

## Implementation references

- `ui/src/components/mode-session/modeAuthority.ts`
- `src/market_platform_foundation/platform/` operating context
- [PAPER_EXECUTION_CHANGE.md](../engineering/sops/PAPER_EXECUTION_CHANGE.md)
- [SECURITY.md](../engineering/SECURITY.md)
