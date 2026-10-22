"""Optional operator-supplied prices. Estimates never mean billed charges or budget authority."""
from __future__ import annotations
import math
from ...market_data.freshness_contract import timestamp


def estimated_cost(price, *, model_id, input_tokens, output_tokens, now):
    if not isinstance(price,dict) or price.get('model_id') != model_id or price.get('currency') != 'USD' or not price.get('source'):
        return None
    cutoff, verified, expiry = (timestamp(x) for x in (now,price.get('verified_at'),price.get('valid_until')))
    if not cutoff or not verified or not expiry or not verified <= cutoff < expiry:
        return None
    rates = [price.get(k) for k in ('input_per_million','output_per_million')]
    if any(type(x) not in (int,float) or not math.isfinite(x) or x < 0 for x in rates):
        return None
    return {'estimated_dollars':round((input_tokens*rates[0]+output_tokens*rates[1])/1000000,6),
            'basis':'ESTIMATED_TOKENS_WITH_OPERATOR_PRICE', 'price_source':price['source'],
            'verified_at':price['verified_at'], 'valid_until':price['valid_until'], 'actual_charges':None}
