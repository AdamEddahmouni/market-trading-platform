from __future__ import annotations

from typing import TYPE_CHECKING

from .collectors.bundle import CollectorBundle, configure_collector_bundle
from .news_live import get_news_orchestrator
from .session_state import CURRENT_SCREEN_CAP

if TYPE_CHECKING:
    from .session_state import ScreenerSession


def start_collectors_for_session(
    session: ScreenerSession,
    *,
    sec_user_agent: str | None = None,
) -> CollectorBundle:
    """Wire gap-driven collector scheduler to the live screen session."""

    def universe() -> list[str]:
        with session._lock:
            symbols = list(session.states.keys())
        return symbols[:CURRENT_SCREEN_CAP]

    def gap_buckets(symbol: str) -> list[str]:
        return list(session._gap_buckets_by_symbol.get(symbol.strip().upper(), []))

    bundle = CollectorBundle.from_environment(
        universe_fn=universe,
        gap_buckets_fn=gap_buckets,
        on_headlines=lambda sym, items: get_news_orchestrator().register_external_headlines(
            sym, items
        ),
        sec_user_agent=sec_user_agent,
    )
    session.collector_bundle = configure_collector_bundle(bundle)
    bundle.start()
    return bundle


def stop_collectors_for_session(session: ScreenerSession) -> None:
    bundle = session.collector_bundle
    if bundle is not None:
        bundle.stop()
    else:
        from .collectors import get_collector_bundle

        get_collector_bundle().stop()


__all__ = ["start_collectors_for_session", "stop_collectors_for_session"]
