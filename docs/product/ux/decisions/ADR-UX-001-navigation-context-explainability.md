# ADR-UX-001 — Navigation, Context, and Explainability Model

**Status:** `ACCEPTED` — principal review completed 2026-08-16  
**Created:** 2026-08-15  
**ADR ID:** `ADR-UX-001`  
**Logical ID:** `product.adr_ux_001`

## Context

The Integrated Market Platform will combine many analytical capabilities. Without a binding UX architecture, the interface risks becoming a wall of unrelated dashboards, opaque scores, and ambiguous time context. Revision 3 prohibits universal buy/whale scores and requires capability honesty. UX Foundation V0 planning and prototype validation have produced a coherent model that must be recorded before implementation authorization.

## Decision

Adopt the following **binding UX architecture** for all future UI work:

### 1. Information architecture — five domains

| Domain | Purpose | Default entry |
|---|---|---|
| **NOW** | Attention-prioritized command center | App homepage |
| **EXPLORE** | Discovery, screeners, universe search | Secondary |
| **WORKSPACE** | Instrument cockpit + specialized modules | Per-symbol deep work |
| **RESEARCH** | Datasets, replay, models (gated) | Authorized track only |
| **PORTFOLIO** | Positions, risk, execution (gated) | Future authorization |

Cross-cutting surfaces: global context bar, command palette (`Ctrl/Cmd+K`), Evidence Inspector, contextual AI sidecar (no authority).

### 2. Global context bar — mandatory on every route

Every screen displays:

- **Mode:** LIVE | REPLAY | SIMULATION | PAPER
- **AS OF:** observation/replay timestamp
- **Scope:** active symbol(s) when applicable
- **Quality:** aggregate or per-scope quality when not GOOD

Mode applies workspace-wide. Per-panel out-of-band data requires explicit label.

### 3. Explainability interaction model

Two complementary surfaces:

| Surface | Depth | Default use |
|---|---|---|
| **Explanation drawer** | Levels 1–2 (meaning, why, alignment summary) | `Explain`, `E` shortcut |
| **Evidence Inspector** | Levels 3–6 (evidence, derivation, provenance, raw) | `Inspect`, `I` shortcut |

**Why here?** (attention-specific): compact reason codes only — not full explanation drawer.

Inspector default tab: **SUMMARY**. User preference for EVIDENCE deferred.

### 4. Epistemic classification — mandatory on nontrivial values

All displayed metrics carry visible epistemic class: OBSERVED, DERIVED, INFERRED, MODEL, STRATEGY, RISK, EXECUTION.

Direction semantics (↑ LONG, ↓ SHORT) are separate from quality semantics (GOOD, PARTIAL, DEGRADED).

### 5. Capability honesty

Unsupported capabilities render as **UNAVAILABLE** with explanation — never hidden silently, never faked with placeholder data.

### 6. Attention architecture

- Separate attention ranking from trade/squeeze/model scores
- Show structured reason codes; no opaque rank score by default
- Cursor-paginated feed; Tier-1 system/risk events pinned

### 7. Institutional flow naming

Use **"Institutional Flow"** — never "Whale Score" or universal institutional buy indicator.

## Alternatives considered

| Option | Rejected because |
|---|---|
| Module-first nav (Order Flow, Options, … as top level) | Encourages siloed dashboards; scales poorly |
| Per-panel live/replay mode | Causes time-context leakage |
| Single inspector-only explainability | Too deep for attention-layer scanning |
| Universal confidence % | Implies false precision; conflicts with Revision 3 |
| Hide unavailable modules | Violates capability honesty |

## Consequences

### Positive

- Consistent mental model as capabilities grow
- Explainability path defined before backend APIs
- Aligns with Revision 3, Swim With the Whales, ADR-WHALE-001
- Prototype V0 validates core flows A–B

### Negative

- Five-domain nav requires discipline; feature teams may resist nesting
- Context bar consumes vertical space
- Inspector + drawer = two patterns to implement
- RESEARCH/PORTFOLIO gating may confuse users until authorized

## Non-authorization statement

Acceptance of this ADR records the **UX architecture decision only**. It does **not** authorize:

- Production frontend implementation
- Chart framework selection (UX-015)
- Live data connections, broker controls, or provider adapters
- Modification of governed evidence or canonical contracts

Implementation requires a separate authorization track with backend UX contract delivery per [backend-ui-requirements.md](../backend-ui-requirements.md).

## Conformance evidence

| Artifact | Path |
|---|---|
| UX Foundation V0 | `docs/product/ux/README.md` |
| Design review | `docs/product/ux/design-review-2026-08-15.md` |
| Prototype V0 | `docs/product/ux/prototype/v0/` |
| Walkthrough log | `docs/product/ux/walkthrough-friction-log-2026-08-15.md` |
| Revision 3 | `docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md` |
| Submission package | `docs/product/ux/decisions/ADR-UX-001-submission-package.md` |
| Machine-readable ADR | `docs/product/ux/decisions/2026-08-15-adr-ux-001-navigation-context-explainability.json` |

## References

- UX-001 through UX-023 in [decisions/README.md](README.md)
- [explainability-contract.md](../explainability-contract.md)
- [context-and-time.md](../context-and-time.md)
- [navigation.md](../navigation.md)
