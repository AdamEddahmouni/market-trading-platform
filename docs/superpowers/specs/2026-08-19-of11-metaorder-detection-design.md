# OF11 — Metaorder Detection Primitives (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Persistent aggressive-flow detection primitives; no participant identity  
**Prerequisites:** OF4+ IMPLEMENTED, OF10 IMPLEMENTED (optional MBO corroboration)

## 1. Purpose

Detect probable parent-order execution schedules from consecutive same-side aggressive flow. Output `MetaorderPrimitive` only — Participant Intelligence owns lifecycle interpretation (PI6).

## 2. Detection method

`persistent_aggressive_flow_v1` clusters consecutive `ClassifiedTrade` rows with:

- `min_trade_count = 3`
- `min_signed_volume = 500`
- `min_duration_seconds = 2`

## 3. Primitive flow states (OF-owned)

| State | Condition |
|---|---|
| `FLOW_ACTIVE` | Persistent same-side flow ongoing |
| `FLOW_WEAKENING` | Last bar volume < 50% prior |
| `FLOW_STALLED` | Zero/unknown aggressor on last bar |

## 4. Cross-lane signals

| Signal | Condition |
|---|---|
| `PERSISTENT_AGGRESSIVE_BUY_FLOW` | `FLOW_ACTIVE` + buy |
| `PERSISTENT_AGGRESSIVE_SELL_FLOW` | `FLOW_ACTIVE` + sell |

## 5. Adversarial rules

- Single large print must NOT trigger
- Alternating buy/sell must NOT trigger
- No `participant_id` or named identity fields

## 6. Completion definition

OF11 complete when admitted fixture produces deterministic primitives, cross-lane signals publish, adversarial cases pass, and full test suite remains green.
