# Research intelligence gap audit

**Lane:** E | **Date:** 2026-09-12

## Inventory

| Capability | State | Evidence |
|---|---|---|
| DECISION-RESEARCH-001 SS family | Offline gate complete | `tools/research/run_decision_research_gate_validation.py` |
| NewsArticleEvent + replay | Fixture verified | Wave A `REC-CANONICAL-NEWS-FIXTURES` |
| Recorded news strategy eval (FTEP-D006) | RECORDED_ARTIFACTS_ONLY | evaluation replay packs |
| Live headline vendors (7 ids) | configured_not_operational | news-data-inventory (foreground) |
| Narrative / motive kernel | PARTIAL per PROGRAM_STATUS | IMP-NARRATIVE-01 future |
| AI assistant | Read-only bounded packs | IMP-AI-01 future |

## Gaps

1. **Live news ingress** for prospective campaigns blocked on Finviz probe + owner policy (WAVE-A-003).
2. **No unified research catalog UI** linking experiment cards → runtime features.
3. **MongoDB intelligence store** optional; cloud uses in-memory — no production research DB on IMP.
4. **Cross-lane fusion** does not replace preregistered research gates.

## Classification

- Offline research path: **ALREADY_COMPLETE**
- FTEP empirical locks: **DEFER_TO_FOREGROUND_LANE**
- Paid news APIs: **NEEDS_EXTERNAL_ACCESS**
