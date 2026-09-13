"""Paper-only operator watch/review/dismiss. Does not mutate OpportunityV1.

Ack durability follows the single PD-09 store:

- Persist-on (`IMP_PERSIST_STATE=1` or `IMP_STATE_DIR`): unique rows in
  `opportunity_operator_acks`. Survive process restart.
- Persist-off: process-local `_PROCESS_ACKS` only. This is
  `INTENTIONAL_EPHEMERAL` — durable acks in persist-off mode are
  `NOT_APPLICABLE` because they would require a second store. Campaigns with
  `persistence_required` are preflight-blocked (`PERSISTENCE_DISABLED`).
"""

from __future__ import annotations

from typing import Any

from ..intelligence.opportunity.lifecycle import OperatorLifecycleState
from ..local_state.paths import persistence_enabled
from ..local_state.startup import open_local_state

OPERATOR_ACK_STORAGE_DURABLE = "DURABLE_SQLITE"
OPERATOR_ACK_STORAGE_PROCESS_LOCAL = "PROCESS_LOCAL"

_PROCESS_ACKS: list[dict[str, Any]] = []


def operator_ack_storage() -> str:
    if persistence_enabled():
        return OPERATOR_ACK_STORAGE_DURABLE
    return OPERATOR_ACK_STORAGE_PROCESS_LOCAL


def reset_operator_acks() -> None:
    _PROCESS_ACKS.clear()


def record_operator_ack(
    *,
    summary_id: str,
    opportunity_id: str | None,
    paper_account_id: str,
    action: str,
    created_at_ns: int,
) -> dict[str, Any]:
    ack_action = OperatorLifecycleState(str(action))
    if ack_action not in {
        OperatorLifecycleState.REVIEWED,
        OperatorLifecycleState.WATCHED,
        OperatorLifecycleState.DISMISSED,
    }:
        raise ValueError("OPERATOR_ACK_INVALID")
    record = {
        "summary_id": summary_id,
        "opportunity_id": opportunity_id,
        "paper_account_id": paper_account_id,
        "action": ack_action.value,
        "created_at_ns": created_at_ns,
    }
    repo = open_local_state() if persistence_enabled() else None
    if repo is not None:
        repo.connection.execute(
            """
            INSERT OR IGNORE INTO opportunity_operator_acks(
                summary_id, opportunity_id, paper_account_id, action, created_at_ns
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                summary_id,
                opportunity_id,
                paper_account_id,
                ack_action.value,
                created_at_ns,
            ),
        )
    else:
        _PROCESS_ACKS.append(record)
    return record


def list_operator_acks(*, paper_account_id: str | None = None) -> tuple[dict[str, Any], ...]:
    repo = open_local_state() if persistence_enabled() else None
    if repo is None:
        records = tuple(_PROCESS_ACKS)
        if paper_account_id is None:
            return records
        return tuple(row for row in records if row.get("paper_account_id") == paper_account_id)
    if paper_account_id is None:
        rows = repo.connection.execute(
            """
            SELECT summary_id, opportunity_id, paper_account_id, action, created_at_ns
            FROM opportunity_operator_acks
            ORDER BY created_at_ns ASC
            """
        ).fetchall()
    else:
        rows = repo.connection.execute(
            """
            SELECT summary_id, opportunity_id, paper_account_id, action, created_at_ns
            FROM opportunity_operator_acks
            WHERE paper_account_id=?
            ORDER BY created_at_ns ASC
            """,
            (paper_account_id,),
        ).fetchall()
    return tuple(
        {
            "summary_id": row[0],
            "opportunity_id": row[1],
            "paper_account_id": row[2],
            "action": row[3],
            "created_at_ns": row[4],
        }
        for row in rows
    )


def dismissed_ids() -> set[str]:
    ids: set[str] = set()
    for row in list_operator_acks():
        if row["action"] != OperatorLifecycleState.DISMISSED.value:
            continue
        ids.add(str(row["summary_id"]))
        if row.get("opportunity_id"):
            ids.add(str(row["opportunity_id"]))
    return ids
