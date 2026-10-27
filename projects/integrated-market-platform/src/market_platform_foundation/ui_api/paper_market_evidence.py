"""Asset-aware market observations for internal Paper; no execution authority.

Reads existing owned Kraken streams without subscribing or starting a worker.
REST candles retain their actual receipt availability; receipt times are never
relabeled as exchange quote events. Futures bars stay unavailable until a
dated-contract source with verified timing semantics is integrated.
"""
from __future__ import annotations

import time
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

NS = 1_000_000_000
_EQUITY = ('US_EQUITIES', 'US_ETFS')
_INTERVALS = {'1m': 60, '5m': 300, '15m': 900}


def _timestamp(value):
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return int(parsed.timestamp() * NS) if parsed.tzinfo is not None else None
        except (ValueError, OverflowError):
            return None
    return value if type(value) is int and value > 0 else None


def _decimal(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result > 0 else None
    except (InvalidOperation, ValueError):
        return None


def _minor(value, scale):
    number = _decimal(value)
    scaled = number * scale if number is not None else None
    if scaled is None or scaled != scaled.to_integral_value():
        raise ValueError('PRICE_PRECISION_UNAVAILABLE')
    return int(scaled)


def _unavailable(reason, *, source=None):
    return dict(state='UNAVAILABLE', admissible=False, reason=reason, source=source,
                event_time_ns=None, received_time_ns=None, as_of_time_ns=None)


def _empty_bars(reason, *, source=None):
    return dict(state='UNAVAILABLE', reason=reason, source=source, bars=[], available_time_ns=None)


class PaperMarketEvidence:
    """One source read per envelope; provider failures remain asset-local.

    ``instrument`` is a catalog row or flattened canonical/provider mapping.
    It must preserve the provider ticker separately from the canonical id.
    Quote prices include exact decimal strings and integer prices at
    ``price_scale`` (explicit, or derived from the supplied price increment).
    Bar prices use that same scale; all times are UTC integer nanoseconds.
    """

    def __init__(self, *, crypto=None, kraken_runtime=None, multi=None,
                 equity_quote=None, equity_bars=None, clock=time.time,
                 quote_max_age_seconds=15):
        if not 0 < quote_max_age_seconds <= 60:
            raise ValueError('INVALID_QUOTE_MAX_AGE')
        self._crypto, self._runtime, self._multi = crypto, kraken_runtime, multi
        self._equity_quote, self._equity_bars = equity_quote, equity_bars
        self.clock, self._max_age = clock, int(quote_max_age_seconds * NS)

    def _crypto_service(self):
        if self._crypto is None:
            from .screener_crypto import crypto_screener_service
            self._crypto = crypto_screener_service()
        return self._crypto

    def _kraken(self):
        if self._runtime is not None:
            return self._runtime
        from ..crypto_market import kraken_stream
        return kraken_stream._RUNTIME  # Observe only: never create demand here.

    def _multi_service(self):
        if self._multi is None:
            from .screener_multi import multi_screener_service
            self._multi = multi_screener_service()
        return self._multi

    def _identity(self, instrument_id, universe, instrument):
        if isinstance(instrument_id, Mapping):
            instrument = instrument_id
            instrument_id = instrument.get('instrument_id') or (instrument.get('instrument') or {}).get('instrument_id')
        row = dict(instrument or {})
        if instrument is None and universe == 'CRYPTO':
            row, error = self._crypto_service().row_for(instrument_id)
            if row is None:
                raise ValueError(error or 'UNKNOWN_INSTRUMENT')
        elif instrument is None and universe == 'FUTURES':
            row, error = self._multi_service().row_for(instrument_id, universe=universe)
            if row is None:
                raise ValueError(error or 'UNKNOWN_INSTRUMENT')
        row = dict(row)
        nested = row.pop('instrument', {})
        row = {**nested, **row}
        if row.get('instrument_id') not in (None, instrument_id):
            raise ValueError('INSTRUMENT_IDENTITY_MISMATCH')
        row['instrument_id'] = instrument_id
        return str(instrument_id), row

    @staticmethod
    def _scale(row, universe):
        scale = row.get('price_scale')
        if scale is None:
            tick = _decimal(row.get('price_increment') or row.get('tick_size'))
            if tick is not None:
                scale = 10 ** max(0, -tick.normalize().as_tuple().exponent)
            elif universe in _EQUITY or universe == 'FUTURES':
                scale = 100
        if type(scale) is not int or scale < 1 or scale > 10 ** 12 or str(scale).strip('0') != '1':
            raise ValueError('PRICE_PRECISION_UNAVAILABLE')
        return scale

    def _clock_check(self, event, received, now):
        if event is None or received is None:
            return 'QUOTE_CLOCK_UNAVAILABLE'
        if event > received or received > now:
            return 'QUOTE_FUTURE_CLOCK'
        if now - event > self._max_age or now - received > self._max_age:
            return 'QUOTE_STALE'
        return None

    @staticmethod
    def _prices(last, bid, ask, scale, *, event, received, source, **extra):
        prices = [_decimal(value) for value in (last, bid, ask)]
        if any(value is None for value in prices) or prices[1] >= prices[2]:
            return _unavailable('QUOTE_PRICES_UNAVAILABLE_OR_CROSSED', source=source)
        try:
            values = [_minor(value, scale) for value in prices]
        except ValueError as exc:
            return _unavailable(str(exc), source=source)
        return dict(state='LIVE', admissible=True, reason=None, source=source, provider=source,
                    last_price=str(prices[0]), bid=str(prices[1]), ask=str(prices[2]),
                    last_price_minor=values[0], bid_price_minor=values[1], ask_price_minor=values[2],
                    price_scale=scale, event_time_ns=event, as_of_time_ns=event,
                    received_time_ns=received, **extra)

    def _crypto_quote(self, key, row, scale, now):
        runtime = self._kraken()
        if runtime is None:
            return _unavailable('CRYPTO_STREAM_UNAVAILABLE', source='KRAKEN')
        # Snapshot book, trades, connection and acknowledgements under one runtime lock.
        with runtime._lock:
            if runtime.lifecycle.connection_state != 'CONNECTED':
                return _unavailable('CRYPTO_' + str(runtime.lifecycle.connection_state), source='KRAKEN')
            if row.get('status') != 'ONLINE' or row.get('product_type') != 'SPOT':
                return _unavailable('CRYPTO_PRODUCT_UNAVAILABLE', source='KRAKEN')
            from ..crypto_market.kraken_stream import BOOK, TRADES
            activations = [runtime.subscriptions.activated_at(instrument_id=key, capability=cap) for cap in (BOOK, TRADES)]
            if any(value is None for value in activations):
                return _unavailable('CRYPTO_SUBSCRIPTION_UNVERIFIED', source='KRAKEN')
            book = runtime.state.book_engine_for(key)
            if book is None:
                return _unavailable('CRYPTO_BOOK_UNAVAILABLE', source='KRAKEN')
            if not book.book_state_valid or book.is_crossed or not book.asks:
                return _unavailable('CRYPTO_BOOK_INVALID', source='KRAKEN')
            trades = runtime.state.trades_for(key)
            if not trades:
                return _unavailable('CRYPTO_TRADE_UNAVAILABLE', source='KRAKEN')
            trade = max(trades, key=lambda value: value.get('event_time_ns') or 0)
            clocks = [(trade.get('event_time_ns'), trade.get('received_ns')),
                      (book.last_source_time_ns, book.last_received_time_ns)]
            for event, received in clocks:
                reason = self._clock_check(event, received, now)
                if reason:
                    return _unavailable(reason, source='KRAKEN')
            connected = runtime.lifecycle.connected_ns
            if connected is None or any(received < connected for _event, received in clocks) or any(value < connected for value in activations):
                return _unavailable('CRYPTO_PREVIOUS_CONNECTION_EVIDENCE', source='KRAKEN')
            return self._prices(trade.get('price'), book.bids[0].price, book.asks[0].price, scale,
                                event=min(event for event, _received in clocks),
                                received=max(received for _event, received in clocks), source='KRAKEN',
                                trade_event_time_ns=clocks[0][0], book_event_time_ns=clocks[1][0],
                                trade_received_time_ns=clocks[0][1], book_received_time_ns=clocks[1][1],
                                connection_time_ns=connected, checksum='VALID')

    @staticmethod
    def _future_blocker(row, now):
        expiry = row.get('expiry') or row.get('expiration')
        try:
            expiration = date.fromisoformat(expiry)
        except (ValueError, TypeError):
            return 'FUTURES_DATED_CONTRACT_REQUIRED'
        if expiration < datetime.fromtimestamp(now / NS, UTC).date():
            return 'FUTURES_CONTRACT_EXPIRED'
        if not row.get('root') or not row.get('provider_symbol') or 'MAIN' in str(row.get('provider_symbol')).upper():
            return 'FUTURES_DATED_CONTRACT_REQUIRED'
        if row.get('tradability') == 'REFERENCE_ONLY':
            return 'FUTURES_CONTRACT_REFERENCE_ONLY'
        return None

    def _provider_quote(self, key, row, universe, scale, now):
        if universe == 'FUTURES':
            reason = self._future_blocker(row, now)
            if reason:
                return _unavailable(reason, source='MOOMOO_OPEND')
            view = self._multi_service().quote_for(key, universe=universe)
        else:
            reader = self._equity_quote
            if reader is None:
                from .screener_projections import screener_service
                reader = screener_service().quote_for
            view = reader(row.get('market_data_id') or row.get('symbol') or key)
        source = 'MOOMOO_OPEND'
        if view.get('state') != 'LIVE':
            return _unavailable(view.get('reason') or 'QUOTE_' + str(view.get('state')), source=source)
        fields = view.get('fields') or {}
        clocks = []
        for name in ('price', 'bid', 'ask'):
            field = fields.get(name) or {}
            event = _timestamp(field.get('as_of_ns')) or _timestamp(field.get('as_of'))
            # Snapshot reads occur now; an explicit receipt clock, if present, wins.
            received = _timestamp(field.get('received_time_ns')) or _timestamp(view.get('received_time_ns')) or now
            reason = self._clock_check(event, received, now)
            if reason:
                return _unavailable(reason, source=source)
            clocks.append((event, received))
        return self._prices(*(fields.get(name, {}).get('value') for name in ('price', 'bid', 'ask')), scale,
                            event=min(value[0] for value in clocks), received=max(value[1] for value in clocks),
                            source=source, session_state=view.get('session_state', 'UNAVAILABLE'))

    def _quote(self, key, row, universe, scale, now):
        try:
            if universe == 'CRYPTO':
                return self._crypto_quote(key, row, scale, now)
            if universe in (*_EQUITY, 'FUTURES'):
                return self._provider_quote(key, row, universe, scale, now)
            return _unavailable('REFERENCE_ONLY_UNIVERSE' if universe == 'BONDS' else 'UNSUPPORTED_UNIVERSE')
        except Exception:  # noqa: BLE001 — no provider failure can create execution evidence.
            return _unavailable('MARKET_PROVIDER_UNAVAILABLE')

    def _session(self, universe, row, quote, now):
        if universe in _EQUITY:
            from .paper_automation import market_session
            return market_session(now / NS)
        day = datetime.fromtimestamp(now / NS, UTC).date().isoformat()
        if universe == 'CRYPTO':
            runtime = self._kraken()
            label = 'CONTINUOUS' if runtime is not None and runtime.lifecycle.connection_state == 'CONNECTED' else (
                str(runtime.lifecycle.connection_state) if runtime is not None else 'UNAVAILABLE')
            if row.get('status') not in (None, 'ONLINE'):
                label = 'UNAVAILABLE'
        elif universe == 'FUTURES':
            label = quote.get('session_state', 'UNAVAILABLE')
            if label not in ('TRADING', 'CLOSED', 'MAINTENANCE'):
                label = 'UNAVAILABLE'
        else:
            label = 'REFERENCE_ONLY' if universe == 'BONDS' else 'UNAVAILABLE'
        return dict(label=label, trading_day=label in ('CONTINUOUS', 'TRADING'), session_date=day,
                    minutes_to_close=None, early_close_metadata='NOT_APPLICABLE')

    def _bars(self, key, row, universe, timeframe, scope, scale, now):
        if universe == 'FUTURES':
            return _empty_bars('FUTURES_BARS_UNVERIFIED', source='MOOMOO_OPEND')
        if universe not in (*_EQUITY, 'CRYPTO'):
            return _empty_bars('REFERENCE_ONLY_UNIVERSE' if universe == 'BONDS' else 'UNSUPPORTED_UNIVERSE')
        try:
            if universe == 'CRYPTO':
                payload = self._crypto_service().bars(key, timeframe)
                state, reason = payload.get('state'), payload.get('reason')
                received = _timestamp(payload.get('received_at'))
                source = payload.get('source_id') or 'KRAKEN_SPOT_OHLC'
                rows = [dict(start_ns=_timestamp(bar.get('start')), end_ns=_timestamp(bar.get('end')),
                             **{name: bar.get(name) for name in ('open', 'high', 'low', 'close')})
                        for bar in payload.get('bars', [])]
            else:
                reader = self._equity_bars
                if reader is None:
                    from ..market_data.current_bars import current_bars_service
                    reader = current_bars_service().read
                series = reader(row.get('market_data_id') or row.get('symbol') or key, timeframe=timeframe, scope=scope)
                state, reason = series.state, series.provider_reason or series.reason
                received, source = series.received_ns, 'MOOMOO_OPEND_CUR_KLINE_1M'
                rows = [dict(start_ns=bar.start_ns, end_ns=bar.end_ns,
                             **{name: getattr(bar, name) for name in ('open', 'high', 'low', 'close')}) for bar in series.bars]
            if state not in ('CURRENT', 'SESSION_CLOSED'):
                return _empty_bars(reason or 'BARS_UNAVAILABLE', source=source)
            if received is None or received > now or not rows:
                return _empty_bars('BAR_AVAILABILITY_UNVERIFIED', source=source)
            output = []
            previous = None
            for bar in rows:
                start, end = bar['start_ns'], bar['end_ns']
                if start is None or end is None or not start < end <= received or (previous is not None and start < previous):
                    return _empty_bars('BAR_CLOCK_OR_COMPLETION_INVALID', source=source)
                values = {name: _minor(bar[name], scale) for name in ('open', 'high', 'low', 'close')}
                if not values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']:
                    return _empty_bars('BAR_OHLC_INVALID', source=source)
                output.append(dict(bar_id=f'{source}:{key}:{timeframe}:{end}', event_time=start, end_time=end,
                                   available_time=received, **values))
                previous = end
            if universe == 'CRYPTO' and now - rows[-1]['end_ns'] > (_INTERVALS[timeframe] * 2 + 15) * NS:
                return _empty_bars('BARS_STALE', source=source)
            return dict(state=state, reason=reason, source=source, bars=output, price_scale=scale,
                        available_time_ns=received, latest_complete_bar_end_ns=rows[-1]['end_ns'])
        except Exception:  # noqa: BLE001 — malformed/failed providers have no fillable candles.
            return _empty_bars('BARS_UNAVAILABLE')

    def read(self, instrument_id, *, universe, instrument=None, timeframe='1m', scope='EXTENDED'):
        """Return one canonical observation, explicit session and execution blockers."""
        now = int(self.clock() * NS)
        if timeframe not in _INTERVALS:
            raise ValueError('INVALID_PREVIEW_BAR_SCOPE')
        try:
            key, row = self._identity(instrument_id, universe, instrument)
            scale = self._scale(row, universe) if universe in (*_EQUITY, 'CRYPTO', 'FUTURES') else 100
        except ValueError as exc:
            key, row, scale = str(instrument_id), {}, 100
            quote, bars = _unavailable(str(exc)), _empty_bars(str(exc))
        else:
            quote = self._quote(key, row, universe, scale, now)
            bars = self._bars(key, row, universe, timeframe, scope, scale, now)
        session = self._session(universe, row, quote, now)
        blockers = []
        if not quote.get('admissible'):
            blockers.append(quote.get('reason') or 'QUOTE_UNAVAILABLE')
        if bars['state'] not in ('CURRENT', 'SESSION_CLOSED'):
            blockers.append(bars.get('reason') or 'BARS_UNAVAILABLE')
        if session['label'] not in ('CONTINUOUS', 'TRADING', 'REGULAR', 'PREMARKET', 'AFTER_HOURS'):
            blockers.append('MARKET_SESSION_' + session['label'])
        blockers = list(dict.fromkeys(blockers))
        return dict(schema_version='paper-market-evidence/1.0.0', instrument_id=key, universe=universe,
                    observation_time=now, provider=quote.get('source'), price_scale=scale,
                    state='BLOCKED' if blockers else 'READY', reason=blockers[0] if blockers else None,
                    session=session, quote=quote, bars=bars, blockers=blockers)

    def quote(self, instrument_id, *, universe, instrument=None):
        """Read a quote without fetching bars or adding a market subscription."""
        now = int(self.clock() * NS)
        try:
            key, row = self._identity(instrument_id, universe, instrument)
            return self._quote(key, row, universe, self._scale(row, universe), now)
        except ValueError as exc:
            return _unavailable(str(exc))

    def execution_bars(self, instrument_id, *, universe, instrument=None, timeframe='1m', scope='EXTENDED'):
        """Read completed candles without a quote read; availability stays explicit."""
        if timeframe not in _INTERVALS:
            raise ValueError('INVALID_PREVIEW_BAR_SCOPE')
        try:
            key, row = self._identity(instrument_id, universe, instrument)
            return self._bars(key, row, universe, timeframe, scope, self._scale(row, universe), int(self.clock() * NS))
        except ValueError as exc:
            return _empty_bars(str(exc))

    def crypto_trade_bars(self, instrument_id, *, now_ns=None):
        """Fresh Kraken trade prints as one-print execution bars for the internal Paper simulator.

        Each print is one complete bar at its exact venue price and quantity; availability is its local
        receipt. Prints from a previous connection or subscription, out of clock order or older than the
        quote age are omitted, so a missing or stale stream yields no bar and the order gate fails closed.
        Observe only: no subscription is created here.
        """
        now = int(self.clock() * NS) if now_ns is None else now_ns
        runtime = self._kraken()
        if runtime is None:
            return []
        from ..crypto_market.kraken_stream import TRADES
        key = str(instrument_id)
        with runtime._lock:
            connected = runtime.lifecycle.connected_ns
            activated = runtime.subscriptions.activated_at(instrument_id=key, capability=TRADES)
            if runtime.lifecycle.connection_state != 'CONNECTED' or connected is None or activated is None:
                return []
            trades = runtime.state.trades_for(key)
        since = max(connected, activated)
        bars = []
        for trade in trades:
            event, received = trade.get('event_time_ns'), trade.get('received_ns')
            price, quantity = _decimal(trade.get('price')), _decimal(trade.get('quantity'))
            if self._clock_check(event, received, now) or received < since or price is None or quantity is None:
                continue
            value, volume = format(price, 'f'), format(quantity, 'f')
            trade_id = str(trade.get('trade_id'))
            bars.append(dict(available_time=received, event_time=event, instrument_id=key, provider='KRAKEN',
                             source='KRAKEN_TRADE_PRINT', normalized_event_id=f'KRAKEN:{key}:TRADE:{trade_id}',
                             complete=True, volume=volume, volume_basis='VENUE_TRADE_QUANTITY',
                             bar_payload=dict(open=value, high=value, low=value, close=value, volume=volume,
                                              volume_basis='VENUE_TRADE_QUANTITY', complete=True, event_time=event,
                                              provider='KRAKEN', source='KRAKEN_TRADE_PRINT', trade_id=trade_id)))
        bars.sort(key=lambda bar: (bar['available_time'], bar['event_time']))
        return bars

    def session(self, universe, instrument_id=None, *, instrument=None):
        """Provider/venue session facts; crypto/futures never use the equity close."""
        now = int(self.clock() * NS)
        if universe in _EQUITY or instrument_id is None:
            return self._session(universe, instrument or {}, {}, now)
        key, row = self._identity(instrument_id, universe, instrument)
        quote = self._quote(key, row, universe, self._scale(row, universe), now)
        return self._session(universe, row, quote, now)
