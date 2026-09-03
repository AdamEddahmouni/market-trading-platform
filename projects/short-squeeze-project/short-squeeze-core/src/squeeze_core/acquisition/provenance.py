from .models import HistoricalOrCurrent, ProviderProvenance


def review_historical_provenance(provenance: ProviderProvenance) -> tuple[str, ...]:
    diagnostics = []
    if provenance.historical_or_current is HistoricalOrCurrent.CURRENT:
        diagnostics.append("MODERN_DATA_MISREPRESENTED_AS_HISTORICAL")
    if not provenance.provider_scope.strip() or provenance.provider_scope == "UNKNOWN":
        diagnostics.append("PROVIDER_SCOPE_UNRESOLVED")
    return tuple(sorted(diagnostics))


__all__ = ["review_historical_provenance"]
