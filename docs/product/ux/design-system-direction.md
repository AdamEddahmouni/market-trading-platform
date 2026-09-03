# Design System Direction

**Status:** `PROPOSED` — not implementation

## Aesthetic

Professional dark quantitative research terminal. Credible for institutional research; powerful for active analysis.

**Quiet by default. Dense when requested.**

## Surfaces (dark theme)

| Token | Use | Example |
|---|---|---|
| `surface-0` | App background | `#0D0F12` |
| `surface-1` | Cards, panels | `#141820` |
| `surface-2` | Elevated modals | `#1A2030` |
| `surface-3` | Inspector | `#12161E` |
| `border-subtle` | Dividers | `#2A3142` |
| `border-focus` | Focus ring | `#5B8DEF` |

Exact values subject to contrast validation — illustrative only.

## Typography

| Role | Font stack (proposed) | Notes |
|---|---|---|
| UI | Inter, system-ui | Legibility at small sizes |
| Numbers | Tabular figures mandatory | `font-variant-numeric: tabular-nums` |
| Mono | JetBrains Mono, ui-monospace | Timestamps, IDs, raw JSON |

### Scale
- `text-xs` 11px — metadata, badges
- `text-sm` 13px — table body, cards
- `text-base` 14px — default UI
- `text-lg` 16px — section headers
- `text-xl` 20px — instrument symbol

## Density

| Mode | Row height | Padding |
|---|---|---|
| Compact | 28px | 4px |
| Default | 36px | 8px |
| Comfortable | 44px | 12px |

User preference; safety banners unaffected.

## Semantic colors (accessible)

| Semantic | Use | Not for |
|---|---|---|
| `direction-long` | ↑ LONG text+bg tint | Quality |
| `direction-short` | ↓ SHORT | Errors |
| `conflict` | ↕ CONFLICTED | Warnings |
| `warning` | Quality degraded | Direction |
| `risk` | Risk reject, breach | Bearish |
| `error` | System failure | Short bias |
| `unavailable` | Muted slate | Empty = 0 |

All direction colors paired with text labels.

## Epistemic badges

Small caps pill: `OBS` `DER` `INF` `MDL` `STR` `RSK` `EXE` — distinct hue families, not direction colors.

## Quality badges

`GOOD` `PARTIAL` `DEGRADED` `STALE` `UNAVAILABLE` — amber/red only for actionable degradation.

## Components (planned)

- Attention card
- Evidence alignment panel
- State transition block
- Quality banner
- Capability unavailable panel
- Mode context bar
- Market Story event chip
- Inspector tabs
- Screener match explainer
- Numerical cell (aligned, formatted)

## Numerical formatting

| Type | Display | Inspector precision |
|---|---|---|
| Price | 2 dec (equity), tick-aware (futures) | Full |
| Percent | 2 dec + sign | Full |
| Bps | 0–1 dec | Full |
| Volume | K/M/B suffix | Exact |
| IV | 1 dec % | Full |
| Greeks | 3–4 dec | Full |
| Timestamp | `HH:mm:ss.SSS ET` live; date in replay | ISO8601 |

Avoid false precision on derived/inferred values.

## Motion

- Meaningful change: brief highlight fade (150ms)
- No tick flash
- `prefers-reduced-motion`: instant state change
- Replay scrub: smooth cursor only if reduced motion off

## Charts

- Minimal grid noise
- Crosshair with values (keyboard accessible summary)
- Source + epistemic badge in chart header
- Empty ≠ broken — use capability panel

## Elevation

Subtle borders preferred over heavy shadows on dark theme.
