# PI6 — Metaorder Cooperation (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Lifecycle interpretation of OF11 primitives, cross-lane MetaorderEvidence publish  
**Prerequisites:** OF11 IMPLEMENTED

## 1. Purpose

Interpret Order Flow metaorder primitives into Participant-owned lifecycle evidence. Never invent participant identity from flow.

## 2. Lifecycle mapping

| OF11 state | PI6 state |
|---|---|
| `FLOW_ACTIVE` | `ACTIVE` |
| `FLOW_WEAKENING` | `PAUSED` |
| `FLOW_STALLED` | `LIKELY_COMPLETE` |
| other | `INSUFFICIENT_INFORMATION` |

## 3. Identity policy

- `participant_type = UNKNOWN_LARGE_PARTICIPANT`
- `identity_confidence = ANONYMOUS_INSTITUTIONAL_SCALE`
- `mechanism = MECHANICAL_FLOW`

## 4. Cross-lane signals

| Signal | Condition |
|---|---|
| `METAORDER_LIKELY_ACTIVE` | `ACTIVE` lifecycle |
| `METAORDER_LIKELY_COMPLETE` | `LIKELY_COMPLETE` lifecycle |

Ambiguous or insufficient → no directional signal.

## 5. PIT rules

Primitives included only when `available_time <= prediction_cutoff`.

## 6. Completion definition

PI6 complete when fixture pipeline produces deterministic `MetaorderEvidence`, PIT tests pass, cross-lane signals publish, PI-D10 resolved, and full test suite remains green.
