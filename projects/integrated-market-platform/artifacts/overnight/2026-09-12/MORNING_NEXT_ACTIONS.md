# Morning next actions

## P0 — Unblock ES campaign evidence

1. Run Moomoo OpenD futures entitlement probe; update capability matrix (foreground lane).
2. Re-run campaign-readiness evaluator; do not freeze manifest until OWNER-OD packet resolved.

## P1 — Integrate overnight docs

1. Cherry-pick or merge `overnight/imp-parallel-2026-09-12` deliverables into foreground after review.
2. Reconcile Wave A artifact presence on main vs foreground branch.

## P2 — Product engineering

1. Opportunity summary projection (isolated worktree) per product plan.
2. DISCOVER: wire `capability_states` in observability panel.

## P3 — Research / PIT

1. PIT operator path index (`pit_inventory` CLI spec).
2. MATLAB handoff manifest schema (no runtime bridge yet).

---

## Implementation-ready `/goal` prompts

### Goal 1 — Moomoo ES capability verification

```
/goal Verify and record Moomoo US_FUTURES_QUOTE for ES on work/ftep-v1-activation: run owner-approved OpenD probe, append fresh rows to capability matrix per MARKET_DATA_CAPABILITY_CONTRACT.md, update es-news-provider-stack-selection only if evidence changes. No manifest freeze. Validate: provider readiness CLI + affected tests.
```

### Goal 2 — Opportunity read model

```
/goal On isolated branch from work/ftep-v1-activation: add backend OpportunitySummary projection conforming to OPPORTUNITY_CONTRACT.md (read-only fields from fusion snapshot); expose GET /opportunities/summary for DISCOVER; React Query hook + unit tests. Do not modify projections.py conflict regions without merging foreground first.
```

### Goal 3 — Capability UI convergence

```
/goal Consume context capability_states in DiscoverObservability.tsx with schema-safe degradation; align copy with operator readiness statuses; affected UI tests + validate changed.
```

### Goal 4 — PIT operator inventory

```
/goal Add tools/research/pit_inventory.py (stdlib) listing ADR-PIT-001 / pit_gate / FTEP temporal contract paths as JSON; document in docs/engineering/PIT_OPERATOR_GUIDE.md; unittest for stable output hash.
```

### Goal 5 — Foreground/main reconciliation

```
/goal Merge or rebase work/ftep-v1-activation onto origin/main after PR #19 policy check; re-run reconciliation-gate synthesis; validate full on merged tree; resolve wave-a-findings drift.
```
