"""The real ``run_ui_api.py --collect-only`` child with synthetic provider transports.

Run as a script by tests and the overnight rehearsal. Before the entry point
starts, the vendor transports are replaced by the synthetic ones in
``pf01_synthetic_providers`` and every socket use is logged and refused, so the
collector lifecycle, supply, runtimes, admission, writer and news worker are
the production code while no provider can be reached.

Control (all optional, read from the environment):
  PF01_SYNTHETIC_DIR       folder for ``counts.json`` (and ``counts-<pid>.json``), ``network.log`` and command files
  PF01_SYNTHETIC_RATE      synthetic observations per stream per second (default 5)
  PF01_SYNTHETIC_NEWS      1 = serve RSS items from memory instead of leaving RSS disabled
Command files created in that folder are consumed once: ``drop-opend``,
``restore-opend``, ``drop-kraken``, ``refuse-kraken``, ``crash``.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / 'src'), str(ROOT)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

CONTROL = Path(os.environ.get('PF01_SYNTHETIC_DIR') or '.').resolve()
RATE = float(os.environ.get('PF01_SYNTHETIC_RATE', '5'))


def deny_network(event: str, args: tuple) -> None:
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.sendto', 'socket.gethostbyname'}:
        with (CONTROL / 'network.log').open('a', encoding='utf-8') as log:
            log.write(f'{event} {args[1:] if len(args) > 1 else args}\n')
        raise PermissionError('PF01_SYNTHETIC_NETWORK_DENIED')


def main() -> int:
    sys.addaudithook(deny_network)
    from unittest.mock import patch

    from market_platform_foundation.crypto_market.kraken_stream import KrakenStreamRuntime
    from market_platform_foundation.ui_api import screener_crypto
    from tests.support.pf01_synthetic_providers import KRAKEN_PAIRS, SyntheticKraken, SyntheticOpenD

    opend, venue = SyntheticOpenD(), SyntheticKraken(slice_seconds=0.05)
    opend.install()
    stream = KrakenStreamRuntime(resolve=KRAKEN_PAIRS.get, connect=venue.connect)
    patch.object(screener_crypto, '_stream_runtime',
                 lambda: stream if os.environ.get('IMP_CRYPTO_LIVE') == '1' else None).start()
    if os.environ.get('PF01_SYNTHETIC_NEWS') == '1':
        from market_platform_foundation.news.rss_feeds import FEEDS, RssNewsSource
        from market_platform_foundation.ui_api import screener_news
        from market_platform_foundation.ui_api.screener_news import ScreenerNewsService

        polls = {'count': 0}

        def http(url, headers, timeout):
            feed = next(feed.id for feed in FEEDS if feed.url == url)
            polls['count'] += 1
            item = f'{feed}-{polls["count"]}'.encode()
            return (b'<?xml version="1.0"?><rss version="2.0"><channel><item><title>' + item + b' headline</title>'
                    b'<link>https://example.test/' + item + b'</link><guid>' + item + b'</guid></item></channel></rss>')

        rss_env = {'IMP_NEWS_RSS_LIVE': '1', 'SEC_USER_AGENT': 'Fixture Collector fixture@example.test'}
        service = ScreenerNewsService(rss=RssNewsSource(fetch=http, env=rss_env.get), finviz=lambda: None,
                                      catalog=lambda _universe: [], synthesizer_factory=lambda: None)
        patch.object(screener_news, 'news_service', lambda: service).start()

    generator_stop = threading.Event()
    writer_ref = [None]
    feed_ref = [None]
    counts = {'moomoo_ticks': 0, 'kraken_trades': 0, 'undelivered': 0, 'started': time.time()}

    def command(name: str) -> bool:
        path = CONTROL / name
        if not path.exists():
            return False
        path.unlink()
        return True

    def _opend_metrics():
        from market_platform_foundation.market_data import live_runtime
        runtime = live_runtime._RUNTIME
        feed_ref[0] = runtime.feed if runtime is not None and runtime.feed is not None else feed_ref[0]
        return feed_ref[0].metrics() if feed_ref[0] is not None else {}

    def save() -> None:
        from market_platform_foundation.market_data.persistence import active_writer
        writer_ref[0] = active_writer() or writer_ref[0]
        snapshot = {**counts, 'opend_sessions': len(opend.contexts), 'kraken_connections': len(venue.connections),
                    'writer_accounting': writer_ref[0].status() if writer_ref[0] is not None else {},
                    'opend_ingest': _opend_metrics(),
                    'kraken_transport': venue.transport_counts(), 'kraken_shutdown': dict(stream._shutdown_status),
                    'count_semantics': {'moomoo_ticks': 'CALLBACK_RETURNED', 'kraken_trades': 'TRANSPORT_ENQUEUED'},
                    'opend_subscribed': sorted(map(list, opend.subscribed())),
                    'kraken_subscribed': sorted(map(list, venue.subscribed())), 'pid': os.getpid()}
        temporary = CONTROL / f'counts.{os.getpid()}.tmp'
        temporary.write_text(json.dumps(snapshot), encoding='utf-8')
        (CONTROL / f'counts-{os.getpid()}.json').write_text(json.dumps(snapshot), encoding='utf-8')
        for _ in range(20):  # a reader may hold the file open for a moment on Windows
            try:
                os.replace(temporary, CONTROL / 'counts.json')
                return
            except PermissionError:
                time.sleep(0.01)

    def generate() -> None:
        saved = 0.0
        next_due = time.monotonic()
        while not generator_stop.is_set():
            if command('crash'):
                save()  # the harness's own counters only; the collector gets no chance to drain
                os._exit(3)  # abrupt: no drain, no lease release
            if command('drop-opend'):
                opend.drop()
            if command('restore-opend'):
                opend.restore()
            if command('drop-kraken'):
                venue.drop()
            if command('refuse-kraken'):
                venue.refuse = {('trade', symbol) for symbol, _, _ in KRAKEN_PAIRS.values()}
            for code, subtype in sorted(opend.subscribed()):
                if subtype == 'TICKER':
                    counts['moomoo_ticks' if opend.push_tick(code) else 'undelivered'] += 1
            for channel, symbol in sorted(venue.subscribed()):
                if channel == 'trade':
                    counts['kraken_trades' if venue.push_trade(symbol) else 'undelivered'] += 1
            if time.time() - saved >= 0.5:
                saved = time.time()
                save()
            next_due = max(next_due + 1 / RATE, time.monotonic())
            delay = max(0, next_due - time.monotonic())
            if delay <= .05:
                time.sleep(delay)  # Windows high-resolution sleep avoids coarse Event.wait rate rounding.
            else:
                generator_stop.wait(delay)

    generator = threading.Thread(target=generate, name='pf01-synthetic-generator', daemon=True)
    generator.start()
    import atexit

    atexit.register(save)  # exact delivery counters after a clean stop
    sys.argv = [str(ROOT / 'tools/ui1/run_ui_api.py'), '--collect-only']
    from tools.ui1 import run_ui_api

    try:
        return run_ui_api.main()
    finally:
        generator_stop.set()
        generator.join(timeout=2)
        save()


if __name__ == '__main__':
    raise SystemExit(main())
