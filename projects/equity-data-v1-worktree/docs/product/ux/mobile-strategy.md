# Mobile & Responsive Strategy

**Status:** `PROPOSED`

## Principle

No feature-parity pretense. Mobile is intentional for attention, explanation, and monitoring — not DOM heatmaps or model development.

## Desktop / tablet / mobile matrix

| Capability | Desktop | Tablet | Mobile |
|---|---|---|---|
| NOW / attention | Full | Full | Full |
| Alerts + explanations | Full | Full | Full |
| Watchlists | Full | Full | Full |
| Instrument overview | Full | Full | Simplified |
| Evidence inspector | Panel | Sheet | Full-screen sheet |
| AI sidecar | Panel | Sheet | Full-screen |
| Order flow / DOM | Full | Partial | Not offered |
| Options chain | Full | Scroll | Summary only |
| Screeners | Full | Full | Saved screens + results list |
| Replay | Full | Limited | Jump-to-event only |
| Model Lab | Full | Read-only | Not offered |
| Portfolio/risk | Full | Full | Summary + alerts |

## Mobile primary navigation

Bottom tabs (max 5):

```
NOW | Watchlists | Search | Alerts | More
```

`More`: Instrument (recent), Assistant history, Settings, Portfolio (future).

## Mobile NOW

- Attention cards stack vertically
- Swipe actions: Explain, Open, Dismiss (non-risk)
- 30-second explanation path for push notification deep links (Flow K)

## Mobile instrument overview

- Price + session summary
- Evidence alignment (compact)
- Top 3 Story events
- Quality banner if not GOOD
- CTA: Full analysis on desktop (honest upsell)

## Responsive breakpoints (proposed)

| Breakpoint | Layout |
|---|---|
| ≥1280px | 3-column: nav + main + inspector |
| 1024–1279px | 2-column: collapsible inspector |
| 768–1023px | Single column; inspector as sheet |
| <768px | Mobile tab bar |

## Touch considerations

- Minimum 44×44px touch targets
- No hover-only critical info
- Pull-to-refresh on NOW (with stale indicator)

## PWA considerations (NEEDS DECISION)

Offline: watchlists cached; live data requires connection. Replay sessions may cache last viewed state.
