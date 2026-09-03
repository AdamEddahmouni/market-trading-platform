# MC14 — Social / Author Intelligence (fixture-first, experimental)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Author identity, social influence, and ex-post accuracy as **separate** evidence objects on admitted BOXL social fixtures  
**Prerequisites:** MC1 revision lineage (fixture), MC9 IMPLEMENTED (social attention fail-closed), MC13 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Resolve **MC-D15**: social reach must not be treated as truth. MC14 publishes:

- **Influence** — contemporaneous reach / diffusion proxies (followers, reposts)
- **Accuracy** — ex-post labeled informativeness, only after an admitted outcome `available_time`

High influence never implies high accuracy. No combined “smart social” score. No SHARED P4 fusion. **Experimental** — not validated for trading.

MC9 still owns attention diffusion math. MC10 still owns narrative clustering. MC14 does not own squeeze state or trade EV.

## 2. Scoring model (`author_intelligence_v1`)

### A. Author identity

`author_id = uuid5(NAMESPACE, "author|{platform}|{handle}")`  
Stable across posts. Requires PIT `event_time` / `available_time` on every social row.

### B. Influence (0..1 or None)

```
components = []
if follower_count is not None: components.append(min(1, follower_count / 100000))
if repost_count is not None: components.append(min(1, repost_count / 5000))
influence = mean(components) if components else None
```

Missing both → `None` + `SOCIAL_INFLUENCE_UNAVAILABLE`.

### C. Accuracy (0..1 or None)

Accuracy is visible only when `outcome_available_time <= prediction_cutoff` **and** `labeled_correct` is admitted.

- Missing / future outcome → `None` + `AUTHOR_ACCURACY_UNVALIDATED`
- Never infer accuracy from follower counts
- Outcome time must be **after** the post `available_time` (ex-post)

### D. PIT rules

- Social post rows with `available_time > prediction_cutoff` are excluded
- Document revision V2 from MC1 remains hidden until its `available_time`
- Do not ingest live social APIs (capability boundary)

### E. Quality flags

- `SOCIAL_INFLUENCE_UNAVAILABLE`
- `AUTHOR_ACCURACY_UNVALIDATED`
- `INFLUENCE_NOT_ACCURACY` (always on produced rows)
- `SOCIAL_AUTHOR_EXPERIMENTAL` (always on produced rows)

## 3. Cross-lane boundary

Publish display/research metadata only:

- `SOCIAL_INFLUENCE_ELEVATED` when influence ≥ 0.60
- `AUTHOR_ACCURACY_LOW` when accuracy is known and < 0.50

Does **not** fuse into SHARED P4. Does **not** replace MC9 `SOCIAL_ATTENTION_UNAVAILABLE` on news attention rows. Does **not** claim author skill equals PI5 participant skill.

## 4. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_social_author_slice.json` | Admitted social/author rows + ex-post labels |
| `boxl_social_author_expected.json` | Golden MC14 regression |

## 5. Workspace

- `author_intelligence_available`
- `author_intelligence_producer_id`, `author_intelligence_producer_version`
- `author_intelligence_summaries` with separate `influence_score` and `accuracy_score`
- `research_only: true`

## 6. Out of scope

- Live social / author APIs
- Learned decay coefficients (MC-Q10 remains research)
- Internship Claude scorer as a trade driver
- MC15 / MC16
- Universal social score
