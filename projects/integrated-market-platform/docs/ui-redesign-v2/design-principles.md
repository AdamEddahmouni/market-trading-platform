# Design Principles

Binding presentation rules for the redesign. Simplify presentation, **never truth**:
every backend value remains reachable; nothing operational is fabricated.

---

## 1. Information hierarchy: L1 → L4

| Level | Name | Content | Presentation rules |
|---|---|---|---|
| **L1** | What matters now | Opportunities, positions, P&L, risk, system problems, required actions | Visible without scrolling on the section's landing view; human sentences; one-glance tones (with text, never color-only); no enums, no IDs, no raw timestamps |
| **L2** | What does it mean | Why, confidence, severity, freshness, implications, next actions | Primary panels/cards on the page; every L2 claim carries a freshness and a next action where one exists |
| **L3** | Why does IMP think this | Signals, evidence, source agreement, metrics, distributions | Expanded cards, evidence drawers, lane tabs; structured `EvidenceStack`/`ContradictionPanel`; raw feature values allowed in labeled grids |
| **L4** | Technical / audit | UUIDs, hashes, session IDs, fingerprints, raw timestamps, enums, diagnostics, raw JSON | **Only** behind disclosure: `TechnicalDetails` (Audit / Methodology / Evidence / Diagnostics), inspector drawer, or the StatusBar details popover. Never in L1/L2 viewports. |

**Examples of correct leveling:**
- `DATA FIXTURE_REPLAY · EXEC INTERNAL_SIMULATION · AUTH PAPER_ONLY` (L4 values) → L1:
  "Demo replay — trading disabled" (`ModeBadge`); raw triple in StatusBar details.
- `strategy_identity_hash` (full mono hash in Model Lab primary viewport — S7) → L4
  Methodology disclosure; L2 shows "Strategy identity verified · matches
  preregistration" when true.
- `QUALITY STALE` badge → L1: "Market data is stale — quotes may be delayed." +
  affected surfaces + link to Providers; raw `state`/`detail` in TechnicalDetails.
- `mark_as_of_ns` nanosecond epoch → L2: "Price stale · last updated 12m ago"; ns
  epoch in TechnicalDetails.

**Demotion test:** if a string contains `_`, is a UUID/hash, is a raw ISO/epoch
timestamp, or requires backend source knowledge to decode, it does not belong above L3.

## 2. Language rule

Human sentences are primary everywhere; raw enums appear only inside detail surfaces
(L4). The canonical translations live in
[semantic-state-system.md](semantic-state-system.md); the UI **translates, never
invents** — unmapped values fall back to neutral tone + the raw string inside a
detail surface, never a guessed sentence.

### Before / after (top replacements from audit 04's 43-row jargon map)

| # | Before (current render) | After (primary surface) | Raw retained in |
|---|---|---|---|
| 1 | `DATA FIXTURE_REPLAY` | "Demo replay (recorded data)" | Audit details: `data_mode` |
| 2 | `EXEC INTERNAL_SIMULATION` | "Paper trading (simulated fills)" | Audit details: `execution_mode` |
| 3 | `AUTH PAPER_ONLY` | "Paper orders only" | Audit details: `execution_authority` |
| 4 | `AS OF 2026-08-29T20:59:58.984238+00:00` | "Data as of 4:59 PM ET · updated 2m ago" | Technical details: raw ISO |
| 5 | `QUALITY STALE` | "Market data is stale — quotes may be delayed." | Technical details: `state` + `detail` |
| 6 | `SCOPE —` | "No instrument selected" | — |
| 7 | `Backend aligned · DATA … · EXEC … · AUTH …` | "Backend is in demo replay with execution disabled" | Audit details |
| 8 | `cash starting 100000 minor` | "Starting cash $100,000.00" | Technical details: minor units |
| 9 | `OPEN · 6a2f1c4d-… · FIXTURE_REPLAY / INTERNAL_SIMULATION` | "Open · started Sep 12 · demo replay / paper" | Audit details: full session id |
| 10 | `Mark quality STALE` / `Mark as of <ns>` | "Price stale · last updated 12m ago" | Technical details |
| 11 | `Price (minor)` / `fill_price_minor` | Currency-formatted `$1,234.56` | Technical details |
| 12 | `Data quality STALE` / `Model UNAVAILABLE` | "Mark data is stale — unrealized P&L may be inaccurate." | Technical details |
| 13 | `<code>SQUEEZE_IGNITION_WATCH</code>` reason chips | "Ignition watch triggered" | Technical details: `reason.code` |
| 14 | `tier-1` border-color-only card | "Tier 1 — act now" visible label + tone | — |
| 15 | `STATE: PRE_IGNITION` / `Freshness: STALE` | "Squeeze state: pre-ignition" · "updated 5m ago" | Audit details |
| 16 | `2 PASS / 3 FAIL / 1 UNKNOWN` | "2 of 6 checks passing · 3 failing · 1 unknown" + rule links | Audit details |
| 17 | Epistemic chips `OBSERVED` / `DERIVED` / `INFERRED` | "From provider data" / "Calculated by IMP" / "IMP inference — unverified" | Audit details: `epistemic_class` |
| 18 | `Epistemic class: OBSERVED · Boundary: RESEARCH_ONLY` | "Research-only evidence — not tradeable" | Audit details |
| 19 | `UNAVAILABLE — WHALE_NO_ENTITLED_SOURCE` | "Not available with your current data subscription — this lane is disabled." | Technical details: `reason` |
| 20 | `MOOMOO · CONNECTED_DEGRADED` | "Moomoo — connected with problems" | Technical details: `connection_state` |
| 21 | `Execution eligibility DISPLAY_ONLY` | "Market data only — cannot route orders" | Audit details |
| 22 | `US_EQUITY_L1 · refs 1` | "US equities — basic quotes" | Audit details: capability id |
| 23 | `Radar unready ({unready_reason})` | "Opportunity radar isn't ready: {human reason}." + action link | Technical details |
| 24 | `Live blocked: {block_reasons.join(", ")}` | One sentence per reason: "Live trading is blocked: daily loss limit reached" | Audit details |
| 25 | `IMP_PAPER_EXECUTION=1` env-var instructions | "Paper execution is off. Enable it in Settings → Safety." (CLI kept as advanced fallback) | Technical details: env var |
| 26 | `GATED` nav badge | Removed (no gate logic exists) or "Locked in this mode" + reason | — |
| 27 | `broker_order_id ?? "NONE"` | "Not sent to broker" | Technical details |
| 28 | `Restore … · NONE` / `Execution deferred NO` | "Crash recovery: none needed" / "Execution startup: normal" | Technical details |

Money rule: minor units are **never** rendered; format as currency with the account's
denomination. Time rule: primary surfaces show human time ("4:59 PM ET · 2m ago");
raw ISO/epoch only in TechnicalDetails. Identifier rule: truncate-middle with copy
(`B74B…C9A2` + copy button) via `CopyableIdentifier`; full value in Audit details.

## 3. Warning template (3-question rule)

Every warning / degraded / blocked / stale / unknown / failed condition answers, in
order:

1. **What happened** — one human sentence ("Market data is partially degraded").
2. **What it affects** — the surfaces/decisions impacted ("Some discovery sources are
   unavailable; ranked opportunities may be incomplete").
3. **What to do** — an action or an explicit "no action needed" ("Check Providers in
   Control" / "No action needed — replay continues from the last confirmed event").

Implementation: `AttentionBanner` with `tone` + three content slots; the 17 failing
states from audit 04 are the first migration targets (bare "X unavailable." strings
are banned). Reference implementation to copy: Operator Center's label / detail /
next-action readiness checks (audit 04, the single ✅).

## 4. Opportunity card content rule

Every opportunity, at every density, can answer nine questions: **what is it / why
now / what changed / evidence strength / freshness / confirms / contradicts / risk /
next action.**

- **First card (compact/review density):** curated subset — what is it, why now, what
  changed, evidence strength (`ConfidenceIndicator`), freshness (`FreshnessIndicator`),
  next action. Six of nine, glanceable.
- **Expanded (full `OpportunityCard`):** all nine — adds confirms, contradicts
  (`ContradictionPanel`), risk (`RiskSummary`-lite), plus evidence provenance
  (`EvidenceStack` with per-source agreement) and trade-review history.
- Raw ranking vectors, feature values, reason codes, and row IDs live in the expanded
  evidence section (L3) / TechnicalDetails (L4).
- Empty queue states explain **why** (feed UNREADY reason, filters, live mode has no
  opportunity engine) and what unblocks it.

## 5. Density rules

- Compact terminal density: base body `13px` (`--imp-text-sm`), dense tables
  `12–13px`, micro labels `11px` minimum (nothing below `--imp-text-micro: 11px`;
  current 0.62rem/10px labels are retired — they also fail contrast).
- Spacing from the `--imp-space-*` scale only (4/8/12/16/24/32); no ad-hoc px gaps.
- One H1 per page via `PageHeader`; display clamps (`clamp(2rem…5.4rem)`) are
  replaced by the fixed type scale — density beats theatrical type.
- Monospace **only** for market values, identifiers, timestamps, raw evidence. The
  current mono-eyebrow/label habit (`.demo-eyebrow`, `.paper-eyebrow`, KPI labels,
  nav hints) is retired — eyebrows use `--font-ui` small-caps treatment.
- Corner radii restrained: `--imp-radius-sm 4px` / `--imp-radius-md 6px` /
  `--imp-radius-lg 10px`; pills (999px) only for tone badges.

## 6. Visual direction

- Near-black/graphite surfaces (`--surface-0 #0c0e12` family retained), frosted-glass
  panels (subtle translucency + 1px `--border-subtle`), restrained borders.
- Warm orange/lava IMP accent (`--accent-primary #ff6a00`) for primary actions,
  active nav, focus, and the PAPER/SIMULATION semantic tone.
- Semantic tones per [semantic-state-system.md](semantic-state-system.md); color never
  the sole encoder (always paired with text/icon).
- Minimal line-art iconography; no illustration library; no emoji in UI.
- **No** generic SaaS dashboards, marketing gradients, excessive glow, heavy rounding,
  or glassmorphism stacking. `--accent-glow` usage stays limited to focus/active
  hints.
- Charts: one theme module (`chartTokens.ts`) sourced from tokens; IMP orange accent;
  green/red reserved for direction; every chart ships a text summary (a11y).

## 7. Do / Don't

**Do**
- Do translate every backend enum through `resolveSemanticState` before rendering.
- Do keep every raw value reachable in TechnicalDetails / Audit / Evidence surfaces.
- Do pair every tone with text or icon (tone + label, never color alone).
- Do give every empty state a reason and, when one exists, an action.
- Do keep Paper submit inside the Workspace cockpit with a current preview; keep
  fail-closed guards; keep observability when authority is lost.
- Do use `CopyableIdentifier` for every UUID/hash/session/order/correlation ID.
- Do keep polling cadences, mutation guards, and provenance fields byte-identical.
- Do add/expand `data-testid` hooks when renaming classes (tests assert on classes).

**Don't**
- Don't invent backend capabilities, enum values, health states, or metrics; unknowns
  render neutral + raw-in-details and are logged to the decision log.
- Don't render SNAKE_CASE, raw ISO/epoch timestamps, minor-unit money, or full
  identifiers above L3.
- Don't average away subsystem disagreement — surface it (see
  [semantic-state-system.md](semantic-state-system.md#subsystem-disagreement)).
- Don't add entry-chunk weight: all new surfaces lazy (budget: 203 KiB enforced,
  ~0.8 KiB headroom).
- Don't introduce new fonts, new chart libraries, new color hexes outside tokens, or
  new breakpoint values outside the contract.
- Don't make tooltips load-bearing (`title=`-only information is banned; Tooltip
  content must duplicate visible text or be non-essential).
- Don't reorder `laneRegistry.ts` (backend provenance contract) — presentational lane
  order lives in a separate nav-order map.
