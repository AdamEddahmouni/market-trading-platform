# Agent router

IMP lives at `projects/integrated-market-platform/` in this monorepo
(`AdamEddahmouni/market-trading-platform`). Do not edit the leftover nested
`integrated-market-platform/` clone.

Start here:

- [projects/integrated-market-platform/AGENTS.md](projects/integrated-market-platform/AGENTS.md)
- [Agent Operating System](projects/integrated-market-platform/docs/engineering/AGENT_OPERATING_SYSTEM.md)
- [Program Status](projects/integrated-market-platform/docs/platform/PROGRAM_STATUS.md)
- [IMP Scope, FTEP, and Paper-Validation Doctrine](projects/integrated-market-platform/docs/architecture/IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md)

IMP is the whole platform. FTEP is the protocol. V1-001 ES and V1-002 US equity are campaigns.

Always-on rules: `.cursor/rules/imp-*.mdc`.

- **Model:** start Composer; escalate to Grok 4.6 High only for reasoning
  difficulty; never Fast variants.
- **Agents:** one by default; parallelize only independent work; one primary owner;
  never mutate the same worktree concurrently.
