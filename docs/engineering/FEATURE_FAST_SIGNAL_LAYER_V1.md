# Feature & Fast Signal Layer V1 (BUILD 06)

> BUILD 06 converts immutable point-in-time snapshot state into deterministic structured quantitative measurements represented as `SignalV1`.

Cross-links: [INTELLIGENCE_CONTRACTS_V1.md](./INTELLIGENCE_CONTRACTS_V1.md), [IMMUTABLE_SNAPSHOT_ENGINE_V1.md](./IMMUTABLE_SNAPSHOT_ENGINE_V1.md)

BUILD 09 consumes these snapshot-bound signals through the [Event Detector & Smart Router V1](./EVENT_DETECTOR_SMART_ROUTER_V1.md) without recalculating raw features.

## What BUILD 06 Is

```text
SnapshotV1 (resolved)
    → deterministic calculators
    → SignalV1[]
```

## What BUILD 06 Is Not

| Concept | BUILD 06? |
|---|---|
| Signal | Yes |
| Forecast / probability | No (BUILD 08) |
| Trade recommendation | No |
| Expert narrative / EvidenceV1 | No (later specialists) |
| Outcome label | No |

No LLM, no training, no replay runtime (BUILD 07), no Mongo time-series collections.

## Input Boundary

BUILD 06 may consume **only** information referenced by its source `SnapshotV1`. Calculators do not query the repository for newer records, external history, or post-decision events.

Canonical pipeline:

```text
SnapshotV1 → resolve_snapshot → PreparedSnapshotState → calculators → SignalV1
```

Generated signals reference the snapshot externally. **Snapshots are never mutated** to append derived signals.

## Architecture

```text
FastSignalEngine
    ├── spread-calculator v1
    ├── cvd-calculator v1
    ├── depth-imbalance-calculator v1
    ├── momentum-calculator v1
    ├── realized-volatility-calculator v1
    └── relative-volume-calculator v1
```

Public API (`market_platform_foundation.intelligence.signals`):

- `FastSignalEngine`
- `compute_fast_signals`
- `compute_from_snapshot`
- `SignalComputationRequest` / `SignalComputationResult`

Persistence is optional at the engine boundary via `IntelligenceRepository.put_signal`. Signal core has **no PyMongo dependency**.

## Trade Direction Hierarchy

For trades without provider `aggressor_side`:

1. Provider/exchange aggressor side when present (`BUY` / `SELL`)
2. Lee-Ready quote test when operational quote exists (`bid < ask`)
3. Tick-rule fallback when prior trade price exists
4. `UNKNOWN` — excluded from signed volume and NSS denominator

Unknown-side trades are never silently assigned to buy or sell.

## Signal Catalog

| signal_type | Formula | Unit | Range | Window | Inputs | Min samples | Undefined | Calculator |
|---|---|---|---|---|---|---|---|---|
| `spread_abs` | `ask - bid` | USD/share | [0, ∞) | point-in-time quote | QUOTE | 1 valid quote | no/crossed quote | spread-calculator v1 |
| `spread_bps` | `(ask-bid)/mid × 10⁴` | basis_points | [0, ∞) | point-in-time quote | QUOTE | 1 valid quote | zero mid | spread-calculator v1 |
| `cvd` | Σ signed volume | shares | (-∞, ∞) | time window | TRADE | 1 classified trade | no classified trades | cvd-calculator v1 |
| `net_signed_share` | `(buy_vol - sell_vol)/(buy_vol+sell_vol)` | dimensionless | [-1, 1] | time window | TRADE | 1 classified | zero classified vol | cvd-calculator v1 |
| `depth_imbalance` | `(bid_depth-ask_depth)/(bid_depth+ask_depth)` | dimensionless | [-1, 1] | latest book | BOOK | 1 book | zero total depth | depth-imbalance-calculator v1 |
| `momentum_simple` | `P_end/P_start - 1` | decimal_return | (-∞, ∞) | time window | TRADE or QUOTE mid | 2 prices | insufficient prices | momentum-calculator v1 |
| `realized_vol` | sample std of log returns | log_return_std | [0, ∞) | time window | TRADE or QUOTE mid | 2 returns | insufficient returns | realized-volatility-calculator v1 |
| `relative_volume` | `V_current / V_baseline` | ratio | [0, ∞) | dual windows in snapshot | TRADE | baseline vol > 0 | zero baseline | relative-volume-calculator v1 |

### CVD / NSS

- Buy-initiated volume: positive; sell-initiated: negative
- Unknown trades excluded from CVD sum and NSS denominator (P6-compatible conservative semantics)
- Window: `(decision_time - window_ns, decision_time]` on `event_time_ns`, with `available_time_ns ≤ decision_time_ns`

### Depth

- Top-N levels (default N=5, configurable via `SignalComputationRequest.depth_levels`)
- Latest BOOK event at or before decision time

### Momentum

- Price source: trade prices first; quote mid fallback
- Simple return, not log return

### Realized Volatility

- Log returns between consecutive observations
- Sample standard deviation (Bessel correction when n≥2)
- **Not annualized** — irregular tick spacing limitation documented
- Constant price sequence → `0` when sufficient samples exist

### Relative Volume

- Baseline = prior window of equal duration **within snapshot events only**
- No repository history bypass

## Unsupported Families (documented)

| Family | Reason |
|---|---|
| Options IV / skew / OI | No canonical option chain events in current snapshot composition |
| Borrow / short change | Requires paired observations; FINRA/SEC events not in typical microstructure snapshots |
| Cross-asset | Requires multi-instrument snapshot policy not yet standard |

## Signal Identity

Strategy: `signal-content-sha256-v1`

Identity payload includes:

- `source_snapshot_id`
- `signal_type`
- `scope`
- `calculator_id` + `calculator_version`
- `window_ns` (windowed signals only)
- `parameters` (e.g. `depth_levels`)

**Computed numeric value is excluded** from identity so immutable persistence detects nondeterministic recomputation as `IMMUTABLE_CONFLICT`.

Signal IDs: `SIG-<sha256>`

`as_of_time_ns` = `snapshot.decision_time_ns`

## Quality Semantics

| Snapshot quality | Signal behavior |
|---|---|
| GOOD | GOOD signals when calculation succeeds |
| DEGRADED | Signals retain DEGRADED |
| INVALID | No operational signals |

Undefined statistics → diagnostic skip, not zero, not NaN.

## Persistence

```text
SignalV1 → IntelligenceRepository.put_signal → canonical signals collection
```

Idempotent: `INSERTED` / `ALREADY_PRESENT`. Conflicting semantic replay → `RepositoryConflictError`.

## BUILD 07 Handoff

Replay provides historical events → `SnapshotBuilder` at decision time T → `resolve_snapshot` → same BUILD 06 calculators → identical `SignalV1`. No replay-specific formula branches.

## BUILD 08 Handoff

Baseline models consume persisted `SignalV1` measurements rather than recomputing raw features independently.
