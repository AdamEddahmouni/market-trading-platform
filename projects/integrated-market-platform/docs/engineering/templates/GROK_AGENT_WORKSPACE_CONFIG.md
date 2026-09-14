# Grok Agent Workspace Configuration (template)

**Status:** Template only — copy values into the Grok workspace UI; do not commit secrets.

## Session

| Setting | Value |
|---------|-------|
| Timezone | `America/New_York` |
| Local computer execution | **Never** |
| Auto Review | **ON** |

## Plugins (read-first defaults)

| Plugin | Mode | Notes |
|--------|------|-------|
| GitHub | Read-first | Issues/PR context only |
| Notion | Read-first | Operator-approved pages |
| X | Read-first | CrowdWatch listening only |

**Disallowed plugin classes:** broker, payment, trading execution, credential vaults.

## Writes

| Class | Policy |
|-------|--------|
| Consequential writes (Notion/GitHub/X post) | **Ask first** |
| Ingest enrichment POST | Via IMP adapter only — not direct broker APIs |

## Bot roster (enable narrow bots, not one super-agent)

| Bot | Role | IMP `bot_role` |
|-----|------|----------------|
| Coordinator | Orchestrate work packages | `COORDINATOR` |
| Sentinel | Detect / verify claims | `SENTINEL` |
| CrowdWatch | Social listening | `CROWD_WATCH` |
| Research Scout | Discover sources | `RESEARCH_SCOUT` |
| Skeptic | Challenge narratives | `SKEPTIC` |
| Auditor | Verify provenance | `AUDITOR` |

## Authority reminder

Grok workers may only emit `AgentEnrichmentEvidenceV1` records per [GROK_INTELLIGENCE_INGEST_API.md](../../architecture/GROK_INTELLIGENCE_INGEST_API.md). They must **not** submit Paper/Live orders or mutate `MODE_AUTHORITY`.
