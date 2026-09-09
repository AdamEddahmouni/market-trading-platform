# 09 — Scope Drift Register

Status: **WS02 PASS** (classifications only — no dispositions executed; WS03
traces implementation origin).

Classification vocabulary: ORIGINAL_SCOPE · AUTHORIZED_LATER_SCOPE ·
EXPLICIT_CURRENT_USER_MANDATE · CORRECT_EVOLUTION · ACCEPTABLE_DEVIATION ·
UNINTENTIONAL_SCOPE_DRIFT · INCORRECT_DONOR_IMPORT · INCOMPLETE_MIGRATION ·
OBSOLETE_REQUIREMENT · UNKNOWN_ORIGIN · MISSING_SCOPE (missing required
functionality — NOT drift; tracked separately for WS04/WS07).

## Register

| Area | Classification | Rationale | Evidence | Disposition status |
|---|---|---|---|---|
| Short Squeeze | ORIGINAL_SCOPE | Original stream (ORG-001) confirmed in integrated platform (LATER-013) | IMG-001/005 | PRESERVE |
| CVD / Level 1 / Level 2 | AUTHORIZED_LATER_SCOPE (professor) | Explicit professor stream + donor; IB L1+L2 required | IMG-002/005 | PRESERVE |
| Options | AUTHORIZED_LATER_SCOPE (professor) | Explicit professor stream + donor; profitability NOT assumed | IMG-003/005 | PRESERVE |
| Futures / Future | AUTHORIZED_LATER_SCOPE (professor) | Eric_futuresX then Claude Code News (LATER-011 expands) | IMG-001/004/006 | PRESERVE (architecture undecided) |
| Integrated platform (multi-stream) | AUTHORIZED_LATER_SCOPE | Professor's integrated-platform direction | IMG-005 | PRESERVE |
| Demo/Paper/Live + safety model | AUTHORIZED_SUPPORTING_ARCHITECTURE | Mode isolation, gates, LIVE-001 blocked | IMP governance | PRESERVE |
| Bonds / Crypto / Whale / Industry / Government / Gold / Silver / Commodities | EXPLICIT_CURRENT_USER_MANDATE | Adam's explicit current mandate; NOT drift, NOT out-of-scope; many DETAILS_TO_BE_DEFINED | Program §1 | PRESERVE / DEFINE |
| Crypto planning docs ("planning only — not authorized" per README) | CORRECT_EVOLUTION | Mandate now authorizes the domain; planning groundwork becomes relevant input | README + MND-002 | RECLASSIFY (docs superseded note) |
| GridIQ pattern port (`6adeeec`/`5ec19a7`) | INCORRECT_DONOR_IMPORT (authority) / CORRECT_EVOLUTION (implementation) | WS03: PORT_ADAPT per ADR-GRIDIQ-001, implementation independent (zero GridIQ identifiers), capability required → KEEP code; governance superseded (WS07 re-annotation) | ADR + module docstrings + grep | CODE: KEEP_AS_IS · GOVERNANCE: RE-ATTRIBUTE (WS07 Wave 1) |
| DS-340W / GridIQ donor notes and reuse-matrix rows | INCORRECT_DONOR_IMPORT (candidate) / stale governance | Records predate correction; preserved as history, flagged superseded in 01 | permissions record, matrix | WS03/WS06 |
| Unusual Whales / iVolatility in Options | DONOR_SPECIFIC (acceptable deviation) | Donor used trial accounts; not professor-mandated | IMG-003 | NOT required |
| Tradovate-based Future execution (Claude Code News) | AUTHORIZED_DONOR_SUPPORT | New authorized reference; platform decision deferred | IMG-006 | PRESERVE (decision WS05/07) |
| Moomoo OpenD / Tradier sandbox adapters | CORRECT_EVOLUTION | Authorized observational/broker-paper adapters per IMP ADRs | IMP README | PRESERVE |
| Market Context / participant lanes (MC/PI/O F-series fixture work) | CORRECT_EVOLUTION | Cooperative roadmap lanes on admitted fixtures; consistent with mandate (whale/macro) | IMP docs/research | PRESERVE |
| Any capability with unknown origin | UNKNOWN_ORIGIN | To be classified at WS03/WS04 with evidence | — | INVESTIGATE |
| Bonds/Crypto/Whale/Industry/Gov/Gold/Silver/Commodities implementation absence | MISSING_SCOPE (NOT drift) | Missing required functionality belongs in MISSING_SCOPE analysis for WS04/WS07 | — | COMPLETE (later) |

## Rules (WS02 §40)

- Missing implementation is NOT scope drift. It is MISSING_SCOPE.
- Do not call missing implementation "drift"; do not use implementation
  presence as authorization evidence.
- WS03 must not reclassify legitimate later additions as drift.