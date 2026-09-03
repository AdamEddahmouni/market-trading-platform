# UX State Matrix

**Status:** `PROPOSED`

Matrix: **Mode** × **Data/Capability state** → expected UI behavior.

## Mode dimension

| Mode | Chrome | Data scope | Trading actions |
|---|---|---|---|
| LIVE | Green LIVE | Current entitled streams | Disabled until authorized |
| REPLAY | Amber REPLAY + scrubber | Knowable at T | Disabled; sim actions labeled |
| SIMULATION | Purple SIMULATION | Sim engine state | Sim-only controls |
| PAPER | Blue PAPER (future) | Paper account | Paper order UI distinct |
| LIVE EXEC (future) | Red accent + confirm | Live account | Gated activation |

## Data/capability states

| State | Visual | User action |
|---|---|---|
| Loading | Skeleton + `Loading…` | Wait |
| Available | Normal render | Full interaction |
| Partial | `PARTIAL` badge + detail | Inspect quality; caution on DERIVED |
| Degraded | `DEGRADED` banner | Reduced trust; explain path |
| Stale | `STALE` + age | Refresh or inspect |
| Unavailable | `UNAVAILABLE` panel | Capability explanation |
| Unsupported | `UNSUPPORTED` | No proxy UI |
| Not entitled | `NOT ENTITLED` | Entitlement info |
| Not collected | `NOT COLLECTED` | System config info |
| Disconnected | `DISCONNECTED` | Reconnect status |
| Corrected | `CORRECTED` + delta | Timeline of correction |
| Quarantined | `QUARANTINED` | Admin/explain path |
| Conflicting | `CONFLICTED` in alignment | Show both sides |
| Abstain | `ABSTAIN` neutral | Not failure |
| Empty | `No matches` intentional | Distinct from unavailable |
| Permission denied | `PERMISSION DENIED` | Auth path |

## Cross-matrix (selected cells)

|  | LIVE + GOOD | REPLAY + PARTIAL | SIM + UNAVAILABLE depth |
|---|---|---|---|
| Price chart | Live updates throttled | Frozen at cursor; gap markers | Sim prices only |
| CVD | DERIVED badge | PIT recomputed | N/A or sim |
| DOM | Full if entitled | Historical book if stored | `UNAVAILABLE` |
| Filings | Delay labeled | Only if available_time ≤ T | Hidden or comparison |
| Options | Live chain | Historical snapshot | `UNAVAILABLE` |
| Model | Latest run | Run at cutoff | Sim model |
| Strategy | Current state | Historical decision | Sim only |
| Risk | Live eval (future) | Historical | Sim |
| Alerts | Real-time | Historical replay alerts | Sim events |
| AI sidecar | Cites live refs | Cites PIT refs | Sim context |

## Epistemic × quality

| Epistemic | Quality PARTIAL | UI rule |
|---|---|---|
| OBSERVED | Rare | Show with correction note |
| DERIVED | Common | Badge on card + inspector |
| INFERRED | Common | Reduce strength or show AMBIGUOUS |
| MODEL | Possible | Widen uncertainty or ABSTAIN |

## Focus mode × safety

| Element | Hidden in Focus? |
|---|---|
| Quality degradation | **Never** |
| Mode indicator | **Never** |
| Risk rejection | **Never** |
| Tier 4 metrics | Yes |
| Raw JSON | Yes |
| Diagnostic panels | Yes |

## Alert deduplication states

| State | Behavior |
|---|---|
| New transition | Show card |
| Repeat same state | Suppress or collapse |
| Escalation (magnitude↑) | Show update |
| Risk event | Always show |
