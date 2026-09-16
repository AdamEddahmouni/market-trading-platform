# Responsive Contract

One breakpoint scale replaces the 9-value sprawl (640 / 720 / 820 / 900 / 901 / 960 /
980 / 1080 / 1100 across 12 files — audit 05). This contract is binding for every new
surface and every migrated page.

---

## 1. The breakpoint scale

CSS media queries cannot read custom properties, so the scale is defined as
**documented constants** mirrored in three places: tokens.css comments, a JS module
`ui/src/lib/breakpoints.ts`, and this doc. No other width values may appear in
`@media` rules.

| Name | Value | Meaning |
|---|---|---|
| `BP_SM` | **720px** | Below: handset/small window. Single column everywhere; sidebar and drawers are overlays; tables collapse to cards or scroll. |
| `BP_MD` | **1024px** | Below: sidebar becomes an overlay (moves up from today's 900px); drawers overlay; multi-column grids collapse to 2 → 1 columns. |
| `BP_LG` | **1440px** | Above: full-density operator layout (3-column cockpits). Between `BP_MD` and `BP_LG`: comfortable 2-column density. (Drawers stay overlays at all widths — see §3.) |

**Justification.**
- 720px is already the most common existing collapse point (6 files use it) and covers
  small windows; keeping it minimizes migration churn.
- 1024px is the smallest verification width and the current worst-case band: today
  the 220px sidebar stays inline until 900px while 360px drawers are grid columns,
  squeezing main content to ~444px at 1024px and overflowing at 901–1100px (audit 02
  §A, audit 05). Moving the sidebar overlay to 1024px and making drawers overlays
  **eliminates the tight band by construction** (no width in [1024, 1440) ever
  subtracts both bars).
- 1440px matches the most common desktop verification targets (1440/1366/1280 behave
  identically: 2-column) and the existing content max-widths (1440–1600px).
- The other six values (640/820/900/960/980/1080) are subsumed: 640→720, 820/900/
  960/980/1080→1024 or 1440 per component behavior.

## 2. Verification widths (hard requirement)

**No page-level horizontal scroll** at any of: **2560, 1920, 1600, 1440, 1366, 1280,
1024**. Grids and tables may scroll *internally*. At 2560/1920, content is centered
at its max-width (no full-bleed stretching). Verification is manual + automated
(Playwright viewport matrix, run only when no trading session is active — audit 05);
until automation lands, every page PR includes a 7-width sweep checklist.

## 3. Shell behavior per breakpoint

| Element | ≥ 1440px | 1024–1439px | 720–1023px | < 720px |
|---|---|---|---|---|
| Sidebar (`PrimaryNav`) | Inline, 220px (`--imp-sidebar-width`) | Inline, 220px | **Overlay dialog** (backdrop, focus trap, inert — existing `ImpProductChrome` mobile pattern, breakpoint moved from 900→1024) | Overlay dialog |
| Top bar | Full: menu(hidden), CommandPalette, posture, `?`, Switch mode | Same | CommandPalette collapses to icon button | Icon buttons only |
| StatusBar | One row, all segments | One row; details text truncates with ellipsis; low-priority segments (session) collapse into the details popover | Compact: ModeBadge + data health + degradation indicator only; rest in popover | Same, horizontally scrollable segment row as last resort (internal scroll, not page scroll) |
| Drawers (assistant, explanation, inspector, provider matrix) | Overlay right, `min(420px, 100vw)` — **no longer grid columns** | Overlay right | Overlay, full-height | Full-screen sheet |
| Assistant sidecar | Overlay (same Drawer primitive) | Overlay | Overlay | Full-screen sheet |

**Drawer geometry fix (binding):** drawers are `position: fixed` overlays anchored to
the viewport, `top` = `--imp-topbar-height` + `--imp-statusbar-height` (48 + 40 = 88px)
— replacing the stale `top: calc(44px + 40px)` = 84px that currently overlaps the
~205px top stack (audit 02 §D6). The sticky workspace lane nav offset is recomputed
the same way (`top: 88px`, not the current dead 120px). Both values come from tokens,
so future chrome changes cannot drift again.

## 4. Containment rules (binding)

1. **Page overflow guard:** `html, body, #root { overflow-x: clip; }` — a global
   guard the current app lacks (audit 02 §5). Any page-level overflow is a build-blocking
   regression, not a style choice.
2. **`min-width: 0` on every grid/flex child that carries content** (the existing
   safe pattern: `.main-content`, `.imp-product-main`, `.paper-panel` — generalize
   it into the primitives).
3. **Tables:** every `DataTable` renders inside a scroll wrapper — the
   `paper-portfolio.css` pattern generalized:
   `.imp-table-wrap { overflow-x: auto; }` + table `min-width` per density
   (compact 640px / standard 860–960px) + optional column-hiding below `BP_MD`
   (drop least-important columns first, as `paper-portfolio.css:256-265` does).
   The 20 uncontained tables from audit 02 §B all migrate to this pattern.
4. **Identifiers:** `CopyableIdentifier` — truncate-middle (`B74B…C9A2`), mono,
   `overflow: hidden; text-overflow: ellipsis` inside flex contexts, copy button,
   full value in TechnicalDetails. Manual `slice(0,n)…` truncation without copy is
   banned (4 current sites).
5. **Long strings:** `overflow-wrap: anywhere` on metric `dd`s (existing ribbon
   pattern); `word-break: break-word` in detail rows (existing `JsonDetailPanel`
   pattern); `white-space: nowrap` only inside scroll containers or with ellipsis +
   `min-width: 0`.
6. **Charts:** size to container (existing `clientWidth`/`ResponsiveContainer`/
   `ResizeObserver` patterns — keep); charts never dictate page width.
7. **Popovers:** the discover evidence popover (absolutely positioned, paints over
   neighbors) is replaced by a real portal-based popover/Drawer (audit 02 §D10).

## 5. Component-level responsive notes

| Component | Rule |
|---|---|
| `MetricGroup` | `repeat(auto-fit, minmax(160px, 1fr))`; ≥ 2 columns until `BP_SM` |
| Command decision grid (today's `paper-now.css` 3-col min ~882px) | 3 columns ≥ `BP_LG`; 2 columns 1024–1439; 1 column < 1024 (fixes the 1081–1150px few-px overflow) |
| Control grid (today's `operator-control.css` min ~654px) | 2 columns ≥ `BP_MD`; 1 column below (fixes 821–1094px overflow) |
| StatusBar segments | `min-width: 0` + ellipsis per segment; never wraps to a second row |
| Workspace lane Tabs | Horizontal scroll strip (internal) below `BP_LG`; `aria-scrollable` pattern, active tab scrolled into view |
| Radar dense table | Existing 6→4→2 column collapse (1100/720) re-mapped to `BP_LG`/`BP_SM` |
| Discover controls row | `flex-wrap: wrap`; select `min-width` drops from 280px → 100% at `BP_SM` (fixes audit 02 §A5) |
| Portfolio layout (`1fr 360px` trace column) | Trace column becomes a Drawer below `BP_LG` (fixes the never-collapsing 360px column) |
| `ModeEnvironmentBar` successor (StatusBar) | No fixed min-width grid; segments shrink with `minmax(0, …)` (fixes the ~614px minimum) |

## 6. Density & touch notes

- Desktop-first compact density is retained (13px base, 6–8px table padding).
- Interactive targets ≥ 44px only where coarse pointers are expected (mode launcher
  already does this); desktop operator surfaces may stay compact — but **focus rings
  must be visible at every density** (one global token-driven `:focus-visible` rule).
- `prefers-reduced-motion` and `forced-colors` media queries are required on every
  new animated or tone-coded surface (5 and 4 files have them today; extend, don't
  regress).
- No `100vw` widths (current clean record — keep it).

## 7. Migration notes

- Existing per-page media queries are re-pointed to the three values as pages migrate
  (phases 2–8); CSS-existence tests that string-match breakpoints
  (`PaperNowPage.test.tsx:270-273` etc.) are updated in the same PR.
- `MOBILE_NAV_MAX_PX` (`ImpProductChrome.tsx:12`) moves 900 → 1024; the jsdom
  matchMedia mock in `App.test.tsx:420-432` is updated accordingly.
- A new smoke test asserts no `@media` width outside `{720, 1024, 1440}` exists in
  `ui/src/styles/**` (same style as the existing CSS string assertions).
