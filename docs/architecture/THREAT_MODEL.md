# Threat Model (Lite)

**Status:** Practical IMP-specific threat overview. Not a formal security audit.

## Assets

- Broker/API credentials (env, `.private/`)
- Paper ledger integrity and audit trail
- Operator decisions (intents, snapshots, correlation IDs)
- Local state database (`IMP_PERSIST_STATE`)

## Threats and mitigations

| Threat | Mitigation | Limitation |
|--------|------------|------------|
| Unauthorized live execution | LIVE-001 blocked; env gates; `execution_authority=BLOCKED` in Live | Malicious local process with env vars could enable paper — local trust model |
| Paper execution without authority | Backend rejects mutations; fail-closed preview | Direct API calls bypass UI gating |
| Demo → Paper authority confusion | Mode-specific pages + `evaluateModeContext` | UI alone not sufficient |
| Credential leakage | `.gitignore`, secret scan in validate changed, never log tokens | Operator discipline required |
| Stale preview submission | `confirmedRequestIsCurrent`, revalidation states | Must maintain test coverage |
| Query-key cache collision | Central `queryKeys`; mode/symbol in keys | Ad-hoc keys risk wrong data |
| Schema drift | Zod + JSON schemas + validation manifest | Manual discipline on optional fields |
| Provider compromise/degradation | Health panels, canary, fail-closed reads | Display may show stale data with warnings |
| Forged frontend authority | Backend operating context is authoritative | — |
| Trace/audit tampering | Append-only ledger events | Local DB file could be edited offline — out of scope for local-first |
| Dependency compromise | Stdlib lock for foundation; npm/pip audit on update | Intelligence BUILD adds numpy/sklearn/mongo for dev |

## Sensitive change flag

Changes touching credentials, authority, execution, persistence, or account identity require [SECURITY.md](../engineering/SECURITY.md) checklist and extra validation.

## Out of scope (current)

- Multi-tenant hosted security
- Network perimeter controls
- Hardware security modules
