"""XA-01 versioned enumerations — the ONE canonical asset-class vocabulary.

G1 consolidation: every asset-class / instrument-kind authority in IMP routes
through these enums. `paper.contracts.ASSET_CLASSES` is a deprecated
compatibility view over this vocabulary (see `paper/contracts.py`).
"""

from __future__ import annotations

from enum import StrEnum


class XaAssetClass(StrEnum):
    """Canonical structural asset classes.

    One vocabulary: Equity, ETF, Futures, Options, Fixed Income (sovereign debt
    and broader bonds), Commodities, Crypto, FX, Currencies, and index
    benchmarks are all represented here. New domains extend this enum; they do
    not create a second vocabulary.
    """

    EQUITY = "EQUITY"
    ETF_FUND = "ETF_FUND"
    FUTURE = "FUTURE"
    OPTION = "OPTION"
    SOVEREIGN_DEBT = "SOVEREIGN_DEBT"
    BOND = "BOND"
    COMMODITY = "COMMODITY"
    CRYPTO = "CRYPTO"
    FX_PAIR = "FX_PAIR"
    CURRENCY = "CURRENCY"
    INDEX_BENCHMARK = "INDEX_BENCHMARK"


class InstrumentKind(StrEnum):
    """Canonical instrument granularity.

    Kinds partition identities into specific-contract forms (executable where
    the identity says so) and family/reference/aggregate forms (never
    executable). See `xa01.tradability` for the executable-vs-reference rules.
    """

    TRADABLE_SECURITY = "TRADABLE_SECURITY"
    COMMODITY_ECONOMIC = "COMMODITY_ECONOMIC"
    COMMODITY_SPOT = "COMMODITY_SPOT"
    FUTURE_FAMILY = "FUTURE_FAMILY"
    FUTURE_CONTRACT = "FUTURE_CONTRACT"
    CONTINUOUS_SERIES = "CONTINUOUS_SERIES"
    OPTION_CONTRACT = "OPTION_CONTRACT"
    SOVEREIGN_SECURITY = "SOVEREIGN_SECURITY"
    BOND = "BOND"
    CRYPTO_PAIR = "CRYPTO_PAIR"
    CURRENCY_UNIT = "CURRENCY_UNIT"
    FX_PAIR = "FX_PAIR"
    INDEX_BENCHMARK = "INDEX_BENCHMARK"


class Tradability(StrEnum):
    """Explicit executable-vs-reference semantics for an identity.

    - TRADABLE: the identity may legally become an order target.
    - REFERENCE_ONLY: research/analytics/display only; never an order target.
    - SYNTHETIC: derived/aggregate identity; never an order target.
    - CONTINUOUS_SERIES: continuous/synthetic futures series; never an order
      target (independent of naming conventions such as ``ES1!``).
    """

    TRADABLE = "TRADABLE"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    SYNTHETIC = "SYNTHETIC"
    CONTINUOUS_SERIES = "CONTINUOUS_SERIES"


class AnalyticalDomain(StrEnum):
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    MONETARY_RESERVE = "MONETARY_RESERVE"
    RATES = "RATES"
    SOVEREIGN = "SOVEREIGN"
    MACRO = "MACRO"
    FX = "FX"
    DERIVATIVES = "DERIVATIVES"
    SAFE_HAVEN = "SAFE_HAVEN"


class ExternalIdentifierType(StrEnum):
    PROVIDER_SYMBOL = "PROVIDER_SYMBOL"
    EXCHANGE_SYMBOL = "EXCHANGE_SYMBOL"
    TICKER = "TICKER"
    CUSIP = "CUSIP"
    ISIN = "ISIN"
    VENDOR_ID = "VENDOR_ID"
    DISPLAY_TICKER = "DISPLAY_TICKER"


class RelationshipType(StrEnum):
    UNDERLYING = "UNDERLYING"
    CONTRACT_ROOT = "CONTRACT_ROOT"
    DENOMINATED_IN = "DENOMINATED_IN"
    BENCHMARK_OF = "BENCHMARK_OF"


class AliasResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class PriceUnitKind(StrEnum):
    CURRENCY_PER_SHARE = "CURRENCY_PER_SHARE"
    CURRENCY_PER_CONTRACT = "CURRENCY_PER_CONTRACT"
    INDEX_POINTS = "INDEX_POINTS"
    FX_PAIR_QUOTE = "FX_PAIR_QUOTE"
    YIELD_RATE = "YIELD_RATE"
    COMMODITY_UNIT = "COMMODITY_UNIT"


SCHEMA_VERSION = 1
IDENTITY_PROFILE = "imp-xa01-instrument-identity-v1"