# PLATFORM-DATA-001 — Live Observational Market Data

**Status:** Active (Platformization P2)  
**Authority:** Extends [PLATFORM-PAPER-001](./2026-08-21-platform-paper-001-design.md)  
**Date:** 2026-08-21

## Authorization matrix

| data_mode | execution_mode | execution_provider | Status |
|---|---|---|---|
| `LIVE_OBSERVATIONAL` | `NONE` | `NONE` | **AUTHORIZED** (P2 primary) |
| `LIVE_OBSERVATIONAL` | `INTERNAL_SIMULATION` | `INTERNAL` | **CONDITIONAL** — requires execution admission gates |
| `LIVE_OBSERVATIONAL` | `BROKER_PAPER` | any external | **NOT AUTHORIZED** |
| `LIVE_OBSERVATIONAL` | `LIVE` | any | **NOT AUTHORIZED** |

Live observational providers operate under role **`MARKET_DATA` only**. Moomoo trade APIs must not be imported in the observational adapter path.

## Dual admission model

### Research / fixture admission (unchanged)

```text
observational capture → integrity → PIT validation → review → fixture admission → registry → replay
```

### Runtime live admission (P2)

```text
provider callback → raw envelope → normalization → timestamp interpretation
→ quality checks → capability checks → runtime admission → market state → UI / features
```

A symbol viewed live is **not** automatically an admitted research fixture.

## Architecture

```text
Moomoo OpenD (localhost, quote context only)
      ↓
tools/moomoo/* + LiveObservationalRuntime
      ↓
ProviderEnvelope / capture JSONL
      ↓
normalization.live_envelope_from_capture
      ↓
LiveAdmissionEngine (QualityObservation)
      ↓
ObservationalStateStore (L1 / trades / book)
      ↓
ui_api/live_projections → Explore / Workspace / ContextBar
```

Provider-specific fields remain in envelope provenance; downstream consumers use canonical IMP events only.

## Timestamp semantics

| Field | Meaning |
|---|---|
| `event_time` | Exchange/market event time per provider |
| `provider_received_time` | Provider upstream receipt when supplied (`provider_time_ns`) |
| `local_received_time` | IMP callback receipt (`received_time_ns` / `live_received_time`) |
| `available_time` | Earliest time downstream logic may consume the event |

For live observational mode, **`available_time` defaults to `local_received_time`**, not `event_time`.

## Admission levels

| Level | Use |
|---|---|
| `DISPLAY_ADMITTED` | UI may render with quality annotation |
| `EXECUTION_ADMITTED` | Internal simulator may consume (when enabled) |
| `BLOCKED` | Fail closed |

Cached/initial pushes, disconnects, stale quotes, and clock drift may admit display while blocking execution.

## Subscription manager

Central ref-counted manager (`subscription_manager.py`):

- deduplicates symbol × capability provider subscriptions
- tracks consumer ownership and priority
- surfaces `QUOTA_EXHAUSTED` explicitly
- restores subscriptions after reconnect

Priorities: `ACTIVE_EXECUTION_CONTEXT` > `ACTIVE_WORKSPACE` > `PINNED_WATCHLIST` > `BACKGROUND_EXPLORE`

## Configuration (fail-closed defaults)

| Variable | Default | Effect |
|---|---|---|
| `IMP_LIVE_OBSERVATIONAL` | unset | Live mode disabled |
| `IMP_MOOMOO_LIVE` | unset | No OpenD connection |
| `IMP_LIVE_FIXTURE_FEED` | unset | Optional JSONL feed for local/CI |
| `IMP_LIVE_INTERNAL_SIMULATION` | unset | Live + paper blocked |
| `IMP_MOOMOO_HOST` | `127.0.0.1` | OpenD host (localhost only) |
| `IMP_MOOMOO_PORT` | `11111` | OpenD port |

## Capture format

Observational recordings use `market_data.provider_envelope/1.0.0` JSONL plus a session manifest (`recorder.py`). Captures are **not** auto-promoted to research fixtures.

## Safety invariants

1. No Moomoo order submission in P2 observational path.
2. External execution remains unreachable without separate authorization.
3. Automatic strategy order creation is forbidden.
4. Provider disconnect degrades live state; replay/fixture mode remains usable.

## Internal live simulation (conditional)

`LIVE_OBSERVATIONAL + INTERNAL_SIMULATION` requires:

- PIT adversarial suite pass
- execution admission quality gate
- bounded event buffer
- separated fill vs mark provenance

If unsafe, mark **`DEFERRED_FOR_SAFETY`** — do not enable by default.
