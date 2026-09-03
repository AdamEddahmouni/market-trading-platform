# MRA-001 — Grounded Market Research Assistant (design spec)

**Status:** Approved for implementation  
**Spec date:** 2026-08-18  
**Scope:** MRA-001 only — deterministic grounded evidence retrieval without LLM  
**Prerequisites:** UI-001 `PASS`, UI-002 `PASS`, `ADR-LLM-001` `ACCEPTED`, Phases 9–16 whale families `PASS`

## 1. Purpose

Authorize the first Market Research Assistant slice: a read-only, provider-neutral
assistant that answers prompts by retrieving and citing canonical `/explain` and
`/inspect` projections. No network, no LLM, no execution authority.

## 2. In scope

### Governance

- MRA-001 implementation authorization, activation, and pass publication
- Assertion manifest under `manifests/mra001/`
- Acceptance assertions: `MRA-001` through `MRA-005`

### Backend (stdlib-only)

- `context_assembler` — server-assembled `AssistantContext` snapshot
- `intent_router` — deterministic prompt routing
- `GroundedEvidenceInference` — implements `ProviderNeutralInferenceBoundary`
- Wire grounded inference as default in `ReplayStore` (stub via `IMP_ASSISTANT_STUB`)

### Frontend

- Sidecar quick-actions: Explain selection, What changed?, Show conflicting evidence
- Citation refs link to explain/inspect handlers
- Grounded answer rendering (no abstention banner when answered)

## 3. Out of scope

- Real LLM / OpenAI / Anthropic adapters (MRA-002)
- Order placement, risk override, position mutation
- Portfolio queries
- Network access

## 4. Acceptance assertions

| ID | Predicate |
|---|---|
| `MRA-001` | Grounded prompt on admitted fixture returns cited answer, not `PROVIDER_NOT_AUTHORIZED` |
| `MRA-002` | Missing evidence abstains with explicit reason (`EVIDENCE_NOT_AVAILABLE` or `REF_NOT_FOUND`) |
| `MRA-003` | Response citation refs resolve to canonical explain/inspect payloads |
| `MRA-004` | `authority_boundary` remains `READ_ONLY_NO_EXECUTION`; no order routes |
| `MRA-005` | Identical replay cursor produces identical grounded answers (determinism) |

## 5. Completion definition

MRA-001 is complete when stdlib API and frontend pass contract tests, all MRA-001
assertions pass, and `mra001.pass_publication` is published.
