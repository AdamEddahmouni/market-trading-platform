# Wireframe 08 — Short Squeeze Workspace

```
┌─ AVTX ─ Short Squeeze ─────────────────────────────┐
│ STATE: WATCH ─────── last Δ frozen snapshot       │
│                                                    │
│ Changed / unchanged criteria + transition log      │
│ (frozen_snapshot: INITIAL → WATCH)                 │
│                                                    │
│ Ignition evidence                                  │
│ ┌─────────────┬─────────────┬─────────────┐       │
│ │ SI / Float  │ Borrow      │ Options     │       │
│ │ FROZEN      │ UNAVAIL     │ UNAVAIL     │       │
│ └─────────────┴─────────────┴─────────────┘       │
│                                                    │
│ [Explain state] [History] [Open Inspector]         │
│ Open Story — UNAVAILABLE (narrative module deferred) │
└────────────────────────────────────────────────────┘
```

- **Explain state** opens the explanation drawer for `explain:squeeze:{symbol}`.
- **History** opens Inspector TIMELINE via `inspect:squeeze:timeline:{symbol}`.
- **Open Inspector** opens the evidence inspector summary tab.
- **Open Story** is not implemented in this phase; narrative/story module remains unauthorized.

No opaque "Squeeze Score 87".
