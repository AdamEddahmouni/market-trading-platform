# Parallel lane results and reconciliation matrix

**Program:** IMP Overnight 2026-09-12

## Per-lane summary

| Lane | Topic | Primary output | Class |
|---|---|---|---|
| A | ES market-data alternatives | [ES research doc](../../docs/research/ES_MARKET_DATA_ALTERNATIVES_2026-09-12.md) | RESEARCH_COMPLETE |
| B | Provider universe audit | [PROVIDER_UNIVERSE_MASTER_AUDIT.json](./PROVIDER_UNIVERSE_MASTER_AUDIT.json) | RESEARCH_COMPLETE |
| C | Opportunity engine | [Product plan](../../docs/product/OPPORTUNITY_ENGINE_CURRENT_STATE_AND_IMPLEMENTATION_PLAN.md) | SPEC_READY_FOR_LATER |
| D | UI/UX audit | [UI_UX_AUDIT.md](./UI_UX_AUDIT.md) | RESEARCH_COMPLETE |
| E | Research intelligence gaps | [RESEARCH_INTELLIGENCE_GAPS.md](./RESEARCH_INTELLIGENCE_GAPS.md) | RESEARCH_COMPLETE |
| F | PIT / data quality | [PIT_DATA_QUALITY_AUDIT.md](./PIT_DATA_QUALITY_AUDIT.md) | SPEC_READY_FOR_LATER |
| G | MATLAB integration | [MATLAB_INTEGRATION_PLAN.md](./MATLAB_INTEGRATION_PLAN.md) | DEFER (DEFER-MATLAB-BRIDGE) |
| H | Paper execution calibration | [EXECUTION_CALIBRATION_ROADMAP.md](./EXECUTION_CALIBRATION_ROADMAP.md) | SPEC_READY_FOR_LATER |
| I | Test / reliability / perf | [RELIABILITY_PERFORMANCE_AUDIT.md](./RELIABILITY_PERFORMANCE_AUDIT.md) | RESEARCH_COMPLETE |
| J | Docs / governance | [GOVERNANCE_AUDIT.md](./GOVERNANCE_AUDIT.md) | RESEARCH_COMPLETE |
| K | Security / secrets | [SECURITY_AUDIT.md](./SECURITY_AUDIT.md) | RESEARCH_COMPLETE |
| L | Technical debt map | [TECHNICAL_DEBT_MAP.md](./TECHNICAL_DEBT_MAP.md) | RESEARCH_COMPLETE |

## Master reconciliation matrix

| Finding | Lane | Value | Risk | Foreground overlap? | External dep? | Implement overnight? |
|---|---|---|---|---|---|---|
| ES futures entitlement unverified | A | High | Campaign false-start | Yes (G-A6) | Moomoo | **DEFER_TO_FOREGROUND_LANE** |
| Capability matrix / UI vocabulary drift | B,D | High | Operator confusion | Yes (projections) | No | **DEFER_TO_FOREGROUND_LANE** |
| Opportunity engine consolidation | C | Medium | Product coherence | Partial | No | **SPEC_READY_FOR_LATER** |
| News vendor configured_not_operational | B,E | Medium | Intel gaps | Yes | API keys | **NEEDS_EXTERNAL_ACCESS** |
| PIT export API absent | F | Medium | Research friction | No | No | **IMPLEMENT_IN_ISOLATED_WORKTREE** |
| MATLAB bridge absent | G | Low | External workflow | No | MATLAB license | **DEFER-MATLAB-BRIDGE** |
| Calibration numerics UNSET | H | High | Paper fidelity claims | Yes (FTEP) | No | **DEFER_TO_FOREGROUND_LANE** |
| FULL suite ~4392 tests baseline | I | Medium | CI time | No | No | **OBSERVE** (perf budgets P7) |
| Governance docs on main merged | J | High | Truth routing | No | No | **ALREADY_COMPLETE** |
| Secrets hygiene | K | High | Credential leak | No | No | **MAINTAIN** |
| Legacy parallel type systems | L | Medium | Maintenance cost | Partial | No | **IMPLEMENT_IN_ISOLATED_WORKTREE** |
| EVIDENCE-01C deferred | B,I | High | Live trace absent | Yes | Brokers | **NEEDS_OWNER_DECISION** |
| Owner decisions OWNER-OD-1–11 | B | High | FTEP activation | Yes | Owner | **NEEDS_OWNER_DECISION** |
