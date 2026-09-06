# Product idea registry (non-authoritative)

This directory is a **lookup index** from product-backlog idea ids to optional
experiment-card and outcome/learning references.

It uses OF-03 *shape* (identity, status, refs) only. It is **not** OF-03, does
**not** register capabilities, SOPs, or workflows, and **does not grant**
trading, promotion, paper, live, or any other execution authority.

| File | Role |
|---|---|
| [`manifest.json`](manifest.json) | Declares `non_authoritative: true` |
| [`ideas.json`](ideas.json) | Seeded from [`PRODUCT_BACKLOG.md`](../PRODUCT_BACKLOG.md) |

`experiment_card_hash` / `experiment_card_path` stay null until a hashed card
exists under `evidence/research/experiment-cards/`. Empty refs are allowed.

G1–G6, LIVE-001, and P6 Shadow Run 1 campaign gates stay closed. Listing an
idea here does not open them.
