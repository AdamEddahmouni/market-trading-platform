# PI8 — Contextual Intent (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Pre/post catalyst timing classification for participant actions on admitted fixtures  
**Prerequisites:** PI3 IMPLEMENTED, MC8 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Classify participant disclosure timing relative to MC8 catalyst windows without inventing identity or mechanism. Extends Participant Intelligence beyond PI6 metaorder cooperation.

## 2. Timing model (`contextual_intent_v1`)

### Catalyst window

- Default window: 14 calendar days before/after catalyst `event_time`
- PIT: action `available_time` and catalyst `available_time` ≤ `prediction_cutoff`

### Timing relation

| Relation | Condition |
|---|---|
| `PRE_CATALYST` | `action_time` < catalyst `event_time` and within window |
| `POST_CATALYST` | `action_time` ≥ catalyst `event_time` and within window |
| `CONTEMPORANEOUS` | same calendar day as catalyst `event_time` |
| `UNRELATED` | no catalyst within window |

### Intent classification

| Classification | Condition |
|---|---|
| `INFORMED_TIMING_CANDIDATE` | PRE_CATALYST + discretionary buy or activist stake |
| `REACTIVE` | POST_CATALYST + discretionary action |
| `UNRELATED` | no qualifying catalyst match |
| `INSUFFICIENT_DATA` | ambiguous action semantics |

## 3. Cross-lane signals

| Signal | Condition |
|---|---|
| `PARTICIPANT_ALIGNMENT_CANDIDATE` | INFORMED_TIMING_CANDIDATE + catalyst lean BULLISH |
| `PARTICIPANT_CONTRARIAN_CANDIDATE` | INFORMED_TIMING_CANDIDATE + catalyst lean BEARISH |

No signal when timing UNRELATED or INSUFFICIENT_DATA.

## 4. Identity policy

- Never invent participant identity from flow
- Use PI3 action semantics only

## 5. Fixtures

Uses BIYA disclosure ledger + synthetic catalyst rows in unit tests.

## 6. Out of scope

- Copyability scoring (PI9)
- Live catalyst ingest beyond admitted fixtures
