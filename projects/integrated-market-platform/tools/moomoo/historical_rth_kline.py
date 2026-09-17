"""Paginated OpenD 1m history kline for a single US equity session day (Lane B)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

_TOOLS_MOOMOO = Path(__file__).resolve().parent
if str(_TOOLS_MOOMOO) not in sys.path:
    sys.path.insert(0, str(_TOOLS_MOOMOO))

from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (
    opend_endpoint,
    opend_is_loopback,
    opend_reachable,
)

from opend_quote_transport import (  # type: ignore[import-not-found]
    MOOMOO_AUTH_FAILURE,
    MOOMOO_PROTOCOL_ERROR,
    MOOMOO_SDK_MISSING,
    OPEND_NON_LOOPBACK_BLOCKED,
    US_EQUITY_1M_HISTORY_MIN_COUNT,
    _bounded_vendor_msg,
    _provider_code,
    _snapshot_rows,
    load_vendor_sdk,
)

_PAGE_PACE_S = 0.15


def fetch_history_kline_day_paginated(
    symbol: str,
    *,
    session_date: str,
    repository_root: Path | None = None,
    max_count: int = US_EQUITY_1M_HISTORY_MIN_COUNT,
) -> dict[str, Any]:
    """Fetch all 1m kline pages for ``session_date`` on loopback OpenD."""

    del repository_root  # reserved for future registry hooks
    day = str(session_date).strip()
    host, port = opend_endpoint()
    if not opend_is_loopback(host) or not opend_reachable(host=host, port=port):
        return {"reason_code": OPEND_NON_LOOPBACK_BLOCKED, "pages": ()}
    ft = load_vendor_sdk()
    if ft is None:
        return {"reason_code": MOOMOO_SDK_MISSING, "pages": ()}
    code = _provider_code(symbol)
    if not code:
        return {"reason_code": MOOMOO_PROTOCOL_ERROR, "pages": ()}
    ctx = None
    pages: list[dict[str, Any]] = []
    try:
        ctx = ft.OpenQuoteContext(host=host, port=port)
        ret, state = ctx.get_global_state()
        if ret != ft.RET_OK:
            return {
                "reason_code": MOOMOO_PROTOCOL_ERROR,
                "pages": (),
                "vendor_ret_msg": _bounded_vendor_msg(state),
            }
        if not isinstance(state, dict) or not state.get("qot_logined"):
            return {"reason_code": MOOMOO_AUTH_FAILURE, "pages": ()}
        page_index = 0
        page_key: Any = None
        while True:
            request_kwargs: dict[str, Any] = {
                "start": day,
                "end": day,
                "ktype": ft.KLType.K_1M,
                "autype": ft.AuType.QFQ,
                "max_count": max(int(max_count), US_EQUITY_1M_HISTORY_MIN_COUNT),
                "extended_time": True,
                "session": ft.Session.ALL,
            }
            if page_key is not None:
                request_kwargs["page_req_key"] = page_key
            k_ret, data, next_key = ctx.request_history_kline(code, **request_kwargs)
            if k_ret != ft.RET_OK:
                return {
                    "reason_code": MOOMOO_PROTOCOL_ERROR,
                    "pages": tuple(pages),
                    "vendor_ret_msg": _bounded_vendor_msg(data),
                }
            rows = _snapshot_rows(data)
            pages.append(
                {
                    "provider_response_identity": f"{code}:{day}:page:{page_index}",
                    "rows": rows,
                    "provider_gap": len(rows) == 0 and page_index > 0,
                }
            )
            page_index += 1
            if next_key is None or next_key == page_key:
                break
            page_key = next_key
            time.sleep(_PAGE_PACE_S)
        return {"reason_code": None, "pages": tuple(pages)}
    except Exception as exc:  # noqa: BLE001
        return {
            "reason_code": MOOMOO_PROTOCOL_ERROR,
            "pages": tuple(pages),
            "vendor_ret_msg": _bounded_vendor_msg(f"{type(exc).__name__}: {exc}"),
        }
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:  # noqa: BLE001
                pass


__all__ = ["fetch_history_kline_day_paginated"]
