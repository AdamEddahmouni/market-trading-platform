"""OCT1-09 Paper portfolio experiment service.

Creates, restores, reads and closes the explicit $100,000 simulated-capital
experiment. Every financial number here is a projection of the experiment's
``PaperExecutionLedger``; this module holds no accounting of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..canonical import canonical_bytes, sha256_bytes
from ..clock import monotonic_wall_ns
from ..local_state.paper_experiments import MAX_PAGE, paper_experiment_repository
from ..operating_modes import PAPER_EXECUTION_AUTHORITIES, resolve_execution_authority
from ..paper import experiment as contract
from ..paper.ledger import PaperExecutionLedger

if TYPE_CHECKING:
    from .store import ReplayStore

# A mark-only change is snapshotted at most this often; fills, creation and
# close always snapshot.
MARK_SNAPSHOT_MIN_INTERVAL_NS = 60 * 1_000_000_000
DEFAULT_NAME = "OCT1-09 live-market Paper experiment"


def _ledger_closed(ledger: PaperExecutionLedger) -> bool:
    return any(event["event_type"] == "PaperSessionClosed" for event in ledger.events)


def active_experiment(store: ReplayStore) -> dict[str, Any] | None:
    """The ACTIVE experiment bound to this store's ledger, if any."""
    ledger = store.paper_ledger
    experiment_id = ledger.experiment_id if ledger.is_portfolio_scoped() else None
    if not experiment_id:
        return None
    record = paper_experiment_repository().get(experiment_id)
    if record is None or record["status"] != contract.STATUS_ACTIVE:
        return None
    return record


def restore_active_experiment_ledger() -> tuple[PaperExecutionLedger | None, dict[str, Any] | None]:
    """Rebuild the persisted ACTIVE experiment's ledger from its own events.

    The stored policy (and therefore the $100,000 starting cash) is the
    authority, so the default-cash resume check does not apply and nothing is
    re-seeded. Authority is re-derived from the environment, never granted
    because persistence loaded.
    """
    from ..local_state.startup import ledger_from_session, open_local_state

    local = open_local_state()
    if local is None:
        return None, None
    for record in paper_experiment_repository().list(status=contract.STATUS_ACTIVE, limit=1):
        session = local.load_session(str(record["paper_session_id"]))
        if session is None:
            continue
        ledger = ledger_from_session(
            session,
            local.load_events(str(session["session_id"])),
            local.load_idempotency(str(session["session_id"])),
        )
        return ledger, record
    return None, None


def _load_closed_ledger(record: dict[str, Any]) -> PaperExecutionLedger | None:
    from ..local_state.startup import ledger_from_session, open_local_state

    local = open_local_state()
    if local is None:
        return None
    session = local.load_session(str(record["paper_session_id"]))
    if session is None:
        return None
    ledger = ledger_from_session(session, local.load_events(str(session["session_id"])), {})
    ledger.persist_sink = None
    ledger.execution_authority = "BLOCKED"
    return ledger


def _ledger_for(store: ReplayStore, record: dict[str, Any]) -> PaperExecutionLedger | None:
    if store.paper_ledger.experiment_id == record["experiment_id"]:
        return store.paper_ledger
    return _load_closed_ledger(record)


def _market_data_state(store: ReplayStore, ledger: PaperExecutionLedger) -> str:
    if str(store.data_mode) != str(ledger.data_mode):
        return "MARKET_DATA_UNAVAILABLE"
    if getattr(store, "execution_deferred", False):
        return "EXECUTION_DEFERRED"
    return "AVAILABLE"


def assert_experiment_order_allowed(store: ReplayStore) -> None:
    """Fail closed before preview/submit against an experiment account."""
    ledger = store.paper_ledger
    if not ledger.is_portfolio_scoped():
        return
    if _ledger_closed(ledger) or active_experiment(store) is None:
        raise ValueError("PAPER_EXPERIMENT_CLOSED: no new orders on a closed experiment")
    if str(ledger.execution_mode).upper() != contract.EXPERIMENT_EXECUTION_MODE:
        raise ValueError("EXPERIMENT_EXECUTION_MODE_FORBIDDEN")
    if str(store.data_mode) != str(ledger.data_mode):
        # A live-observational experiment must never trade against replay data.
        raise ValueError(
            "EXPERIMENT_MARKET_DATA_UNAVAILABLE: experiment data mode "
            f"{ledger.data_mode} is not the running data mode {store.data_mode}; execution deferred"
        )


def assert_experiment_instrument_supported(store: ReplayStore, instrument: dict[str, Any]) -> None:
    """The experiment account values share positions only; derivatives are refused, not mis-valued."""
    if not store.paper_ledger.is_portfolio_scoped():
        return
    kind = str(instrument.get("instrument_kind") or "").upper()
    if kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT"}:
        raise ValueError(f"EXPERIMENT_INSTRUMENT_KIND_UNSUPPORTED: {kind} is outside the experiment's equity/ETF scope")


def create_experiment(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    from ..local_state.startup import persist_ledger, persist_ledger_batch
    from ..market_data.live_config import live_internal_simulation_enabled

    requested_mode = str(body.get("execution_mode", contract.EXPERIMENT_EXECUTION_MODE)).upper()
    if requested_mode != contract.EXPERIMENT_EXECUTION_MODE:
        # The experiment is fake money on the internal simulator. LIVE and
        # broker-paper routing are refused, not downgraded.
        raise ValueError(f"EXPERIMENT_EXECUTION_MODE_FORBIDDEN: {requested_mode} is not {contract.EXPERIMENT_EXECUTION_MODE}")
    repo = paper_experiment_repository()
    if active_experiment(store) is not None or (
        repo.connection is not None and repo.list(status=contract.STATUS_ACTIVE, limit=1)
    ):
        raise ValueError("PAPER_EXPERIMENT_ACTIVE: close the active experiment before creating another")
    name = str(body.get("name") or DEFAULT_NAME).strip()[:120] or DEFAULT_NAME
    notes = str(body.get("notes") or "")[:500]

    authority = resolve_execution_authority(requested_mode=contract.EXPERIMENT_EXECUTION_MODE)
    if authority not in PAPER_EXECUTION_AUTHORITIES:
        # Fail closed before anything is written: an experiment that could never trade is not created.
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED: internal Paper simulation is not enabled for this backend")
    if live_internal_simulation_enabled():
        authority = "PAPER_ONLY"

    previous = store.paper_ledger
    if previous.events and not _ledger_closed(previous):
        previous.close_session()
        persist_ledger(previous)
    created_at_ns = monotonic_wall_ns()
    experiment_id = contract.new_experiment_id(name=name, created_at_ns=created_at_ns)
    policy = contract.build_experiment_policy()
    data_provider = "MOOMOO" if store.data_mode == "LIVE_OBSERVATIONAL" else store.data_provider
    ledger = PaperExecutionLedger.open_session(
        replay_session_id=store.session_id,
        instrument_id=contract.EXPERIMENT_SEED_INSTRUMENT,
        symbol=contract.EXPERIMENT_SEED_INSTRUMENT,
        policy=policy,
        execution_mode=contract.EXPERIMENT_EXECUTION_MODE,
        execution_authority=authority,
        data_mode=store.data_mode,
        data_provider=data_provider,
        execution_provider="INTERNAL",
        experiment_id=experiment_id,
    )
    record = contract.build_experiment_record(
        experiment_id=experiment_id,
        name=name,
        created_at_ns=created_at_ns,
        paper_account_id=ledger.paper_account_id,
        paper_session_id=ledger.session_id,
        policy=policy,
        data_mode=store.data_mode,
        data_providers=[data_provider],
        execution_provider="INTERNAL",
        execution_authority=authority,
        source_scope=str(body.get("source_scope") or "US_EQUITY_ETF"),
        notes=notes,
    )
    repo.create(record, status=contract.STATUS_ACTIVE)
    store.paper_ledger = ledger
    ledger.persist_sink = persist_ledger_batch
    persist_ledger(ledger)
    store.execution_deferred = False
    if authority in PAPER_EXECUTION_AUTHORITIES:
        store.execution_mode = contract.EXPERIMENT_EXECUTION_MODE
        store.execution_authority = authority
    record_equity_snapshot(store, trigger="EXPERIMENT_CREATED")
    return {"experiment": experiment_view(store, repo.get(experiment_id))}


def close_experiment(store: ReplayStore, experiment_id: str) -> dict[str, Any]:
    from ..local_state.startup import persist_ledger

    repo = paper_experiment_repository()
    record = repo.get(experiment_id)
    if record is None:
        raise ValueError("EXPERIMENT_NOT_FOUND")
    if record["status"] != contract.STATUS_ACTIVE:
        raise ValueError("EXPERIMENT_ALREADY_CLOSED")
    ledger = store.paper_ledger
    if ledger.experiment_id != experiment_id:
        raise ValueError("EXPERIMENT_NOT_BOUND: the experiment is not the running Paper account")
    # Closing never liquidates. Open exposure or working orders block it.
    if ledger.project_positions():
        raise ValueError("OPEN_POSITIONS_REMAIN: flatten every position before closing the experiment")
    if any(str(o.get("state")) in {"ACTIVATED", "WORKING", "PARTIALLY_FILLED", "REPLACE_PENDING", "REPLACED"} for o in ledger.project_orders()):
        raise ValueError("WORKING_ORDERS_REMAIN: cancel working orders before closing the experiment")
    record_equity_snapshot(store, trigger="EXPERIMENT_CLOSED", force=True)
    valuation = ledger.project_valuation()
    ended_at_ns = monotonic_wall_ns()
    ledger.close_session()
    persist_ledger(ledger)
    ledger.execution_authority = "BLOCKED"
    store.execution_authority = "BLOCKED"
    repo.close(
        experiment_id,
        ended_at_ns=ended_at_ns,
        status=contract.STATUS_CLOSED,
        closing={
            "final_cash_minor": valuation["cash_minor"],
            "final_equity_minor": valuation["equity_minor"],
            "final_realized_pnl_minor": valuation["realized_pnl_minor"],
            "final_total_pnl_minor": valuation["total_pnl_minor"],
            "final_return_bps": valuation["return_bps"],
            "total_commission_minor": valuation["total_commission_minor"],
            "total_fees_minor": valuation["total_fees_minor"],
            "trade_count": len(ledger.project_trades()),
        },
    )
    return {"experiment": experiment_view(store, repo.get(experiment_id))}


def experiment_view(store: ReplayStore, record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    view = {key: value for key, value in record.items() if key != "risk_policy"}
    policy = record["risk_policy"]
    view["risk_limits"] = {
        "max_open_orders": policy["max_open_orders"],
        "max_order_shares": policy["max_order_shares"],
        "max_position_shares": policy["max_position_shares"],
        "policy_version": policy["policy_version"],
    }
    view["bound_to_running_account"] = store.paper_ledger.experiment_id == record["experiment_id"]
    return view


def assumptions_block(record: dict[str, Any]) -> dict[str, Any]:
    costs = record["cost_policy"]
    return {
        "commission_minor_per_share": costs["commission_minor_per_share"],
        "cost_policy_id": costs["cost_policy_id"],
        "execution": "INTERNAL_PAPER_SIMULATION",
        "fee_minor_per_order": costs["fee_minor_per_order"],
        "fill_is_market_truth": False,
        "fill_model_id": record["fill_model_id"],
        "fill_model_registry_id": record["fill_model"]["registry_id"],
        "fill_model_version": record["fill_model"]["simulator_version"],
        "fill_source_capability": record["fill_model"]["source_capability"],
        "participation_cap": f"{costs['participation_cap_numerator']}/{costs['participation_cap_denominator']}",
        "pnl_statement": contract.NOT_A_PROFITABILITY_CLAIM,
        "slippage_model": record["slippage_model"],
        "slippage_statement": record["slippage_statement"],
    }


def boundary_block(store: ReplayStore, ledger: PaperExecutionLedger) -> dict[str, Any]:
    """Data identity and execution identity, recorded independently."""
    return {
        "capital": {"kind": "SIMULATED", "live_capital": False},
        "execution": {
            "execution_authority": ledger.execution_authority,
            "fill_kind": "SIMULATED_FILL",
            "mode": ledger.execution_mode,
            "provider": ledger.execution_provider,
        },
        "market_data": {
            "mode": ledger.data_mode,
            "provider": ledger.data_provider,
            "running_mode": store.data_mode,
            "state": _market_data_state(store, ledger),
        },
    }


def portfolio_blocks(store: ReplayStore) -> dict[str, Any]:
    """Additive ``/paper/portfolio`` blocks for an experiment account."""
    ledger = store.paper_ledger
    if not ledger.is_portfolio_scoped():
        return {"experiment": None}
    record = paper_experiment_repository().get(str(ledger.experiment_id))
    if record is None:
        return {"experiment": None}
    record_equity_snapshot(store, trigger="MARK_UPDATE")
    return {
        "assumptions": assumptions_block(record),
        "boundary": boundary_block(store, ledger),
        "experiment": experiment_view(store, record),
        "valuation": ledger.project_valuation(),
    }


def record_equity_snapshot(store: ReplayStore, *, trigger: str, force: bool = False) -> bool:
    ledger = store.paper_ledger
    if not ledger.is_portfolio_scoped() or not ledger.experiment_id:
        return False
    repo = paper_experiment_repository()
    experiment_id = str(ledger.experiment_id)
    valuation = ledger.project_valuation()
    now_ns = int(valuation["valuation_cutoff_ns"])
    last_sequence = int(ledger.events[-1]["sequence"]) if ledger.events else 0
    material = {
        "cash_minor": valuation["cash_minor"],
        "equity_minor": valuation["equity_minor"],
        "last_event_sequence": last_sequence,
        "marks": [[m["instrument_id"], m["mark_minor"], m["quality"]] for m in valuation["marks"]],
        "quality": valuation["quality"],
        "realized_pnl_minor": valuation["realized_pnl_minor"],
        "unrealized_pnl_minor": valuation["unrealized_pnl_minor"],
    }
    if force:
        # A forced lifecycle row (close) is its own state even when the numbers match the last fill.
        material["lifecycle"] = trigger
    state_hash = sha256_bytes(canonical_bytes(material))
    latest = repo.latest_snapshot(experiment_id)
    if latest is not None and not force:
        if latest["state_hash"] == state_hash:
            return False
        if (
            trigger == "MARK_UPDATE"
            and int(latest.get("last_event_sequence", -1)) == last_sequence
            and now_ns - int(latest["captured_at_ns"]) < MARK_SNAPSHOT_MIN_INTERVAL_NS
        ):
            return False
    return repo.append_snapshot(
        experiment_id,
        state_hash=state_hash,
        captured_at_ns=now_ns,
        payload={
            "cash_minor": valuation["cash_minor"],
            "equity_minor": valuation["equity_minor"],
            "last_event_sequence": last_sequence,
            "marked_position_value_minor": valuation["marked_position_value_minor"],
            "position_value_minor": valuation["position_value_minor"],
            "quality": valuation["quality"],
            "realized_pnl_minor": valuation["realized_pnl_minor"],
            "total_pnl_minor": valuation["total_pnl_minor"],
            "trigger": trigger,
            "unrealized_pnl_minor": valuation["unrealized_pnl_minor"],
        },
    )


def _resolve(store: ReplayStore, experiment_id: str | None) -> dict[str, Any] | None:
    repo = paper_experiment_repository()
    if experiment_id:
        record = repo.get(experiment_id)
        if record is None:
            raise ValueError("EXPERIMENT_NOT_FOUND")
        return record
    current = active_experiment(store)
    if current is not None:
        return current
    bound = store.paper_ledger.experiment_id
    return repo.get(bound) if bound else None


def current_experiment_payload(store: ReplayStore) -> dict[str, Any]:
    record = active_experiment(store)
    if record is None:
        return {"experiment": None, "state": "NO_ACTIVE_PAPER_EXPERIMENT"}
    ledger = store.paper_ledger
    return {
        "assumptions": assumptions_block(record),
        "boundary": boundary_block(store, ledger),
        "experiment": experiment_view(store, record),
        "state": "ACTIVE",
        "valuation": ledger.project_valuation(),
    }


def experiment_payload(store: ReplayStore, experiment_id: str) -> dict[str, Any]:
    record = _resolve(store, experiment_id)
    ledger = _ledger_for(store, record) if record else None
    payload: dict[str, Any] = {"experiment": experiment_view(store, record)}
    if record and ledger is not None:
        payload["assumptions"] = assumptions_block(record)
        payload["boundary"] = boundary_block(store, ledger)
        payload["positions"] = ledger.project_positions()
        payload["valuation"] = ledger.project_valuation()
    return payload


def list_experiments_payload(store: ReplayStore, *, limit: int = 25) -> dict[str, Any]:
    repo = paper_experiment_repository()
    page = min(max(int(limit), 1), MAX_PAGE)
    current = active_experiment(store)
    return {
        "active_experiment_id": current["experiment_id"] if current else None,
        "experiments": [experiment_view(store, record) for record in repo.list(limit=page)],
        "page_size": page,
        "total_count": repo.count(),
    }


def trades_payload(
    store: ReplayStore,
    *,
    experiment_id: str | None = None,
    cursor: str | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """Newest-first trade page; ``cursor`` is the last returned fill id."""
    record = _resolve(store, experiment_id)
    page = min(max(int(limit), 1), MAX_PAGE)
    if record is None:
        return {"experiment_id": None, "next_cursor": None, "page_size": page, "total_count": 0, "trades": []}
    ledger = _ledger_for(store, record)
    trades = list(reversed(ledger.project_trades())) if ledger is not None else []
    start = 0
    if cursor:
        ids = [trade["fill_id"] for trade in trades]
        if cursor not in ids:
            raise ValueError("TRADE_CURSOR_INVALID")
        start = ids.index(cursor) + 1
    rows = trades[start : start + page]
    more = start + page < len(trades)
    return {
        "experiment_id": record["experiment_id"],
        "next_cursor": rows[-1]["fill_id"] if rows and more else None,
        "page_size": page,
        "total_count": len(trades),
        "trades": rows,
    }


def equity_history_payload(
    store: ReplayStore,
    *,
    experiment_id: str | None = None,
    before: int | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    record = _resolve(store, experiment_id)
    page = min(max(int(limit), 1), MAX_PAGE)
    if record is None:
        return {"experiment_id": None, "next_before": None, "page_size": page, "snapshots": [], "total_count": 0}
    repo = paper_experiment_repository()
    rows = repo.snapshots(record["experiment_id"], limit=page, before=before)
    total = repo.snapshot_count(record["experiment_id"])
    oldest = rows[-1]["snapshot_id"] if rows else None
    return {
        "experiment_id": record["experiment_id"],
        "initial_capital_minor": record["initial_capital_minor"],
        "next_before": oldest if rows and len(rows) == page and oldest and oldest > 1 else None,
        "page_size": page,
        "snapshots": rows,
        "total_count": total,
    }
