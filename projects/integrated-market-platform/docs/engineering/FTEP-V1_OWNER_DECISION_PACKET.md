# FTEP-V1 Owner Decision Packet

| Field | Value |
| --- | --- |
| **Protocol ID** | `FTEP-V1/0.1.0-PREREG` |
| **Campaign slug** | `FTEP-V1-001` |
| **Manifest status** | `PENDING_OWNER_DECISIONS` |
| **Audit basis** | Agent A re-run (`c4f6ca28`) |
| **Classification** | `PLANNED` / `PRE-REGISTERED` / **NOT YET EMPIRICAL EVIDENCE** |

> **This packet is not evidence.** It records owner choices required before the
> activation manifest can transition from `PENDING_OWNER_DECISIONS` to `FROZEN`.
> Paper-only, $0 cost, no Live execution authority.

## Purpose

Resolve [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md)
OPEN DECISION rows into a signed activation manifest at
`artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json`.

Agent A classified **28 inventory rows** across the protocol and activation
prerequisites:

| Classification | Count |
| --- | --- |
| `DETERMINISTIC_FROM_AUTHORITY` | 6 |
| `SAFE_ENGINEERING_DEFAULT` | 11 |
| `OWNER_DECISION_REQUIRED` | 9 (3 minimal path; 6 full packet if non-default paths) |
| `DEFER_UNTIL_EVIDENCE` | 4 |

If the owner signs the **minimal path** below, **14 of 28** rows require no
further owner input beyond the three binding choices.

---

## Minimal path (recommended)

Three owner signatures unblock the first `SIGNAL_ONLY` shakedown segment when
combined with pre-resolved safe/deterministic defaults in the manifest skeleton.

### FTEP-OD-01 — Strategy binding

| Field | Value |
| --- | --- |
| **Location** | FTEP-V1 §1 (L77–85) |
| **Classification** | `OWNER_DECISION_REQUIRED` |
| **Recommended** | **Option A** — news-strategy ES lane |

| Option | Description | Evidence |
| --- | --- | --- |
| **A** (recommended) | Bind first campaign to news-strategy-evaluation policies (`FUTURES_EQUITY_INDEX` / ES lane) | [NEWS_STRATEGY_EVALUATION.md](../architecture/NEWS_STRATEGY_EVALUATION.md) L35–39 selects ES lane; baseline `news_deterministic_baseline@1.0.0` and AI `news_ai_enhanced@1.0.0` frozen in FTEP-V1 §2–3 |
| B | Single-symbol equity smoke protocol (symbol TBD) | FTEP-V1 §1 Option B; requires OD-02 baseline + FTEP-SUB-01 symbol |
| C | Defer until Opportunity Engine candidate schema frozen | FTEP-V1 §1 Option C; blocks campaign start |

**Impacts if A selected:**

- OD-02 (baseline if B/C) → resolved as `news_deterministic_baseline@1.0.0`
- OD-04 (universe) → `FUTURES_EQUITY_INDEX` / `ES`
- OD-05 (instruments) → ES canonical (non-continuous)
- OD-12 (horizons) → 5m / 15m / 30m / 60m per strategy-eval lab
- No FTEP-SUB-01/03 required for first segment

**Blocks:** All activation — gates baseline, universe, horizons, and policy pinning.

---

### FTEP-ACT-01 — H2 primary metric

| Field | Value |
| --- | --- |
| **Location** | FTEP-V1 §15 (L397–398), §17 (L478) |
| **Classification** | `OWNER_DECISION_REQUIRED` |
| **Recommended** | `percentage_return` |

| Option | Description | Evidence |
| --- | --- | --- |
| **`percentage_return`** (recommended) | Primary H2 comparison on mean/median per-decision return delta | FTEP-V1 §15.1 L397–398; BUILD 19/20 paired-bootstrap precedent ([CHAMPION_CHALLENGER_PROMOTION_V1.md](CHAMPION_CHALLENGER_PROMOTION_V1.md) L52) |
| `directional_correct` | Sign test on directional correctness | FTEP-V1 §15 Option B L405 |

**Impacts:**

- Exactly **one** primary metric frozen at activation (OD-18 deterministic: single-primary-only)
- Secondary metrics remain descriptive unless preregistered in manifest secondary family

**Blocks:** Activation manifest §23 checklist item "Primary metric and multiple-testing option selected".

---

### FTEP-ACT-03 — Readiness checklist reopen

| Field | Value |
| --- | --- |
| **Location** | FTEP-V1 §23 (L623); [FORWARD_VALIDATION_READINESS_CHECKLIST.md](FORWARD_VALIDATION_READINESS_CHECKLIST.md) L34, L46 |
| **Classification** | `OWNER_DECISION_REQUIRED` |
| **Recommended** | Deliberate go — reopen FTEP-V1 campaign row |

| Option | Description | Evidence |
| --- | --- | --- |
| **Reopen** (recommended) | Owner explicitly reopens the FTEP-V1 row in the forward-validation readiness checklist | Checklist: all forward campaigns `DEFERRED` until deliberately reopened; FTEP-V1 §23 L623 |
| Defer | Leave checklist row `DEFERRED` | Blocks first lock |

**Impacts:**

- Permits operator preflight and first `ForwardTestDecision` lock under Paper `INTERNAL_SIMULATION`
- Does **not** authorize Live execution, promotion, or empirical closure claims

**Blocks:** First lock per FTEP-V1 §23.

---

### Minimal path signature block

```
Owner: _________________________  Date: __________

I sign:
  [ ] FTEP-OD-01 = A (news-strategy ES lane)
  [ ] FTEP-ACT-01 = percentage_return
  [ ] FTEP-ACT-03 = reopen readiness checklist

I accept all SAFE_ENGINEERING_DEFAULT and DETERMINISTIC_FROM_AUTHORITY
resolutions listed in § Pre-resolved defaults below.
```

Upon signature, update `ACTIVATION_MANIFEST.json`:
`activation_status` → `FROZEN`, populate `strategy_binding`, `primary_metric`,
`owner_signed_at`, and derive `campaign_id` per OD-19.

---

## Full packet

Six items if the owner selects **non-default** strategy-binding paths. Items 1–3
are always required; items 4–6 are conditional.

| # | Decision ID | Item | Trigger | Options |
| --- | --- | --- | --- | --- |
| 1 | **FTEP-OD-01** | Strategy binding | Always | A news-strategy ES · B single-equity smoke · C defer Opportunity Engine |
| 2 | **FTEP-ACT-01** | H2 primary metric | Always | `percentage_return` · `directional_correct` |
| 3 | **FTEP-ACT-03** | Readiness checklist reopen | Always | Reopen FTEP-V1 row · Defer |
| 4 | **FTEP-SUB-01** | Single equity symbol | OD-01 = B | Liquid single name (TBD at activation) |
| 5 | **FTEP-OD-01** (Option C branch) | Defer vs interim smoke | OD-01 = C | Wait for Opportunity Engine schema · adopt interim Option B smoke |
| 6 | **FTEP-OD-02** / **FTEP-SUB-03** | Baseline policy ID/version | OD-01 ≠ A | Must preregister non-news baseline before any lock |

**Full packet signature block** (use when OD-01 ≠ A):

```
Owner: _________________________  Date: __________

FTEP-OD-01: _______
FTEP-ACT-01: _______
FTEP-ACT-03: _______
(if OD-01=B) FTEP-SUB-01 symbol: _______
(if OD-01=C) interim/defer choice: _______
(if OD-01≠A) FTEP-OD-02 baseline policy: _______
```

---

## Pre-resolved defaults

The following items are populated in `ACTIVATION_MANIFEST.json` → `resolved_fields`
without owner signature. Values marked `recommended_not_binding` in the manifest
apply only after OD-01/ACT-01/ACT-03 are signed.

### DETERMINISTIC_FROM_AUTHORITY (6)

| ID | Resolution | Citation |
| --- | --- | --- |
| **FTEP-OD-12** | Horizons `5m` / `15m` / `30m` / `60m` when OD-01=A | `news_strategy_evaluation/config.py` L14–18 `DEFAULT_HORIZONS`; FTEP-V1 §10 Option A L279 |
| **FTEP-OD-14** | Slippage = Paper internal simulation only; signal metrics gross | FTEP-V1 §12 L318–321, Option A L327 |
| **FTEP-OD-17** | No Opportunity Engine runtime linkage; descriptive metrics only | FTEP-V1 §15.3 L432–433 |
| **FTEP-OD-18** | Single primary metric; secondaries descriptive | FTEP-V1 §17 L478–480, Option A L474 |
| **FTEP-OD-19** | `campaign_id` = SHA-256-derived from frozen activation manifest fields | FTEP-V1 L49; `evidence01a/identity.py` `derive_campaign_id` pattern |
| **FTEP-ACT-05** | `IMP_PERSIST_STATE=1` or `IMP_STATE_DIR` set before first lock | FTEP-V1 §23 L624; [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md) L146–151; PD-09 closed per WORK_LOG |

### SAFE_ENGINEERING_DEFAULT (11)

| ID | Resolution | Citation |
| --- | --- | --- |
| **FTEP-OD-00** | Machine-readable companion: `PROTOCOL_REF.json` + campaign artifact tree | P6 precedent `artifacts/shadow-run-1/P6_SHADOW_RUN_1_PROTOCOL.json`; FTEP-V1 §24 L637–646 |
| **FTEP-OD-03** | Option A — recorded intelligence artifacts only at decision time | [NEWS_STRATEGY_EVALUATION.md](../architecture/NEWS_STRATEGY_EVALUATION.md) L152; FTEP-V1 §3 Option A L127 |
| **FTEP-OD-05** | ES canonical instrument (not continuous) when news lane | NEWS_STRATEGY_EVALUATION L38; FTEP-V1 §5 L157 |
| **FTEP-OD-06** | Option A — US equity RTH 09:30–16:00 ET | FTEP-V1 §6 Option A L180; P6 L21 |
| **FTEP-OD-07** | Require **both** ≥5 qualifying sessions (each ≥5 min) **and** ≥5 distinct trading days | `evidence01a/types.py` L13–14; EVIDENCE-01 L38–40; FTEP-V1 §6 Option C constraint L190 |
| **FTEP-OD-08** | Option A — no regime filter; record tags if present | FTEP-V1 §7 Option A L211; §19 L507–508 |
| **FTEP-OD-09** | Option A — event-driven (news catalyst match) | NEWS_STRATEGY_EVALUATION L74–81; FTEP-V1 §8 Option A L234 |
| **FTEP-OD-10** | Option A — forbid concurrent decisions per symbol while `OBSERVING`/`PAPER_ACTIVE` | FTEP-V1 §8 Option A L242 |
| **FTEP-OD-11** | Option C — `SIGNAL_ONLY` shakedown → `EXECUTION` after N clean locks | FTEP-V1 §9 Option C L263; §21 REPEAT L563; EVIDENCE-01A shakedown L132–139 |
| **FTEP-OD-13** | Phase 1: min 1 contract; Phase 2 EXECUTION: fixed `quantity` at lock | FTEP-V1 §11 L308–310 |
| **FTEP-OD-15** | Adopt §14 proposed floors verbatim (see manifest `sample_floors`) | FTEP-V1 §14 L367–374; weakening forbidden L362–363 |
| **FTEP-OD-16** | Option A — paired bootstrap CI on per-decision return delta | FTEP-V1 §15 Option A L404; CHAMPION_CHALLENGER_PROMOTION_V1 L52 |
| **FTEP-OD-20** | Artifact directory `artifacts/forward-test-campaigns/FTEP-V1-001/` | FTEP-V1 §24 L637–646 |
| **FTEP-ACT-02** | N = **5** integrity-clean locks before EXECUTION segment | EVIDENCE-01A L39–42; FTEP-V1 §9 Option C L263 |
| **FTEP-ACT-07** | Exclude `news_naive_reference@1.0.0` unless explicitly preregistered | FTEP-V1 §3 L117–121 |

> **Note:** OD-15, OD-16, OD-20, ACT-02, ACT-07 are bundled under the 11
> `SAFE_ENGINEERING_DEFAULT` authority count in Agent A (range notation OD-15–16,
> OD-05–07, OD-08–11). All are listed here for manifest completeness.

### DEFER_UNTIL_EVIDENCE (not owner-blocking)

| ID | Resolution | Citation |
| --- | --- | --- |
| FTEP-OD-03→C | Defer live AI arm until `CLAUDE_LIVE_VALIDATION` cleared | FTEP-V1 §3 Option C L129 |
| FTEP-ACT-04 | Live Moomoo/OpenD only if observational ingress required | FORWARD_VALIDATION_READINESS_CHECKLIST L76–82 |
| FTEP-ACT-06 | Manual bridge API/CLI; no EVIDENCE-01B auto-bridge for v1 | PAPER_FORWARD_TESTING_BRIDGE L160 |
| FTEP-ACT-08 | UI route-policy mutations deferred | PAPER_FORWARD_TESTING_BRIDGE L161 |

---

## Safety constraints (non-choosable)

- **Paper-only** — `INTERNAL_SIMULATION`; Live brokers unreachable (FTEP-V1 L31–32)
- **$0 cost** — no external spend
- **No empirical claims** — manifest `PENDING_OWNER_DECISIONS` until owner signs; no `PAPER_OBSERVED` or `ACTUAL_FORWARD` closure until governed locks under frozen manifest
- **No post-hoc floor weakening** — sample minimums frozen at activation (FTEP-V1 §14 L362–363)

---

## Related artifacts

| Artifact | Path |
| --- | --- |
| Protocol | [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) |
| Activation manifest | `artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json` |
| Protocol reference | `artifacts/forward-test-campaigns/FTEP-V1-001/PROTOCOL_REF.json` |
| Agent A audit | Transcript `c4f6ca28` (read-only, 2026-09-10) |
