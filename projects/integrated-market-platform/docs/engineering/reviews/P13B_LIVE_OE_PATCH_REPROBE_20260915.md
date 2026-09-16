# P13b re-probe — live-OE candidate after MUST-FIX (`91b07b4f`)

Reviewer: falsify again. No merge. No Live enable. Frozen RTH `7aade60` **not edited**. Patch branch **not edited**.

Target: `repair/live-oe-cockpit-state-20260915` HEAD `91b07b4f342f8a73dcaa237dc4de1e5c69c86593` (closes P13 leaks on top of `c43688ed`).  
This note: `review/live-oe-patch-20260915` only.

Overall: **SAFE-TO-RETAIN-AFTER-REBASE**. Prior MUST-FIX items are closed on the request-path surfaces they named. Residual gaps they listed do **not** block a later rebase merge. **Do not merge mid-session today** — the branch still changes empirical cockpit/discovery display versus frozen RTH.

Tests: 62 ran, OK (`test_live_observational_state`, `test_opportunity_api`, `test_opportunity_radar_feed`, `test_finviz_news_event_v1_ingress`, `test_discovery_p33`, `test_mixed_discovery`).

---

## Claimed fixes vs re-probe

| Claimed fix | Verdict |
|---|---|
| 1. EventV1 no longer claimed as `UiApiHandler` request-path admission | **CONFIRMED.** Handler has no `admit_news` / `put_event`. Docs, `live_intelligence`, `event_v1_ingress`, `run_ui_api` now say helper-only. Historical commit subject `c4d88ef7` still overclaims; current tree does not. |
| 2. `include_ineligible` gone; live INELIGIBLE not on current book | **CONFIRMED.** `rank_review_rows` has no flag. Denied-family + live clock → `feed_status=EMPTY`, `ranked_n=0`. |
| 3. READY never when as_of UNAVAILABLE; READY needs clock + eligible rows | **CONFIRMED** for `/opportunities/summary`. No clock + seeded OpportunityV1 → `EMPTY`, items `[]`, `build_ranked_rows()=()`. Clock + eligible → `READY`. `_feed_status` UNREADY/`LIVE_AS_OF_UNAVAILABLE` is dead after summary zeros the page; EMPTY is the observed no-clock status. |
| 4. `store.as_of_time()` and inspect EVIDENCE as_of UNAVAILABLE without live receive | **CONFIRMED** on the default live store (both `UNAVAILABLE`; inspect EVIDENCE `as_of=UNAVAILABLE`). **Residual footgun:** if `as_of_time_ns` is set to `prediction_cutoff()`, `store.as_of_time()` becomes July 21 while `display_as_of_time` stays `UNAVAILABLE`. Production `run_ui_api` does not assign `as_of_time_ns`. Follow-on, not a merge block. |
| 5. `replay_shelf` DEMO_REPLAY locked out of current items | **CONFIRMED.** Current `items=[]`; shelf count 8, label `DEMO_REPLAY`, no id overlap. UI `App.tsx` still passes `attentionQuery.data?.items` only. Schema now *can* parse the shelf; it does not merge it into current cards. |
| ACK/WATCH still fail-closed | **CONFIRMED.** `WATCH_BLOCKED` / `DISMISS_BLOCKED` `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`. |

---

## Remaining listed gaps — block merge or follow-on?

| Gap | Merge impact |
|---|---|
| No `UiApiHandler` admit | **Acceptable follow-on.** Documented. Does not block rebase merge. |
| No Finviz auto-fetch | **Acceptable follow-on.** Bind does not fetch. |
| Mixed discovery EMPTY still on this branch | **Acceptable follow-on for OE safety.** It *will* change next-session Finviz empty-screen honesty (`UNAVAILABLE` → `EMPTY`). That is P12 observability, not a live-mutation or fixture-rank leak. Do not merge mid-session; after rebase it is not MUST-FIX-BEFORE-MERGE. |

Other leftovers (workspace bar times still July 21; `fixture_cursor_as_of_time()` still July 21; unused ingress router attached): follow-ons. Not current-book ranking.

---

## Classification

**SAFE-TO-RETAIN-AFTER-REBASE.** Not **MUST-FIX-BEFORE-MERGE**.

Do not merge onto today's frozen RTH process. After session close / rebase onto the approved base, this candidate is retainable. No Live enable.
