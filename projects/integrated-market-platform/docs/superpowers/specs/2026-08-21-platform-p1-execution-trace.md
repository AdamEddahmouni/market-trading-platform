# Interactive execution architecture (P1)

User-originated and strategy-originated orders converge on shared primitives:

```text
OrderIntent
    → evaluate_risk()          [risk/decision.py]
    → BarConservativeSimulator [execution/simulator.py]
    → FillEvent (optional)
    → ledger projection
```

## Interactive path

```text
UI OrderTicket
  → POST /paper/orders/preview | /paper/orders
  → build_user_order_intent()   [paper/contracts.py]
  → execute_order_intent()      [paper/execution.py]
  → PaperExecutionLedger events [paper/ledger.py]
```

Execution bars: `ReplayStore.bars_for_execution()` (forward from replay cursor — no look-ahead).

## Strategy path

```text
run_strategy_evaluation()
  → build_order_intent()        [execution/intent.py]
  → evaluate_risk + simulator   [risk_simulation/evaluation.py]
  → in-memory portfolio ledger
```

Strategy path may include squeeze context and full bar history; interactive path uses cursor-forward bars.

## Parity invariant

`INTERACTIVE_EXECUTION_PARITY` (`tests/platform/test_paper_p1.py`): at the same cutoff and bar window, equivalent direction/qty/instrument semantics produce identical fill quantity, fill price, and order state.

IDs (`intent_id`, `order_id`, `fill_id`) may differ when intent metadata differs — compare execution semantics, not byte-identical hashes.

## Trace / correlation

| ID | Purpose |
|---|---|
| `client_order_id` | UI command identity |
| `idempotency_key` | HTTP retry deduplication |
| `correlation_id` | End-to-end trace anchor (defaults to client_order_id) |
| `intent_id` | Hash of intent body |
| `order_id` | Simulator order hash |
| `fill_id` | Fill event hash |
| `event_id` | Ledger event hash |

Trace resolution: `GET /paper/trace?intent_id=…`
