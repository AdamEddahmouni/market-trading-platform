# Wireframe 18 — Empty / Unavailable / Degraded States

## UNAVAILABLE (capability)
```
┌─ Order Flow ────────────────────────────────────────┐
│                                                      │
│              ⊘  LEVEL 2 UNAVAILABLE                  │
│                                                      │
│   Current dataset does not contain verified          │
│   depth information for this instrument.             │
│                                                      │
│              [Capability details]  [Explain]           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## PARTIAL (quality)
```
┌─ CVD  +184K  DER  ──────────────────────────────────┐
│  PARTIAL — Quote gap 10:31:14–10:31:22              │
│  Aggressor inference may be affected.               │
│  [Inspect quality]                                   │
└──────────────────────────────────────────────────────┘
```

## EMPTY (screener — intentional)
```
┌─ RESULTS ───────────────────────────────────────────┐
│  No instruments matched current criteria.            │
│  [Adjust filters]  [Save screen anyway]              │
└──────────────────────────────────────────────────────┘
```

## ABSTAIN (strategy — not failure)
```
┌─ Strategy state ────────────────────────────────────┐
│  ABSTAIN — evidence conflicting                      │
│  5 groups support LONG · 1 SHORT · 1 ambiguous      │
│  [Show alignment]                                    │
└──────────────────────────────────────────────────────┘
```

## LOADING
```
┌─ Skeleton bars ─────────────────────────────────────┐
│  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  Loading bars…                                       │
└──────────────────────────────────────────────────────┘
```

Never: blank chart area with no message.
