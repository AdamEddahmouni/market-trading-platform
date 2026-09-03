# Order Flow / Market Microstructure Glossary (Deliverable 11)

**Canonical source for microstructure terms in IMP.**

---

## Core terms

### liquidity maker / liquidity taker
A **maker** posts resting liquidity; a **taker** demands immediacy by executing against resting orders.

### aggressor
The party that initiated the trade by taking liquidity. Every trade has both a buyer and a seller; aggressor side indicates who crossed the spread or hit the book.

**Does NOT mean:** more buyers than sellers.

### trade delta / CVD
`signed_volume = +quantity` if buyer-initiated, `-quantity` if seller-initiated.  
`CVD_t = Σ signed_volume`.

**Does NOT mean:** CVD > 0 ⇒ price must rise.

### L1 / L2 / MBP / MBO / DOM
- **L1:** best bid/ask and sizes
- **L2/MBP:** multi-level depth by price
- **MBO:** individual orders with IDs and queue priority
- **DOM:** depth-of-market visualization over book state

### spread / mid
`spread = ask - bid`; `mid = (bid + ask) / 2`.

### microprice
Size-weighted fair price: `(ask × bid_size + bid × ask_size) / (bid_size + ask_size)`.

### queue imbalance (QI)
`(bid_size - ask_size) / (bid_size + ask_size)` at L1. Near-term book-pressure evidence.

### OFI / MLOFI
Order Flow Imbalance — changes in bid/ask liquidity from adds, cancels, and trades. Multiple definitions exist; always specify `ofi_method` and `ofi_version`.

### depth
Resting quantity at price levels. **Displayed depth ≠ all potential liquidity.**

### liquidity withdrawal / replenishment / resiliency
- **Withdrawal:** displayed liquidity disappears without trade
- **Replenishment:** depth reappears after shock
- **Resiliency:** speed/quality of book recovery

### book fragility
Low depth + high cancellation + low replenishment + wide spread + high impact.

### market impact
Price response per unit aggressive flow. Separate raw flow from price response.

### absorption / exhaustion
- **Absorption:** high aggression + weak price progress + opposing replenishment
- **Exhaustion:** aggression remains but progress fails / momentum decays

**Does NOT mean:** hidden whale confirmed.

### hidden liquidity / iceberg
Probabilistic inference only unless feed provides native hidden-order flags.

**Does NOT mean:** iceberg order confirmed from replenishment alone.

### fill probability / adverse selection
- `P(fill | book state, horizon)` for passive orders
- `E(price move against position | passive fill)` for maker risk

### metaorder
Inferred parent-order execution schedule. No participant identity without evidence.

### spoofing
Legal manipulation requires intent. May detect `fleeting_liquidity` or `layering_like_pattern` — never output "SPOOFING CONFIRMED" from heuristics alone.

---

## Misunderstood concepts

| Statement | What it does NOT mean |
|---|---|
| CVD positive | Automatic bullish forecast |
| Large displayed wall | Proven support/resistance |
| Large print | Specific whale identity |
| Order cancellation | Proof of spoofing |
| Bid-heavy DOM | Aggressive buying (resting ≠ aggressive) |
