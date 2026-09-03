from .models import IdentityClaim, IdentityResolution, IdentityState


_CONFLICT_FIELDS = ("symbol", "issuer_name", "exchange", "security_type", "provider_identifier")


def resolve_identity(claims: tuple[IdentityClaim, ...]) -> IdentityResolution:
    if not claims:
        return IdentityResolution(state=IdentityState.UNRESOLVED, claims=())
    conflicts = []
    for field in _CONFLICT_FIELDS:
        values = {getattr(claim, field) for claim in claims if getattr(claim, field) is not None}
        if len(values) > 1:
            conflicts.append(field)
    first = sorted(claims, key=lambda item: item.source_artifact_id)[0]
    risks = []
    if any(claim.symbol_reuse_risk for claim in claims):
        risks.append("SYMBOL_REUSE_RISK")
    if any(claim.corporate_actions for claim in claims):
        risks.append("CORPORATE_ACTION_REVIEW_REQUIRED")
    required = (first.symbol, first.issuer_name, first.exchange, first.security_type,
                first.provider_identifier)
    state = (
        IdentityState.CONFLICTED if conflicts
        else IdentityState.PARTIALLY_RESOLVED if risks or any(value is None for value in required)
        else IdentityState.RESOLVED
    )
    return IdentityResolution(
        state=state,
        canonical_symbol=first.symbol,
        issuer_name=first.issuer_name,
        exchange=first.exchange,
        security_type=first.security_type,
        provider_identifiers=tuple(
            claim.provider_identifier for claim in claims if claim.provider_identifier is not None
        ),
        claims=claims,
        conflict_fields=tuple(conflicts),
        risk_codes=tuple(risks),
    )


__all__ = ["resolve_identity"]
