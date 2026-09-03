# Accessibility Requirements

**Status:** `PROPOSED`  
**Baseline:** WCAG 2.2 Level AA where applicable ([W3C Quick Ref](https://www.w3.org/WAI/WCAG22/quickref/))

## Requirements

### Perceivable
- Text contrast ≥ 4.5:1 (normal), 3:1 (large text) on dark surfaces
- Non-text UI contrast ≥ 3:1 for controls and chart focus indicators
- Color never sole carrier of meaning — direction uses text + icons
- Scalable text to 200% without loss of function
- Charts: plain-language summary + key-value table alternative

### Operable
- Full keyboard navigation for all non-chart-critical flows
- Visible focus rings (not removed for aesthetics)
- No keyboard traps in inspector/sidecar
- Skip link to main content
- Replay controls keyboard-operable

### Understandable
- Consistent navigation and terminology
- Error/quality messages in plain language
- Mode (LIVE/REPLAY) announced on change (live region)

### Robust
- Semantic HTML landmarks: `nav`, `main`, `complementary` (inspector)
- ARIA live regions for alerts and quality changes
- Table headers associated with data cells
- Form labels and error identification

## Chart accessibility

| Requirement | Implementation |
|---|---|
| Summary | Auto-generated or template-based text summary |
| Data table | Export/view underlying OHLCV or selected series |
| Selection | Keyboard-navigable data points where feasible |
| Motion | Respect `prefers-reduced-motion` |

High-frequency tick charts may offer simplified accessible view (aggregated bars).

## Expert shortcuts vs accessibility

Shortcuts augment, never replace, standard navigation. Document in `?` help overlay.

## Testing plan (usability)

Include screen reader spot-checks (NVDA/VoiceOver) in Foundation V0 validation:

1. Announce mode change live → replay
2. Navigate attention card → explain → inspector
3. Read evidence alignment without color-only cues

## Design system tokens

See [design-system-direction.md](design-system-direction.md) for accessible dark palette.
