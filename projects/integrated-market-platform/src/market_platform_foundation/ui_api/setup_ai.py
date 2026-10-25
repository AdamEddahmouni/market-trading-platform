"""Setup's "Which AI decides" card: the machine-wide AI engine, the paid AI dollar caps, spend, prices, benchmark.

Read-only. It calls no model, starts nothing and never returns a key. Changes go through the existing routes: the
engine through ``POST /screener/news/synthesis/engine`` (refused while automatic passes hold the engine), the caps
through ``POST /operator/config/provider`` with provider ``paid_ai`` (loopback only).
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

SCHEMA = 'setup-ai/1.0.0'
# Written by ``tools/ai_decision_benchmark.py report --publish``.
BENCHMARK_RELATIVE = Path('benchmarks') / 'ai-decision' / 'summary.json'


def _prices(day) -> list[dict[str, Any]]:
    from ..intelligence.inference.paid_prices import price_for
    from ..intelligence.inference.synthesis_engines import ENGINE_SPECS

    rows = []
    for engine in ('anthropic', 'openai', 'gemini'):
        for model, _ in ENGINE_SPECS[engine].models:
            row = price_for(model, day)
            rows.append(dict(engine=engine, model=model, priced=row is not None,
                             input_per_mtok=row.input_per_mtok if row else None,
                             output_per_mtok=row.output_per_mtok if row else None,
                             long_prompt_above=row.long_above if row else None,
                             source=row.source if row else None, checked=row.checked if row else None))
    return rows


def _caps(store: Any) -> dict[str, Any]:
    entry = next((p for p in store.payload()['providers'] if p['provider'] == 'paid_ai'), None)
    fields = {f['key']: f for f in (entry or {}).get('fields', [])}
    return {name: dict(source=fields.get(name, {}).get('source', 'NONE'), editable=fields.get(name, {}).get('editable', True))
            for name in ('IMP_PAID_AI_DAILY_USD', 'IMP_PAID_AI_MONTHLY_USD')}


def setup_ai_status(*, settings: Any = None, value: Callable[[str], str | None] | None = None,
                    cache_dir: Path | None = None, store: Any = None, engine_lock: dict[str, Any] | None = None,
                    now: datetime | None = None) -> dict[str, Any]:
    from ..intelligence.inference.paid_spend import caps_micro, ledger_for, usd
    from ..intelligence.inference.synthesis_engines import resolved_engine
    from ..local_state.external_cache import imp_cache_dir, read_manifest
    from ..news.config import configured_value
    from .operator_config import default_store
    from .screener_news import _default_synthesis_settings

    value = value or configured_value
    cache_dir = cache_dir or imp_cache_dir()
    settings = settings or _default_synthesis_settings()
    current = settings.current()
    daily, monthly = caps_micro(value)
    benchmark = read_manifest(cache_dir / BENCHMARK_RELATIVE)
    return dict(schema_version=SCHEMA, engine=current['engine'], resolved_engine=resolved_engine(current['engine']),
                model=current['model'], source=current['source'], engines=settings.options(),
                caps=dict(daily_usd=usd(daily), monthly_usd=usd(monthly), set=daily > 0 and monthly > 0,
                          settings=_caps(store or default_store())),
                spend=ledger_for(value, cache_dir).status(), prices=_prices((now or datetime.now(UTC)).date()),
                benchmark=benchmark if isinstance(benchmark, dict) else None,
                engine_lock=engine_lock or dict(locked=False, reason=None), secrets_included=False)


__all__ = ['BENCHMARK_RELATIVE', 'SCHEMA', 'setup_ai_status']
