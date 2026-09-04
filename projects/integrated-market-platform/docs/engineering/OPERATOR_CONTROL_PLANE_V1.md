# Operator Control Plane (BUILD 31)

BUILD 31 improves the operator's ability to see and control supervised live operations. It does **not** create new trading authority or remove any human approval requirement.

## Core principle

> The operator interface may expose and invoke existing governed actions, but it must never collapse independent safety gates into one convenient action or create a new execution authority of its own.

## Authority mapping

| Operator action | Backend authority | Increases authority? |
| --- | --- | --- |
| Prepare session authorization | `live_canary.authorization.prepare_canary_authorization_preview` | No |
| Authorize session | `live_canary.authorization.authorize_canary_from_human_approval` | Yes |
| Confirm order | `live_canary.confirmation.confirm_order` | No (binds exact order) |
| Activate kill switch | `live_canary.kill_switch_store.KillSwitchStore` | No |
| Revoke authorization | `live_canary.authorization.revoke_authorization` | No |
| Acknowledge incident | `operator_control.commands.acknowledge_incident` | No |
| Submit resolution evidence | `live_canary.incidents.resolve_incident` | No |
| Approve resume | `live_canary.incidents.record_resume_approval` | No |

There is **no** generic `ENABLE LIVE TRADING` action.

## Stale-view protection

High-risk mutations bind a `reviewed_snapshot_id`. The backend compares frozen snapshot fields against current canonical state. If broker health, kill switches, incidents, or authorization changed:

```text
STALE_OPERATOR_VIEW
```

The operator must refresh and re-review.

## Kill switch asymmetry

- **Activation**: one explicit operator action; blocks new submissions.
- **Clearing**: governed; requires resume approval and fresh session authorization.
- Kill switch does **not** auto-liquidate positions.

## Incident workflow

```text
detect → acknowledge → reconcile → resolve → resume review → fresh authorization
```

Acknowledgement does **not** resolve incidents or unblock trading.

## PAPER vs LIVE

- Paper terminal (`/portfolio`, OrderTicket): `PAPER — INTERNAL SIMULATION ONLY`
- Live canary control plane (`/live-canary`): `LIVE CANARY — REAL MONEY — HUMAN CONFIRMATION REQUIRED`

Modes are explicit and must not be confused.

## Incident drills (D01–D15)

Fixture-only qualification. Zero real broker submits/cancels/replaces.

| Drill | Scenario |
| --- | --- |
| D01 | Broker disconnect |
| D02 | Stale status feed |
| D03 | Broker-only order |
| D04 | Local-only order |
| D05 | Ambiguous submission |
| D06 | Unexpected fill |
| D07 | Position mismatch |
| D08 | Partial fill + restart |
| D09 | Global kill switch |
| D10 | Session kill switch |
| D11 | Auth expiry during review |
| D12 | Stale confirmation view |
| D13 | External broker order |
| D14 | Critical incident → resume |
| D15 | Stale confirmation after restart |

## Audit trace

Exact ref lineage:

```text
Forecast → Opportunity → TradeProposal → RiskDecision → BrokerOrderIntent
→ LiveOrderConfirmation → Gate → SubmissionReceipt → Fill → Reconciliation
```

No nearest-time reconstruction.

## API routes (read-only unless POST /canary/command)

- `GET /canary/snapshot`
- `GET /canary/authorization/preview`
- `GET /canary/timeline`
- `GET /canary/reconciliation`
- `GET /canary/incidents`
- `GET /canary/action-inventory`
- `POST /canary/command`

## Limitations

- Single-user/local operator control plane
- No mobile UI
- No external pager/push notifications
- Incident drills fixture-only
- Replace orders uncertified (NOT CERTIFIED)
- No emergency liquidation automation
- Role enforcement remains `MODEL_ONLY_NOT_ENFORCED`

## BUILD 32 boundary

Future work: production telemetry, alert delivery, broker SLO monitoring, incident paging, long-duration supervised operations, disaster recovery — **not** reduced human confirmation.
