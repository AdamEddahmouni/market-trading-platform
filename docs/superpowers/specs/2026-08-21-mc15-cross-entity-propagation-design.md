# MC15 — Cross-Entity Propagation (fixture-first, experimental)

**Status:** Implemented  
**Spec date:** 2026-08-21  
**Scope:** Propagate admitted donor catalyst/attention/information/diffusion signals to related entities via explicit `EntityLink` edges on BOXL/NVDA fixture graph  
**Prerequisites:** MC2 IMPLEMENTED (entity resolution), MC8 IMPLEMENTED (catalyst), MC9 IMPLEMENTED (attention), MC14 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Extend the entity graph beyond single-name MC outputs. MC15 publishes **separate propagated fields** from donor entities (e.g., NVDA) to a target workspace symbol (BOXL) through admitted link types:

- `ETF_CONSTITUENT` — ETF → constituent (SMH → NVDA in graph fixture)
- `SECTOR_PEER` — sector peer linkage (NVDA → BOXL)
- `SUPPLY_CHAIN` — supply-chain dependency (NVDA → BOXL)

No universal news score. No fusion of catalyst + attention into one number. **Experimental** — not validated for trading.

MC8 still owns catalyst fusion on the donor entity. MC9 still owns attention diffusion math. MC14 still keeps influence and accuracy separate. MC15 does not replace donor-native signals on the target symbol.

## 2. Scoring model (`cross_entity_propagation_v1`)

### A. EntityLink

Admitted fixture rows define directed edges:

```text
link_id, source_entity_id, target_entity_id, link_type, link_weight,
event_time, available_time, expires_time?, ambiguous?, quality_flags?
```

`link_weight` is the attenuation factor (0..1). Missing weight → fail-closed (no propagation row).

### B. Donor signals

Fixture `donor_signals` carry separate donor fields (not fused):

| Field | Source lane |
|---|---|
| `catalyst_strength` | MC8 donor catalyst |
| `attention_level` | MC9 donor attention |
| `information_value` | MC9 donor information value |
| `diffusion_score` | MC9 donor diffusion |

### C. Propagation (per link × donor event)

```
propagated_catalyst_strength = donor.catalyst_strength * link_weight
propagated_attention_level   = donor.attention_level * link_weight
propagated_information_value = donor.information_value * link_weight
propagated_diffusion_score   = donor.diffusion_score * link_weight
```

Missing donor component → that propagated field is `None`; row may still publish other fields. All donor components missing → skip row.

`propagation_id = uuid5(NAMESPACE, "propagation|{link_id}|{source_event_id}|{target}")`

### D. PIT rules

- Exclude links with `available_time > prediction_cutoff`
- Exclude links with `expires_time <= prediction_cutoff` → `PROPAGATION_LINK_STALE`
- Exclude donor signals with `available_time > prediction_cutoff`
- Propagation row `available_time = max(link.available_time, signal.available_time)`
- Direct links only (`target_entity_id == workspace symbol`); no transitive inference in v1

### E. Fail-closed ambiguity

- `ambiguous: true` on a link → **no propagation row** for that link
- Missing `link_weight` → no propagation row
- Never infer link weight from link type defaults in v1

### F. Quality flags

- `ENTITY_LINK_AMBIGUOUS` (on ambiguous link fixture rows)
- `PROPAGATION_SOURCE_UNAVAILABLE` (partial donor fields)
- `PROPAGATION_LINK_STALE` (expired link at cutoff)
- `CROSS_ENTITY_PROPAGATION_EXPERIMENTAL` (always on produced rows)
- `NO_UNIVERSAL_NEWS_SCORE` (always on produced rows — UI doctrine)

## 3. Cross-lane boundary

Publish display/research metadata only when attenuated thresholds are met:

- `PROPAGATED_CATALYST_ELEVATED` when `propagated_catalyst_strength >= 0.50`
- `PROPAGATED_ATTENTION_ELEVATED` when `propagated_attention_level >= 0.40`

Does **not** fuse into SHARED P4. Does **not** replace native MC8/MC9 rows on the target symbol.

## 4. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_nvda_propagation_slice.json` | Entity graph (SMH/NVDA/BOXL) + donor signals + ambiguous/stale adversarial edges |
| `boxl_nvda_propagation_expected.json` | Golden MC15 regression |

## 5. Workspace

- `cross_entity_propagation_available`
- `cross_entity_propagation_producer_id`, `cross_entity_propagation_producer_version`
- `cross_entity_propagation_count`, `entity_link_count`
- `cross_entity_propagation_summaries` with separate `propagated_*` fields
- `cross_entity_propagation_adapter_rows`
- `entity_links` (PIT-eligible admitted edges for target symbol)
- `research_only: true`

## 6. Out of scope

- Live entity graph APIs / supply-chain databases
- Transitive multi-hop propagation trees
- Learned propagation coefficients
- Universal news / context score
- MC16 advanced multi-document LLM synthesis
