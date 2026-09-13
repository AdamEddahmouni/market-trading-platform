# FTEP-V1 Owner Decision Packet

| Field | Value |
| --- | --- |
| **Protocol ID** | `FTEP-V1/0.1.0-PREREG` |
| **Campaign slug** | `FTEP-V1-001` |
| **Manifest status** | **Historical packet.** V1-001 owner resolutions are recorded in the frozen activation manifest (`activation_status=FROZEN`, OD-11 pathway **A**). Catalog: `MANIFEST_FROZEN`; **not** `FROZEN_FOR_ACTIVATION`; SIGNAL_ONLY **not** authorized; **not** `EMPIRICAL_ACTIVE`. |
| **Audit basis** | Agent A re-run (`c4f6ca28`) + first-run inventory (`81265595`) |
| **Cost** | $0 incremental (Paper-only; `safety_constraints.cost_usd: 0`) |

> **Historical OD text.** This packet consolidates **28** Agent A
> `OWNER_DECISION_REQUIRED` inventory rows into **11** irreducible decision
> groups. OD-1…OD-11 resolutions live in the frozen
> [`ACTIVATION_MANIFEST.json`](../../artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json).
> The OD sections below remain the decision worksheet, **not** current campaign
> status. Do **not** mutate the frozen JSON to “update” this packet. Current
> labels: [FTEP_CAMPAIGN_CATALOG.md](FTEP_CAMPAIGN_CATALOG.md). `FTEP-V1/0.1.0-PREREG`
> and frozen `PROTOCOL_REF.json` are hash-bound preregistration artifacts.

## Audit summary

| Classification | Count | Treatment |
| --- | --- | --- |
| `OWNER_DECISION_REQUIRED` | 28 | Consolidated into OD-1 … OD-11 below |
| `SAFE_ENGINEERING_DEFAULT` | 11 | Pre-resolved in manifest `resolved_fields` |
| `DETERMINISTIC_FROM_AUTHORITY` | 6 | Pre-resolved in manifest `resolved_fields` |
| `DEFER_UNTIL_EVIDENCE` | 4 | Not activation-blocking for recorded-intelligence path |

**Top blocker:** FTEP-D002 (OD-1 strategy binding). If owner selects **Option A**
(news-strategy / ES lane), FTEP-D004, D005, D009, and D020 become deterministic
and 14 of 28 owner rows collapse without further input.

**Document conflicts to acknowledge:**

| ID | Conflict |
| --- | --- |
| **C3** | ES futures instrument + US equity RTH calendar (FTEP §6 Option A) — see OD-3 |
| **C5** | No dedicated FTEP row in readiness checklist yet — see OD-11 |

---

## OD-1 — Strategy binding (FTEP-D002)

| Field | Value |
| --- | --- |
| **Decision** | Which frozen strategy policy family governs the first Paper forward-test campaign? |
| **Authoritative constraints** | FTEP-V1 §1 L77–85: "**Decision required before activation. No default is selected.**" Paper-only; Live unreachable. Baseline and AI policy IDs in §2–3 apply only after binding. |
| **Recommended** | **Option A** — Bind to news-strategy-evaluation policies on the `FUTURES_EQUITY_INDEX` / ES lane (`news_deterministic_baseline@1.0.0` vs `news_ai_enhanced@1.0.0`). |
| **Alternatives** | **B** — Single-symbol equity smoke (symbol TBD; requires OD-2 + FTEP-D003 baseline). **C** — Defer until Opportunity Engine candidate schema frozen. |
| **Impact on experimental validity** | Option A inherits lab-validated policy definitions and horizons; narrowest scope for first `ACTUAL_FORWARD` cohort. B/C widen or delay interpretability. |
| **Impact on Paper risk** | All options remain `INTERNAL_SIMULATION`; no Live authority. Option A uses min 1-contract smoke sizing when EXECUTION phase enabled. |
| **Post-freeze mutability** | **Immutable.** Change requires new protocol version + new campaign segment (`MODIFY` disposition). |

**Evidence:** [NEWS_STRATEGY_EVALUATION.md](../architecture/NEWS_STRATEGY_EVALUATION.md) L35–39 (ES lane selected); FTEP-V1 §1 Option A L83.

---

## OD-2 — Universe and instruments (FTEP-D008, FTEP-D011)

| Field | Value |
| --- | --- |
| **Decision** | Which instruments are eligible for locked forward-test decisions? |
| **Authoritative constraints** | FTEP-V1 §4 L142–150, §5 L163: "**No symbol is binding until the activation manifest is signed.**" Continuous futures non-executable (G1/G4). Conditional on OD-1. |
| **Recommended** | **If OD-1 = A:** `lane_id=FUTURES_EQUITY_INDEX`, canonical instrument **`ES`** (not continuous). |
| **Alternatives** | **If OD-1 = B:** single equity symbol (FTEP-D010 / FTEP-SUB-01, e.g. liquid name). **If OD-1 = C:** defer or interim smoke list. **Multi-symbol** (FTEP §4 Option C) requires frozen `ForwardTestSession.universe`. |
| **Impact on experimental validity** | ES aligns with news-strategy lab; P6 BIYA equity precedent does not apply without explicit owner choice (conflict C2). |
| **Impact on Paper risk** | Single-instrument ES limits exposure surface; multi-symbol increases concurrent-position complexity. |
| **Post-freeze mutability** | **Immutable** per campaign segment. |

**Evidence:** NEWS_STRATEGY_EVALUATION L38; FTEP-V1 §5 L157.

---

## OD-3 — Calendar scope (FTEP-D013)

| Field | Value |
| --- | --- |
| **Decision** | Which session window defines eligible decision times? |
| **Authoritative constraints** | FTEP-V1 §6 L176–182. Decisions must respect `source_time_ns` at lock. |
| **Recommended** | **Option A** — US equity regular hours **09:30–16:00 ET** (P6 precedent). |
| **Alternatives** | **B** — Globex ETH for ES (requires explicit liquidity/fill assumptions; FTEP-SUB-04). **C** — Operator-bounded windows in session config. |
| **Impact on experimental validity** | **Conflict C3:** ES trades outside RTH; RTH-only calendar may exclude valid ES catalyst windows or misalign session labels. Owner must accept RTH scope explicitly or select Option B. |
| **Impact on Paper risk** | RTH-only reduces session count; ETH extends exposure hours. |
| **Post-freeze mutability** | **Immutable** per segment. |

**Evidence:** P6_SHADOW_RUN_1_PROTOCOL L21; FTEP-V1 §6 Option A L180.

---

## OD-4 — Campaign duration floor (FTEP-D014)

| Field | Value |
| --- | --- |
| **Decision** | Minimum campaign duration before disposition? |
| **Authoritative constraints** | FTEP-V1 §6 L184–190. Custom floor (Option C) must be ≥ A or B; weakening post-hoc forbidden. |
| **Recommended** | **Option C constraint** — satisfy **both** Option A (≥ 5 qualifying sessions, each ≥ 5 min) **and** Option B (≥ 5 distinct trading days). |
| **Alternatives** | **A only** or **B only** if owner accepts reduced dual floor. **Custom** integer floors ≥ A∪B. |
| **Impact on experimental validity** | Dual floor matches EVIDENCE-01A session semantics + EVIDENCE-01 day coverage without auto-binding forecast qualification. |
| **Impact on Paper risk** | Longer calendar spread reduces rush to trade; no capital at risk in SIGNAL_ONLY phase. |
| **Post-freeze mutability** | **Immutable**; weakening forbidden (FTEP §14 L362–363). |

**Evidence:** `evidence01a/types.py` L13–14; EVIDENCE_01 L38–40; FTEP-V1 §6 Option C L190.

---

## OD-5 — Candidate generation cadence (FTEP-D017)

| Field | Value |
| --- | --- |
| **Decision** | How often may eligible candidates be generated? |
| **Authoritative constraints** | FTEP-V1 §8 L230–236. Anti-look-ahead: inputs only with `available_time_ns ≤ decision_time_ns`. |
| **Recommended** | **Option A** — Event-driven (news catalyst match per news-strategy lab). |
| **Alternatives** | **B** — Fixed 60-second buckets (P6 precedent). **C** — Hybrid declared in session config. |
| **Impact on experimental validity** | Event-driven matches news-strategy evaluation design; 60s buckets mimic P6 shadow run, not news lab. |
| **Impact on Paper risk** | Event-driven yields sparser decisions; 60s may increase decision count and overlap pressure. |
| **Post-freeze mutability** | **Immutable** per segment. |

**Evidence:** NEWS_STRATEGY_EVALUATION L74–81; FTEP-V1 §8 Option A L234.

---

## OD-6 — First campaign test mode (FTEP-D019)

| Field | Value |
| --- | --- |
| **Decision** | Initial `test_mode` for infrastructure shakedown vs full Paper execution path? |
| **Authoritative constraints** | FTEP-V1 §9 L257–263. Bridge supports `SIGNAL_ONLY` and `EXECUTION`. EXECUTION uses governed Paper preview/submit. |
| **Recommended** | **Option C phased** — Phase 1 **`SIGNAL_ONLY`** shakedown → Phase 2 **`EXECUTION`** after **N = 5** integrity-clean locks (FTEP-ACT-02). |
| **Alternatives** | **A** — `SIGNAL_ONLY` only for entire campaign. **B** — `EXECUTION` from first lock. |
| **Impact on experimental validity** | Phased path separates signal infrastructure validation from execution metrics (FTEP §21 REPEAT L563). |
| **Impact on Paper risk** | SIGNAL_ONLY phase: **zero Paper fills**; EXECUTION phase: min 1-contract smoke sizing. |
| **Post-freeze mutability** | Phase boundary frozen at activation; segment transition requires preregistered N, not ad-hoc. |

**Evidence:** EVIDENCE_01A L132–139 shakedown; FTEP-V1 §9 Option C L263.

---

## OD-7 — Sample minimum floors (FTEP-D025)

| Field | Value |
| --- | --- |
| **Decision** | Exact integer floors copied into activation manifest? |
| **Authoritative constraints** | FTEP-V1 §14 L362–380: proposed table is **PLANNED** until activation; weakening after observing results forbidden. |
| **Recommended** | Adopt §14 proposed integers **verbatim** (see precedent table). |

### Precedent table (proposed → recommended binding)

| Floor | Integer | Precedent |
| --- | --- | --- |
| Locked forward-test decisions (total) | **30** | Between BUILD 26 (10) and EVIDENCE-01 (50) |
| Evaluated decisions (signal-complete) | **15** | EVIDENCE-01 settled floor (25) scaled for Paper scope |
| Distinct trading days | **5** | EVIDENCE-01 / P6 |
| Distinct qualifying sessions | **5** | EVIDENCE-01A |
| EXECUTION-mode decisions (if arm enabled) | **10** | Operational minimum for execution metric stability |
| Per-arm minimum (baseline vs AI) | **10 each** | Paired comparison floor |

| **Alternatives** | Stricter integers only (weakening disallowed). Custom higher floors with documented rationale. |
| **Impact on experimental validity** | Floors gate `KEEP` vs `INSUFFICIENT_SAMPLE`; too low risks underpowered H2 inference. |
| **Impact on Paper risk** | Sample floors affect campaign length, not per-trade sizing. |
| **Post-freeze mutability** | **Immutable**; post-hoc weakening forbidden. |

**Evidence:** FTEP-V1 §14 L367–374.

---

## OD-8 — Primary metric for H2 (FTEP-D026)

| Field | Value |
| --- | --- |
| **Decision** | Single primary metric for AI vs baseline comparison? |
| **Authoritative constraints** | FTEP-V1 §15.1, §17 L478–480: at most **one** primary metric chosen at activation. Statistical test: paired bootstrap CI (pre-resolved FTEP-D027). |
| **Recommended** | **`percentage_return`** — mean/median per-decision return delta (H2). |
| **Alternatives** | **`directional_correct`** (sign test on directional correctness). Cannot select both as primary without new protocol version. |
| **Impact on experimental validity** | Return-based primary aligns with BUILD 19/20 paired-bootstrap precedent; directional metric alone ignores magnitude. |
| **Impact on Paper risk** | Metric choice does not change execution authority. |
| **Post-freeze mutability** | **Immutable** per segment. |

**Evidence:** CHAMPION_CHALLENGER_PROMOTION_V1 L52; FTEP-V1 §15 Option A L404.

---

## OD-9 — Cohort matching key (FTEP-D030)

| Field | Value |
| --- | --- |
| **Decision** | Granularity for baseline vs AI-enhanced cohort alignment? |
| **Authoritative constraints** | FTEP-V1 §16 L449–456. Analysis query frozen before unblinding. Bucket definition depends on OD-5 cadence. |
| **Recommended** | **`(symbol, decision_bucket, evaluation_horizon_ns)`** — default §16 matching key with event-time bucket from catalyst timestamp. |
| **Alternatives** | Finer key (e.g. include catalyst class) if preregistered. Coarser key (symbol + horizon only) if cadence is fixed-interval. |
| **Impact on experimental validity** | Misaligned buckets inflate paired-comparison bias; finer keys reduce match count. |
| **Impact on Paper risk** | None — analysis-time only. |
| **Post-freeze mutability** | **Immutable**; cohort SQL/JSONL query frozen at activation. |

**Evidence:** FTEP-V1 §16 L454.

---

## OD-10 — Campaign identity (FTEP-D031)

| Field | Value |
| --- | --- |
| **Decision** | Accept deterministic `campaign_id` derivation from frozen manifest? |
| **Authoritative constraints** | FTEP-V1 L49: "Deterministic ID from activation manifest." Assigned only at freeze, not while `PENDING_OWNER_DECISIONS`. |
| **Recommended** | **`FTCAMP-{sha256(manifest_fingerprint).lower()}`** — matches `evidence01a/identity.py` `derive_campaign_id` pattern implemented in activation loader. |
| **Alternatives** | Reject algorithm → block freeze until alternative preregistered in protocol revision (not recommended). |
| **Impact on experimental validity** | Stable ID binds sessions/decisions to exact frozen manifest bytes. |
| **Impact on Paper risk** | None — identifier only. |
| **Post-freeze mutability** | **Immutable** once assigned at freeze transition. |

**Evidence:** FTEP-V1 L49; `paper_forward_bridge/activation.py` `derive_campaign_id`.

---

## OD-11 — Activation sign-off (FTEP-D035, FTEP-D037, FTEP-D039)

| Field | Value |
| --- | --- |
| **Decision** | Operator attestation to begin governed empirical Paper forward testing under this manifest? |
| **Authoritative constraints** | FTEP-V1 §23 L623–629: all OPEN DECISION rows resolved; checklist reopened; persistence enabled; shakedown tagged if used. Conflict **C5**: checklist has no FTEP row yet. |
| **Recommended** | **Sign all recommended OD-1 … OD-10 defaults**, set `paper_account_id`, reopen forward-validation checklist for FTEP-V1, append WORK_LOG activation entry, transition manifest → `FROZEN`. |
| **Alternatives** | **Defer** — leave manifest `PENDING_OWNER_DECISIONS` (no empirical locks). **Partial sign** — invalid; fail-closed preflight rejects. |
| **Impact on experimental validity** | Sign-off is the gate between preregistration and `ACTUAL_FORWARD` evidence class. |
| **Impact on Paper risk** | Sign-off authorizes Paper session creation only after preflight `READY`; Live still unreachable. |
| **Post-freeze mutability** | Sign-off timestamp recorded; material changes require new activation version. |

**Sub-items:**

| ID | Action |
| --- | --- |
| FTEP-D035 | Accept `ACTIVATION_MANIFEST.json` + artifact tree as canonical binding |
| FTEP-D037 | Reopen / add FTEP-V1 row in `FORWARD_VALIDATION_READINESS_CHECKLIST.md` |
| FTEP-D039 | Operator runbook acknowledgment + WORK_LOG entry at freeze |

---

## Minimal activation path (recommended)

If owner accepts all recommended choices:

1. **OD-1 = A** (news-strategy ES lane)
2. **OD-2 … OD-7** = recommended defaults (pre-populated in manifest)
3. **OD-8 = `percentage_return`**
4. **OD-9** = default §16 matching key
5. **OD-10** = accept SHA-256 campaign_id derivation
6. **OD-11** = sign-off + `paper_account_id` + checklist reopen

No other owner choices required for first **SIGNAL_ONLY** shakedown segment.

## Conditional owner items (only if non-recommended paths)

| Trigger | Additional decisions |
| --- | --- |
| OD-1 = B | FTEP-D003 baseline policy, FTEP-D010 symbol (FTEP-SUB-01) |
| OD-1 = C | Defer or interim protocol (FTEP-SUB-03) |
| OD-3 = B | FTEP-SUB-04 Globex fill assumptions |
| OD-5 = B | Redefine `decision_bucket` for 60s cadence |
| OD-6 = B from start | Full EXECUTION from lock 1 (higher Paper surface) |
| FTEP-D007 | Optional `news_naive_reference@1.0.0` third arm (default: exclude) |

## Pre-resolved fields (not owner decisions)

See manifest `resolved_fields` for FTEP-D003→A path: intelligence recorded-only (D006), overlap forbid (D018), horizons 5m/15m/30m/60m (D020), sizing smoke (D022), slippage Paper-only (D023), stats bootstrap (D027), single primary family (D028), no OE linkage (D029), persistence required (D034), artifact paths (D036).

## Safety envelope (non-negotiable)

- **Paper-only** — `INTERNAL_SIMULATION`; Live brokers unreachable
- **$0 incremental cost** — recorded intelligence; no paid APIs
- **No empirical claims** — status remains `NOT YET EMPIRICAL EVIDENCE` until governed locks under `FROZEN` manifest
- **No post-hoc floor weakening**

## Artifact links

| Artifact | Path |
| --- | --- |
| Activation manifest | [`artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json`](../../artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json) |
| Protocol reference | [`artifacts/forward-test-campaigns/FTEP-V1-001/PROTOCOL_REF.json`](../../artifacts/forward-test-campaigns/FTEP-V1-001/PROTOCOL_REF.json) |
| Protocol document | [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) |
| Agent A audit | Transcript `c4f6ca28` (read-only, 2026-09-10) |
