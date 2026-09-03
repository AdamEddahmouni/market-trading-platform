# Component Contract Matrix

**Status:** `PROPOSED` — initial high-priority components

Legend: **E** = epistemic class, **Q** = quality behavior

| Component | Purpose | Tier | E | Data dependency | Explain path | Unavailable | Keyboard |
|---|---|---|---|---|---|---|---|
| **ContextBar** | Mode, time, symbol, quality | 1 | — | ModeState, AsOfContext | N/A | Show DISCONNECTED | Focusable segments |
| **AttentionCard** | NOW ranked item | 1 | INF/STR | AttentionItem | Full chain | Hide if no data | Enter to open |
| **StateTransitionBlock** | Changed/unchanged lists | 1 | STR/INF | StateTransition | Per criterion | N/A | Expand/collapse |
| **EvidenceAlignmentPanel** | Multi-domain directions | 2 | Mixed | EvidenceBundle[] | Per row | Domain UNAVAILABLE rows | Row focus |
| **QualityBanner** | Global degradation | 1 | — | QualitySummary | Inspect quality | N/A | Dismiss forbidden |
| **CapabilityPanel** | Module unavailable | 2 | — | CapabilityState | Capability details | Self | N/A |
| **ExplanationDrawer** | Levels 1–2 explain | 2 | * | ExplanationReference | Inspector link | EXPLANATION UNAVAILABLE | Esc close |
| **EvidenceInspector** | Deep inspect | 3–6 | * | InspectableRef | Self | Per-tab | Tab nav |
| **MarketStoryTimeline** | Event sequence | 2 | OBS/INF | TimelineEvent[] | Event inspect | Empty vs unavailable | Arrow nav |
| **ReplayScrubber** | Time travel | 1 | — | ReplaySession | N/A | Disabled in LIVE | Space, arrows |
| **PriceChart** | OHLCV display | 2 | OBS | BarSeries | Point inspect | CapabilityPanel | Summary table alt |
| **ScreenerResultRow** | Explore match | 2 | DER | ScreenMatch | Why matched? | N/A | Enter |
| **FlowTable** | Options/order flow | 3–4 | OBS/DER | FlowEvent[] | Row inspect | NOT ENTITLED | Virtualized nav |
| **CommandPalette** | Expert navigation | — | — | Routes, commands | N/A | N/A | Typeahead |
| **AISidecar** | Contextual assist | 2 | — | Context + citations | Citation links | Provider down | Message list a11y |
| **WatchlistTable** | Compact symbols | 2 | OBS | WatchlistQuote | Symbol open | Empty list | Table nav |
| **NumericalCell** | Formatted number | 2–4 | * | Value + meta | Inspector | `—` unavailable | Copy precision |

## Component requirements template (for new components)

```markdown
### ComponentName
- **Purpose:**
- **Information shown:**
- **Interaction:**
- **Data dependency:**
- **Epistemic class:**
- **Quality behavior:**
- **Explanation path:**
- **Loading state:**
- **Unavailable state:**
- **Responsive behavior:**
- **Keyboard behavior:**
```

## Performance UX (all real-time components)

- Batch visual updates (e.g., 100–250ms)
- Stable row keys / no layout shift
- Virtualize tables >50 rows
- Throttle chart repaints
- Update highlight on meaningful change only
- Show freshness timestamp

## Traceability examples

| UI component | Backend chain |
|---|---|
| CVD card | canonical trades → aggressor → FeatureRunner CVD v1 → quality |
| Squeeze state | squeeze engine → evidence bundle → freshness gates → FSM |
| Institutional row | ADR-WHALE family → adapter → unavailable fail-closed |

Do not imply chains that Phase 5 does not support.
