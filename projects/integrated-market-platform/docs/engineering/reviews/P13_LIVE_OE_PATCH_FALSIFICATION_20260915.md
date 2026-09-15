# P13 adversarial review — isolated live-OE/cockpit candidate patch (2026-09-15)

Reviewer: falsify, do not confirm. No merge. No Live enable. Frozen RTH (`7aade60`, `.rth-operator-20260915`) **not edited**. Patch branch `repair/live-oe-cockpit-state-20260915` **not edited**.

This note lives only on `review/live-oe-patch-20260915` (worktree `.worktrees/review-live-oe-patch-20260915`).

Target: `repair/live-oe-cockpit-state-20260915` HEAD `c43688ed1171e5c64e70d49746507cf8a083f114`  
Worktree: `.worktrees/repair-live-oe-cockpit-state-20260915`  
Base: `7aade60`  
Commits: `8189af4c` as_of/attention honesty; `c4d88ef7` NewsArticleEvent→EventV1+ingress; `c43688ed` ranked READ split, ACK/WATCH still `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`.

Overall: **MUST-FIX-BEFORE-MERGE**. Directionally right on the P12 request-path split and mutation fail-close. Overclaims UI API production EventV1 admission. Leaves July 21 on inspect/`store.as_of_time()`. Would change today's empirical cockpit/discovery runtime if merged mid-session. **Do not merge today.** Isolated candidate may be retained after the must-fix list; it is not a no-op.

---

## Claim table

| Attack / claim | Verdict |
|---|---|
| Live ranked READS still rank BIYA/BOXL/ES **fixtures as current RTH** | **DISPROVEN** for `/opportunities/summary` items and `/attention` current `items`. **MUST-FIX** adjacent leaks: `replay_shelf` still ships 8 fixture cards; `include_ineligible=True` on live rank; inspect `as_of` still July 21. |
| WATCH/DISMISS/acks fire in `LIVE_OBSERVATIONAL` | **DISPROVEN**. **CONFIRMED safe-to-retain.** |
| `as_of` still July 21 when no live quote | **DISPROVEN** for `as_of_context.as_of_time` (`UNAVAILABLE`). **MUST-FIX:** `store.as_of_time()` and inspect EVIDENCE `as_of` remain `2026-07-21T21:01:09Z`. |
| EventV1 is `put_event`'d in `UiApiHandler` | **DISPROVEN.** Helpers + `bind_ui_api_intelligence` only. **MUST-FIX** the production-ingress claim. Plumbing **safe-to-retain** as unused. |
| They deleted `_is_live` entirely | **DISPROVEN.** Helper kept; used for mutations, live `_feed_status`, live attention quarantine. **CONFIRMED safe-to-retain.** |
| Locked tests still require `UNAVAILABLE` on ranked reads (contradicting the split) | **DISPROVEN.** Tests were rewritten to `EMPTY`/`READY`. **CONFIRMED** they updated tests rather than leaving a lock contradiction. |
| Merge mid-session would change today's empirical runtime | **CONFIRMED.** **MUST NOT MERGE TODAY.** |

---

## Attack 1 — can live ranked READS still rank BIYA/BOXL/ES fixtures as current RTH?

**Verdict: DISPROVEN for current OE/attention items. MUST-FIX for shelf, inspect clock, and `include_ineligible`.**

Probe on patch HEAD (ReplayStore loaded, `data_mode=LIVE_OBSERVATIONAL`, `mode=LIVE`, `get_live_runtime` → `None`):

- `instrument_id` still `BIYA`.
- `_attention_rows(store)` → `()`.
- `build_ranked_rows` → `[]`; no BIYA/BOXL/ES.
- `/opportunities/summary` equivalent: `feed_status=EMPTY`, `items=[]`, no `reason`.
- `/attention` current `items=[]` (no `att-replay-context`).
- `replay_shelf` **still present**: 8 fixture cards, including `att-replay-context` and `att-futures-es-imbalance`, labeled `DEMO_REPLAY`.

Two independent quarantines keep fixture attention out of ranked OE: `_all_attention_items` returns `[]` when live, and `_attention_rows` returns `()` when live. Deleting only the old summary early-return would **not** rank July cards **if** those quarantines stay.

Landmines that still fail the “current RTH” bar:

1. `rank_review_rows(..., include_ineligible=_is_live(store))` **includes INELIGIBLE rows in live**. If attention quarantine regresses, ineligible July `NOT_OPPORTUNITY_V1` cards become ranked current book. P12 said deleting the gate without quarantine ranks fixtures; this flag weakens the remaining filter.
2. Live `_feed_status` returns `READY` whenever the repository has rows, even if `as_of_time=UNAVAILABLE`. `test_live_observational_read_ranks_repository_not_fixture_attention` locks that. A seeded `OpportunityV1` is presented as a current ranked book with no live clock.
3. UI `AttentionResponseSchema` does **not** declare `replay_shelf`. Zod strips it. Live Now renders `items` only, so the UI would go empty (not show July cards as current). Raw `/attention` JSON still carries the fixture shelf. Mixed discovery remains a **separate** ranked INVESTIGATE surface (`execution_authority=NONE`) and is not OE.

**CONFIRMED safe-to-retain:** empty live current `items` + empty ranked book without a repository.

**MUST-FIX-BEFORE-MERGE:** do not rank INELIGIBLE live rows; do not advertise `READY` with `UNAVAILABLE` as_of; do not leave fixture cards on an unlabeled client path (UI drops the shelf with no test).

---

## Attack 2 — can WATCH/DISMISS/acks fire in LIVE_OBSERVATIONAL?

**Verdict: DISPROVEN. CONFIRMED safe-to-retain.**

`apply_opportunity_ack` still raises `PermissionError("LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")` before ranking. HTTP `POST /opportunities/{id}/watch|dismiss|review` maps through that helper. Probe: `WATCH_BLOCKED` / `DISMISS_BLOCKED` with that exact reason. Paper path still requires `INTERNAL_SIMULATION` and `not _is_live`.

No Live enable. No mutation authority change.

---

## Attack 3 — is as_of still July 21 when no live quote?

**Verdict: DISPROVEN for `as_of_context.as_of_time`. MUST-FIX remaining July 21 surfaces.**

Probe:

- `store.as_of_time()` = `2026-07-21T21:01:09.000000000Z` (BIYA fixture cursor). **Unchanged.**
- `build_as_of_context` overwrites to `as_of_time=UNAVAILABLE`, `as_of_provenance=UNAVAILABLE`. `2026-07-21` not in that field.
- Inspect EVIDENCE for `inspect:replay:context`: `as_of` **still** `2026-07-21T21:01:09.000000000Z` while quality `state=UNAVAILABLE`.

`_live_receive_ns` uses `quote_for(focus)` then `store.last_source_time_ns`. `LIVE_OBSERVATIONAL` never falls back to fixture identity for focus (`operator_instrument.py`). If focus is `None`, live quotes on other symbols are ignored → `UNAVAILABLE` even with tape. If focus has a quote, merge would switch today's July 21 clock to `LIVE_RECEIVE`. Both are empirical changes.

**CONFIRMED safe-to-retain:** context clock no longer claims the fixture cursor when there is no receive time.

**MUST-FIX-BEFORE-MERGE:** inspect/workspace `store.as_of_time()` leak; document that focus-none + live quotes still yields `UNAVAILABLE`.

---

## Attack 4 — is EventV1 actually `put_event`'d in `UiApiHandler`?

**Verdict: DISPROVEN. MUST-FIX the commit/docs claim. Helpers safe-to-retain.**

`admit_news_article_event` is defined in `news/event_v1_ingress.py` and called from tests only. `UiApiHandler` (`server.py`) has **zero** `admit_news_article_event`, `event_v1_ingress`, or `put_event` references (source probe). Production path:

- `run_ui_api._load_store` calls `bind_ui_api_intelligence` → empty `InMemoryIntelligenceRepository` + `build_production_observation_ingress_router`.
- Nothing in the request path dispatches a `NewsArticleEvent`.
- Detector news branch returns `NEWS_ARTICLE_ADMITTED` only if something already `router.dispatch`'d an EventV1. That does not mint `OpportunityV1`.

Commit `c4d88ef7` (“Admit Finviz news as EventV1 through UI API production ingress”) overstates wiring. Bind is necessary-not-sufficient, which the helper docstring already admits.

**MUST-FIX-BEFORE-MERGE:** strip or rewrite the production-ingress claim; do not merge as if Finviz news is now EventV1 in the cockpit process.

---

## Attack 5 — did they delete `_is_live` entirely?

**Verdict: DISPROVEN they deleted it. CONFIRMED safe-to-retain.**

`opportunity_projections._is_live` still exists and still delegates to `projections.is_live_observational`. Used to: quarantine `_attention_rows`, skip the quality UNREADY gate on live ranked reads, set source `LIVE_OBSERVATIONAL`, pass `include_ineligible`, and block ACK. P12 warning was followed for the helper itself, not for `include_ineligible`.

---

## Attack 6 — do locked tests still require UNAVAILABLE on ranked reads?

**Verdict: DISPROVEN. CONFIRMED they updated the lock.**

`test_opportunity_api.test_live_mode_observational_read_is_empty_without_repository_rows` now asserts `feed_status=EMPTY` and `reason != LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`. Mutation tests still lock that reason on ACK. `test_error_taxonomy` still maps the code to `MODE_BLOCKED` (correct for mutations). No leftover ranked-read lock contradiction found in the patch tree.

New files `tests/ui1/test_live_observational_state.py` and `tests/news/test_finviz_news_event_v1_ingress.py` sit under existing suite globs `tests/ui1/test_*.py` and `tests/news/test_*.py` (directory discover). Not a manifest miss.

---

## Attack 7 — would merge mid-session change today's empirical runtime?

**Verdict: CONFIRMED. MUST NOT MERGE TODAY.**

If this SHA replaced the frozen RTH process today it would change operator-visible behavior without a Live-enable flip:

| Surface | Today's frozen runtime (P12) | This patch |
|---|---|---|
| `/opportunities/summary` | `UNAVAILABLE` / `LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE` before `build_ranked_rows` | `EMPTY` or `READY` from repository |
| `/attention` current items | Fixture replay/MC9/ES/BIYA cards | Empty current `items`; fixture JSON on `replay_shelf` (UI drops it) |
| `/context` `as_of_time` | July 21 BIYA cursor | `UNAVAILABLE` or `LIVE_RECEIVE` from focus quote |
| Mixed discovery empty successful screen | `quality=UNAVAILABLE` / `FINVIZ_SCREEN_UNAVAILABLE` (P12 14:01–14:35 all eight screens `candidate_count=0`) | `EMPTY` / not `FINVIZ_SCREEN_UNAVAILABLE`; mixed status can become `HEALTHY`/`DEGRADED` instead of `UNAVAILABLE` |
| UI API process | No intelligence repo bind | Empty in-memory repo + production ingress router attached at start |

That mixed-discovery EMPTY vs UNAVAILABLE change is **in this candidate** (`engine.py` + `mixed_discovery_projections.py`). It is not a no-op relative to today's empirical Finviz screener loop.

---

## Tests run (patch worktree, no Live enable)

IMP venv Python, `PYTHONPATH=src`, from `.worktrees/repair-live-oe-cockpit-state-20260915/projects/integrated-market-platform`:

```
python -m unittest tests.ui1.test_live_observational_state tests.ui1.test_opportunity_api tests.ui1.test_opportunity_radar_feed tests.news.test_finviz_news_event_v1_ingress tests.platform.test_discovery_p33 tests.platform.test_mixed_discovery
```

**Ran 60, OK.** Tests passing does not make the patch merge-safe today; several passing tests lock the READY-with-UNAVAILABLE and unused-ingress behaviors.

---

## Must-fix before any later merge (not today)

1. Stop claiming `UiApiHandler` / UI API request path admits Finviz news as EventV1.
2. Stop live `include_ineligible=True` unless there is an explicit observational-ineligible shelf, not the current ranked book.
3. Do not return live `feed_status=READY` when `as_of_time=UNAVAILABLE`.
4. Close July 21 on `store.as_of_time()` / inspect EVIDENCE (and any other non-context as_of) or fail-close those payloads in live.
5. Keep mixed-discovery EMPTY vs UNAVAILABLE **out of a mid-session merge**; it changes today's empirical screener honesty independently of OE.

Retainable after that: mutation fail-close, current-item fixture quarantine, context-clock `UNAVAILABLE`, EventV1 mapper as a helper, `_is_live` kept.

**Do not merge. Do not enable Live. Do not edit frozen RTH.**
