# Usability Test Script — UX Prototype V0.6

**Status:** `PROPOSED`  
**Duration:** 45–60 minutes  
**Participants:** 1 facilitator, 1–3 users (intermediate market knowledge)  
**Environment:** [prototype/v0/index.html](prototype/v0/index.html) via local server

## Pre-test briefing (2 min)

> This is a **design prototype** with static mock data — not a live trading platform. Think aloud as you work. There are no wrong answers; we're testing the design, not you.

## Tasks

### Task 1 — Find what matters (Flow A)

**Prompt:** You just opened the platform before market open. What deserves your attention right now?

| Measure | Target |
|---|---|
| Time to identify top item | < 15 seconds |
| Correct identification | NVDA state transition OR system quality (both acceptable) |
| Chart wall avoidance | User stays on NOW, doesn't hunt for charts |

**Success criteria:** Names attention card without opening unrelated nav.

---

### Task 2 — Explain why (Flow B)

**Prompt:** NVDA is highlighted. Why is it on your attention feed?

| Measure | Target |
|---|---|
| Path | Uses `Why here?` or `Explain` |
| Completion | Can articulate at least one reason |
| Depth | Optional: reaches Inspector |

**Probe:** "What does WATCH → CONFIRMED mean to you?"  
**Probe:** "How would you verify this isn't just noise?"

---

### Task 3 — Inspect evidence (Flow B depth)

**Prompt:** Show me how you would dig deeper into that NVDA alert.

| Measure | Target |
|---|---|
| Reaches Inspector | Yes |
| Finds provenance or raw | Navigates to PROVENANCE or RAW tab |

---

### Task 4 — Capability boundaries (Flow C partial)

**Prompt:** You want to see institutional accumulation evidence for NVDA. What do you do?

| Measure | Target |
|---|---|
| Finds alignment panel | Yes |
| Recognizes institutional unavailable | Does not assume fake data |
| Alternative path | Clicks Catalysts row or unavailable panel explain |

**Critical fail:** User believes institutional data is showing when panel says UNAVAILABLE.

**Critical fail:** User believes institutional data is showing when panel says UNAVAILABLE.

---

### Task 5 — Contradictory evidence (Flow H partial)

**Prompt:** NVDA shows conflicting signals. How would you investigate the disagreement?

| Measure | Target |
|---|---|
| Notices conflict callout | Yes |
| Opens inspector | Compares Catalysts vs Model evidence |
| Does not conflate with unavailable | Doesn't treat Order Flow as present |

---

### Task 6 — Replay mode (Flow F partial)

**Prompt:** Replay what the platform knew about NVDA at 10:37 AM.

| Measure | Target |
|---|---|
| Enters replay | Via ⌘K command or Replay button |
| Mode clarity | Identifies REPLAY vs LIVE |
| PIT awareness | Notices price/story change at 10:37 |

**Critical fail:** User believes replay data is current live data after entering replay.

---

### Task 7 — Data quality (Flow J)

**Prompt:** The platform shows PARTIAL quality. What can you still trust?

| Measure | Target |
|---|---|
| Notices quality indicator | Context bar or card badge |
| Opens quality detail | Clicks PARTIAL badge or ⌘K → Data quality detail |
| Distinguishes layers | Names OBSERVED vs DERIVED trust difference |

---

### Task 8 — Mobile alert (Flow K partial)

**Prompt:** You received a push notification about NVDA. Open `⌘K` → "Mobile alert: NVDA" (or navigate to `#/now/alert/att-nvda-1`).

| Measure | Target |
|---|---|
| Gets summary in <30s | Mobile drawer shows meaning + alignment |
| Finds next step | Taps Open full workspace or Inspector |
| No chart hunting | Stays in explanation path |

---

### Task 9 — State change timeline (Flow E partial)

**Prompt:** NVDA squeeze state changed to CONFIRMED. Walk through what happened over time.

| Measure | Target |
|---|---|
| Finds transition path | Explain transition or ⌘K timeline |
| Reaches TIMELINE | Inspector TIMELINE tab |
| Identifies changed criteria | Names CVD / liquidity events |

---

### Task 10 — Downstream trace (USED BY)

**Prompt:** You want to know what else in the platform uses the NVDA attention signal. How would you find that?

| Measure | Target |
|---|---|
| Reaches USED BY tab | Inspector on NVDA attention object |
| Names consumers | At least one downstream feature or screener |
| Optional navigation | Uses Open link to screener or NOW |

---

### Task 11 — Discovery path (EXPLORE)

**Prompt:** You want to find symbols with unusual volume today. Use EXPLORE.

| Measure | Target |
|---|---|
| Reaches EXPLORE | Nav or ⌘K → Go to EXPLORE |
| Selects screen | Unusual volume results visible |
| Explains match | Uses **?** Why matched? on NVDA |
| Next step | Opens NVDA cockpit or Inspector |

**Probe:** Switch to "Large insider" screen — what happens?

---

### Task 12 — Keyboard shortcuts

**Prompt:** You forgot the keyboard shortcuts. How would you find them?

| Measure | Target |
|---|---|
| Opens overlay | Press `?` or click **?** in context bar |
| Finds E / I | Locates explain and inspector shortcuts |
| Distinguishes planned | Notes J/K or Space are not yet active |

---

## Post-test questions

1. Was it clear whether data was live or mock?
2. Did the Inspector feel like too much or too little?
3. What would you want on the homepage that isn't here?
4. Did unavailable modules feel honest or frustrating?
5. Rate confidence in understanding NVDA alert (1–5).

## Facilitator notes template

| Task | Time | Path taken | Errors | Quotes |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |
| 9 | | | | |
| 10 | | | | |
| 11 | | | | |
| 12 | | | | |

## Debrief actions

Record findings in [walkthrough-friction-log-2026-08-15.md](walkthrough-friction-log-2026-08-15.md) or new dated log. Update [decisions/README.md](decisions/README.md) if new UX decisions emerge.
