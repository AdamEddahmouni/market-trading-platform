# Short-Pressure Confirmation Rule Semantics

This category is structurally separate from momentum. Published short interest retains its
delayed publication/revision lifecycle. Days to cover and short-interest change consume Phase
2C metrics. Borrow fee and availability use explicitly scoped provider observations; their
change rules consume Phase 2C metrics. Units must match the policy exactly.

Unavailable historical records return `UNKNOWN`; insufficient denominator/history returns
`INSUFFICIENT_DATA`; material conflict returns `CONFLICTED`. Zero borrow availability is a
known numeric value. A zero denominator is not coerced to zero days to cover. Mixed providers
cannot silently combine, and FINRA daily short-sale volume is never substituted for published
short interest or a short-pressure rule.

