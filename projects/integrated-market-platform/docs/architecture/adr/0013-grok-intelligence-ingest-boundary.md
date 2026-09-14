# ADR-0013: Grok Intelligence Ingest Boundary

*Status: Accepted — Lane I (docs/contracts)*

## Context

IMP opportunity surfaces are driven by deterministic detection and normalized opportunity contracts. Product direction adds optional **async** Grok/agent enrichment (sources, contradictions, crowd context, hypothesis suggestions) without granting trading authority.

Prior art:

- ADR-0011 — analysis-only news AI with no execution fields
- `EvidenceV1` — specialist model evidence over snapshots (different lifecycle)

Risk if unspecified: UI blocks on agent latency; ingest path becomes a shadow execution API.

## Decision

1. Introduce `AgentEnrichmentEvidenceV1` and ingest operation guards under `intelligence/contracts/agent_ingest.py`.
2. Introduce `evaluate_ui_intelligence_render_gate()` under `intelligence/contracts/ingest_ui_timing.py` encoding **detection-first, never-wait-on-agent** semantics.
3. Document logical ingest API and Grok workspace templates in `GROK_INTELLIGENCE_INGEST_API.md`.

Do **not** (in this ADR scope):

- Wire HTTP handlers or persistence
- Add Paper/Live routes
- Store Grok credentials in-repo
- Grant Grok trading authority

## Consequences

### Positive

- Clear separation between deterministic UI truth and optional agent context
- Typed fail-closed guards for forbidden mutations
- Bot role matrix encourages Skills-first narrow jobs

### Negative / deferred

- Durable ingest store and UI merge logic are follow-on increments
- No empirical calibration of agent `confidence`
- Transport authentication not specified here (inherits platform operator auth)

## Safety

- Forbidden mutations enumerated and tested
- `MODE_AUTHORITY` unchanged
- Agent confidence is explicitly not execution authority

## References

- [GROK_INTELLIGENCE_INGEST_API.md](../GROK_INTELLIGENCE_INGEST_API.md)
- [ADR-0011](0011-news-ai-intelligence-boundary.md)
