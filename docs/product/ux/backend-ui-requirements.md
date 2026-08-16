# Backend UI Contract Requirements

**Status:** `PROPOSED` — requirements for future API design; **not** implementation authorization

These contracts must be designed after canonical internal contracts (Phase 2+) and exposed via stable read-only research APIs (Revision 3 Section 17) before production UI.

## Priority 1 — Foundation (required for any UI)

### AsOfContext
```typescript
interface AsOfContext {
  mode: 'LIVE' | 'REPLAY' | 'SIMULATION' | 'PAPER';
  as_of_time: string; // ISO8601
  replay_session_id?: string;
  timezone: string; // e.g. America/New_York
}
```

### ModeState
Server-authoritative mode; client cannot silently override.

### CapabilityState
```typescript
interface CapabilityState {
  capability_id: string; // e.g. depth.L2, options.chain, whale.disclosure
  state: 'AVAILABLE' | 'UNSUPPORTED' | 'NOT_ENTITLED' | 'NOT_COLLECTED' | 'LOADING' | 'DEGRADED';
  reason?: string;
  explanation_ref?: string;
}
```

### QualitySummary
```typescript
interface QualitySummary {
  state: 'GOOD' | 'PARTIAL' | 'DEGRADED' | 'STALE' | 'UNAVAILABLE' | 'CORRECTED' | 'QUARANTINED' | 'DISCONNECTED';
  detail?: string;
  affected_range?: { start: string; end: string };
  affected_symbols?: string[];
}
```

## Priority 2 — Explainability

### ExplanationReference
See [explainability-contract.md](explainability-contract.md).

### EvidenceReference
```typescript
interface EvidenceReference {
  evidence_id: string;
  family: string; // whale family 1-8
  epistemic_class: string;
  direction?: string;
  strength?: string;
  as_of: string;
  quality: QualitySummary;
}
```

### ProvenanceReference
Chain node: `{ type, id, label, child_refs?, external_uri? }`

### StateTransition
```typescript
interface StateTransition {
  from_state: string;
  to_state: string;
  at: string;
  changed_criteria: CriterionChange[];
  unchanged_criteria: string[];
  explanation_ref: string;
}
```

## Priority 3 — Attention & discovery

### AttentionItem
```typescript
interface AttentionItem {
  attention_id: string;
  priority_rank: number;
  reasons: AttentionReason[];
  instrument_id?: string;
  headline: string;
  transition?: StateTransition;
  explanation_ref: string;
}
```

### AttentionReason
```typescript
interface AttentionReason {
  code: string; // machine-readable
  label: string; // human-readable
  weight?: number; // optional, not shown as score by default
}
```

### ScreenMatch
Criteria pass/fail with `why_matched` breakdown.

## Priority 4 — Replay & time

### ReplaySession
Session id, instrument, date, cursor, event index, speed.

### AvailabilityBoundary
For PIT: what was knowable at `as_of_time` per data class.

## Priority 5 — Models & research

### ModelExplanation
Model id, version, artifact hash, target, horizon, uncertainty, feature refs.

### ForecastInterface
Aligns with Phase 5R `FCAST-001` — UI projects, does not redefine.

## Priority 6 — AI (later track)

### AssistantContext
Instrument, mode, as_of, selected evidence IDs, replay state — server-assembled snapshot (OpenBB `get_workspace_snapshot` pattern).

### CitationBlock
`{ explanation_ref, evidence_ref, quote?, unavailable_reason? }`

**Hard rule:** AI responses without resolvable citation or explicit uncertainty flag are rejected by client policy.

## Priority 7 — Portfolio (future)

Position, fill, P&L, risk evaluation — separate from strategy state.

## API principles

1. DTOs are projections of canonical contracts — not sources of truth
2. Every response includes `as_of_context` and applicable `capability_states`
3. Quality travels with every derived/inferred payload
4. Pagination + stable sort keys for feeds
5. WebSocket/SSE for live updates with sequence numbers for gap detection

## Current gap analysis

| UI need | Backend today (Phase 5) |
|---|---|
| Live quotes | Not authorized |
| DOM/depth | Not admitted |
| Institutional data | Interfaces exist; fail-closed unavailable |
| CVD/OFI | Not on admitted fixture (bar-only features) |
| Replay UI | Phase 2 contracts exist; no UI API |
| Explanation refs | Not implemented |
| Attention ranking | Not implemented |

UI prototypes must use **labeled mock boundaries** until contracts exist.

## AI interaction model (summary)

- Persistent sidecar, not primary nav
- Auto-context from workspace snapshot
- Actions: Ask, Explain, Compare, What changed?, Show conflicting evidence, What would invalidate?, Show source
- Never: place order, override risk, mutate positions

See [information-architecture.md](information-architecture.md).
