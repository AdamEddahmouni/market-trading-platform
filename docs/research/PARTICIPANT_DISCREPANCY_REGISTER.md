# Participant Intelligence — Discrepancy Register (Deliverable 4)

| ID | Existing behavior | Why incomplete / incorrect | Risk | Recommended change | Owner | Phase | Priority |
|---|---|---|---|---|---|---|---|
| PI-D01 | `features/institutional.py` returns `direction: neutral` + counts only | No participant semantics; cannot support conditional follow/fade | High — false neutrality | Consume `ParticipantAction`; publish mechanism-aware summaries | Participant | PI3 | P0 |
| PI-D02 | `edgar_whale.py` maps Form 4 direction via P/S only | Ignores grant/exercise/tax codes | Medium — misclassified insider actions | Use `ParticipantActionType` + `InsiderDiscretion` | Participant | PI2 | P0 |
| PI-D03 | Form 5 not in `FORM_TYPE_MAP` | Incomplete insider coverage | Low | Add when data available | Participant | PI3 | P2 |
| PI-D04 | 13F treated as holding snapshot without copyability flags | Lookahead / false real-time copy risk | **Critical** | `QUARTER_END_NOT_COPYABLE`, `available_time` enforcement | Participant | PI2/PI4 | P0 |
| PI-D05 | No `participant_id` canonical model | Cannot track skill/history | High | `contracts/participant.py` | Participant | PI1 | P0 |
| PI-D06 | Whale ledger `futures_positioning` holds ES depth, not COT | Naming confusion; cross-lane misinterpretation | Medium | Document alias; PI consumes F4 COT separately | Platform/Participant | PI11 | P1 |
| PI-D07 | No cross-lane insider/activist signals | SS/Options cannot consume disclosure semantics | Medium | `EvidenceSignal` participant family | Participant | PI3 | P1 |
| PI-D08 | Strategy `WHALE_ALIGNED` without mechanism | May align with passive/forced flow | High | Gate on mechanism + copyability (PI7/PI9) | Participant/Strategy | PI9 | P1 — **PARTIAL** (fixture scope: `ABSTAIN_COPYABILITY_UNAVAILABLE`) |
| PI-D09 | Options whale family without participant identity | Correct fail-closed; no PI bridge | Low | `UNKNOWN_LARGE_OPTIONS_PARTICIPANT` when PI12 | Participant/Options | PI12 | P2 |
| PI-D10 | Metaorder research not started (OF11) | Live whale-flow remaining unknown | Medium | PI6 cooperates with OF11 | Order Flow/Participant | PI6 | **RESOLVED (fixture scope)** |
| PI-D11 | Activist 13D lacks structured campaign fields | Cannot research strategic influence | Medium | PI3 extraction schema | Participant | PI3 | P1 |
| PI-D12 | No participant skill / shrinkage | "Smart money" heuristic risk | High | PI5 walk-forward skill | Participant | PI5 | **RESOLVED (fixture scope)** |
| PI-D13 | Institutional ignition cards use family counts | Not commitment/skill aware | Medium | Wire `ParticipantEvidence` + PI5 skill | Participant/SS bridge | PI5 | **PARTIAL (skill wired)** |
| PI-D14 | Crypto wallet labels without `label_available_time` | Historical leakage | **Critical** (future) | PI14 contract enforcement | Participant/Crypto | PI14 | Deferred |
| PI-D15 | `COPY_PLATFORM_SIGNAL` enum unused | Research track undefined | Low | RESEARCH_FIRST per professor brief | Participant | PI16 | P3 |
| PI-D16 | Missing ≠ neutral not enforced in institutional query | Unknown intent treated as neutral count | Medium | Explicit `INSUFFICIENT_INFORMATION` | Participant | PI2 | P0 |
