"""Offline replay provider: rebuild snapshots from saved JSON files.

Purpose
-------
Deterministic chain source for demos, CI, and agent ``offline_mode`` without network.

Features / API role
-------------------
``fetch_options_snapshot_replay``, ``list_rich_snapshot_tickers``,
``find_best_snapshot_path``, ``snapshot_from_dict``.

How ``news_momentum_agent`` consumes it
---------------------------------------
When ``options_confirmation.offline_mode`` is true, ``options_client`` merges
``chain.provider: replay`` before ``run_batch``. Evaluation reads the same
``state/raw_snapshots`` tree via ``ENGINE_ROOT``.

Options-specific vs reusable
----------------------------
Reusable file-backed snapshot replay; min-contract filter skips empty placeholders.

Used for demos and tests when no network or Finviz token is available. Reads
from ``state/raw_snapshots/`` and picks the most recent file per ticker that
has at least ``min_contracts`` contracts (skipping empty placeholder files).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from options_engine.data_models import ContractRow, Snapshot
from options_engine.utils import PROJECT_ROOT, load_json


DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "state" / "raw_snapshots"


def _snapshot_dir(settings: Dict[str, Any]) -> Path:
    replay_cfg = settings.get("chain", {}).get("replay", {})
    raw = replay_cfg.get("snapshot_dir", "state/raw_snapshots")
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _min_contracts(settings: Dict[str, Any]) -> int:
    return max(1, int(settings.get("chain", {}).get("replay", {}).get("min_contracts", 20)))


def _contract_from_dict(row: Dict[str, Any]) -> ContractRow:
    return ContractRow(
        contract_symbol=str(row.get("contract_symbol", "")),
        side=str(row.get("side", "unknown")),
        strike=float(row.get("strike", 0.0) or 0.0),
        expiration=str(row.get("expiration", "")),
        implied_volatility=float(row.get("implied_volatility", 0.0) or 0.0),
        volume=float(row.get("volume", 0.0) or 0.0),
        open_interest=float(row.get("open_interest", 0.0) or 0.0),
        bid=float(row.get("bid", 0.0) or 0.0),
        ask=float(row.get("ask", 0.0) or 0.0),
        last_price=float(row.get("last_price", 0.0) or 0.0),
        in_the_money=bool(row.get("in_the_money", False)),
        delta=float(row.get("delta", 0.0) or 0.0),
    )


def snapshot_from_dict(data: Dict[str, Any], as_of: str | None = None) -> Snapshot:
    """Rebuild a Snapshot from a saved JSON dict."""
    contracts = [_contract_from_dict(row) for row in data.get("contracts", []) if isinstance(row, dict)]
    return Snapshot(
        ticker=str(data.get("ticker", "")).upper().strip(),
        as_of=as_of or str(data.get("as_of", datetime.now(timezone.utc).isoformat())),
        spot_price=float(data.get("spot_price", 0.0) or 0.0),
        expirations=list(data.get("expirations", []) or []),
        contracts=contracts,
        data_quality_flags=list(data.get("data_quality_flags", []) or []),
        provider="replay",
    )


def find_best_snapshot_path(ticker: str, settings: Dict[str, Any]) -> Optional[Path]:
    """Return the most recent rich snapshot file for a ticker, or None."""
    directory = _snapshot_dir(settings)
    min_count = _min_contracts(settings)
    prefix = f"{ticker.upper().strip()}_"
    if not directory.exists():
        return None
    candidates = sorted(directory.glob(f"{prefix}*.json"), reverse=True)
    for path in candidates:
        if path.name == ".gitkeep":
            continue
        data = load_json(path, {})
        if not isinstance(data, dict):
            continue
        contracts = data.get("contracts", [])
        if isinstance(contracts, list) and len(contracts) >= min_count:
            return path
    return None


def list_rich_snapshot_tickers(settings: Dict[str, Any]) -> List[str]:
    """Return tickers that have at least one rich snapshot file."""
    directory = _snapshot_dir(settings)
    min_count = _min_contracts(settings)
    if not directory.exists():
        return []
    tickers: List[str] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*_*.json"), reverse=True):
        if path.name == ".gitkeep":
            continue
        ticker = path.stem.rsplit("_", 1)[0].upper()
        if ticker in seen:
            continue
        data = load_json(path, {})
        if not isinstance(data, dict):
            continue
        contracts = data.get("contracts", [])
        if isinstance(contracts, list) and len(contracts) >= min_count:
            seen.add(ticker)
            tickers.append(ticker)
    return sorted(tickers)


def fetch_options_snapshot_replay(
    ticker: str,
    settings: Dict[str, Any],
    as_of: str | None = None,
) -> Snapshot:
    """Load the best saved snapshot for one ticker (offline, no network)."""
    normalized = ticker.upper().strip()
    now_text = as_of or datetime.now(timezone.utc).isoformat()
    path = find_best_snapshot_path(normalized, settings)
    if path is None:
        return Snapshot(
            ticker=normalized,
            as_of=now_text,
            spot_price=0.0,
            provider="replay",
            data_quality_flags=["empty_chain"],
        )
    data = load_json(path, {})
    if not isinstance(data, dict):
        return Snapshot(
            ticker=normalized,
            as_of=now_text,
            spot_price=0.0,
            provider="replay",
            data_quality_flags=["fetch_error"],
        )
    snapshot = snapshot_from_dict(data, as_of=now_text)
    snapshot.provider = "replay"
    if snapshot.spot_price <= 0:
        snapshot.data_quality_flags.append("missing_spot_price")
    if not snapshot.contracts:
        snapshot.data_quality_flags.append("empty_chain")
    return snapshot
