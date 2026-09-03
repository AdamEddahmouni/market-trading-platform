from .models import SequenceScope, TradeQuoteRecord


def sequence_compatibility_key(record: TradeQuoteRecord) -> tuple[str, ...] | None:
    if record.sequence_number is None or record.sequence_scope is SequenceScope.UNKNOWN:
        return None
    suffix = {
        SequenceScope.PROVIDER_GLOBAL: (),
        SequenceScope.SYMBOL: (record.symbol,),
        SequenceScope.VENUE: (record.symbol, record.venue or "UNKNOWN"),
        SequenceScope.CHANNEL: (record.sequence_channel or "UNKNOWN",),
        SequenceScope.SESSION: (record.sequence_session or "UNKNOWN",),
    }[record.sequence_scope]
    return (record.provider, record.record_type.value, record.sequence_scope.value, *suffix)

