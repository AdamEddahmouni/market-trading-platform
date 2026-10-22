"""Bounded research projection over XA identity/reference and Screener services.

Edges assert structure or documented relevance, never causality or execution.
Unspecified return windows cannot produce directional agreement.
"""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any, Callable

from ..xa01.compatibility import register_equity, register_future_family, register_future_contract_reference
from ..xa01.registry import InstrumentRegistry
from ..xa02.catalog import bootstrap_xa_targets, build_catalog_relationships
from ..xa04.operations import get_repository
from .screener_futures_context import related_futures, MAPPING_VERSION

SCHEMA_VERSION = "screener-connectivity/1.0.0"
DOMAINS = ("STOCK_ETF", "OPTIONS", "FUTURES", "BONDS_RATES")
MAX_NODES = 20
MAX_EDGES = 24


def compare_direction(left: dict | None, right: dict | None, *, cutoff: str | None = None) -> dict[str, str]:
    """Exact observed-return windows only; not a forecast or correlation."""
    result = {"state": "UNKNOWN", "basis": "OBSERVED_DIRECTION_V1",
              "explanation": "Compatible observed-return windows and provenance are required."}
    if left is None or right is None:
        return {**result, "state": "UNAVAILABLE"}
    for observation in (left, right):
        if observation.get("decision_evidence", {}).get("eligible_for_current_decision") is False:
            return result
        if observation.get("state") not in ("CURRENT", "LIVE"):
            return result
        if not all(observation.get(key) for key in ("source", "as_of", "window_start", "window_end", "basis")):
            return result
        value = observation.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value == 0:
            return result
        try:
            start, end, as_of = [datetime.fromisoformat(observation[key].replace("Z", "+00:00"))
                                 for key in ("window_start", "window_end", "as_of")]
            if any(t.tzinfo is None for t in (start, end, as_of)) or start >= end or as_of != end:
                return result
            if cutoff:
                decision = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
                if not 0 <= (decision - end).total_seconds() <= observation.get("stale_after_ms", 60_000) / 1000:
                    return result
        except (ValueError, TypeError):
            return result
    if any(left[key] != right[key] for key in ("window_start", "window_end", "basis")):
        return result
    return {**result, "state": "CONFIRMING" if left["value"] * right["value"] > 0 else "CONFLICTING",
            "explanation": "Observed price-direction agreement over identical windows; not a prediction."}


def _safe(reader: Callable, *args: Any) -> dict:
    try:
        return reader(*args) or {}
    except Exception:  # provider composition boundary: retain other domains
        return {"state": "UNAVAILABLE", "reason": "SOURCE_READ_FAILED"}


def _clock(field: dict) -> str | None:
    if field.get("as_of"):
        return field["as_of"]
    if field.get("as_of_ns"):
        return datetime.fromtimestamp(field["as_of_ns"] / 1e9, UTC).isoformat().replace("+00:00", "Z")
    return None


class ConnectivityService:
    def __init__(self, *, row_getter=None, quote_getter=None, options_reader=None, futures_reader=None,
                 rates_reader=None, catalog=None, now=None):
        self.row_getter = row_getter or _row
        self.quote_getter = quote_getter or _quote
        self.options_reader = options_reader or _options
        self.futures_reader = futures_reader or _futures
        self.rates_reader = rates_reader or _rates
        self.catalog = catalog if catalog is not None else get_repository()
        self.now = now or (lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))

    def read(self, instrument: str, universe: str) -> dict | None:
        if universe not in ("US_EQUITIES", "US_ETFS", "FUTURES", "BONDS"):
            raise ValueError("CONNECTIVITY_UNAVAILABLE_FOR_UNIVERSE")
        if not instrument or len(instrument) > 80:
            raise ValueError("INVALID_INSTRUMENT")
        row = self.row_getter(instrument, universe)
        if row is None:
            return None
        if row["instrument"]["instrument_id"] != instrument:
            return None
        generated = self.now()
        registry = InstrumentRegistry()
        selected_id = instrument if instrument.startswith("XA01:") else register_equity(symbol=row["symbol"], registry=registry)
        domains = {d: {"state": "UNKNOWN", "reason": "NO_SUPPORTED_RELATIONSHIP"} for d in DOMAINS}
        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        def node(identifier, label, domain, asset, kind, *, state="UNAVAILABLE", source=None,
                 as_of=None, received_at=None, facts=None, canonical=None, decision_evidence=None):
            if identifier not in nodes and len(nodes) < MAX_NODES:
                nodes[identifier] = dict(node_id=identifier, canonical_instrument_id=canonical,
                    label=label, domain=domain, asset_class=asset, instrument_kind=kind, state=state,
                    source=source, as_of=as_of, received_at=received_at, facts=facts or {},
                    decision_evidence=decision_evidence, executable=False, role="SELECTED" if identifier == selected_id else "CONTEXT")
            return identifier

        def edge(origin, target, relation, classification, basis, explanation, state="CONTEXT_ONLY",
                 provenance=None, version=None):
            if origin not in nodes or target not in nodes or len(edges) >= MAX_EDGES:
                return
            identifier = f"{origin}|{relation}|{target}"
            if any(e["edge_id"] == identifier for e in edges):
                return
            edges.append(dict(edge_id=identifier, from_node=origin, to_node=target,
                relationship_type=relation, relationship_class=classification, basis=basis,
                definition_version=version, evidence_state=state, explanation=explanation,
                provenance=provenance or {}))

        selected_domain = {"US_EQUITIES": "STOCK_ETF", "US_ETFS": "STOCK_ETF",
                           "FUTURES": "FUTURES", "BONDS": "BONDS_RATES"}[universe]
        quote = _safe(self.quote_getter, instrument, universe)
        price = (quote.get("fields") or {}).get("price") or {}
        if price.get("value") is None:
            price = (row.get("fields") or {}).get("price") or {}
        source_state = price.get("state") or quote.get("state") or "UNAVAILABLE"
        node(selected_id, row["symbol"], selected_domain, row["instrument"].get("asset_class", "UNKNOWN"),
             row["instrument"].get("instrument_kind", "UNKNOWN"), state=source_state,
             source=price.get("source"), as_of=_clock(price), facts={"price": price.get("value")},
             canonical=selected_id)
        domains[selected_domain] = {"state": "AVAILABLE" if price.get("value") is not None else "UNAVAILABLE",
                                    "reason": None if price.get("value") is not None else quote.get("reason", "NO_MARKET_OBSERVATION")}

        if universe in ("US_EQUITIES", "US_ETFS"):
            options = _safe(self.options_reader, instrument, universe)
            valid = options.get("instrument_id") == instrument and options.get("universe") == universe
            available = valid and options.get("state") in ("CURRENT_SNAPSHOT", "MARKET_CLOSED", "STALE")
            domains["OPTIONS"] = {"state": "AVAILABLE" if available else "UNAVAILABLE",
                                  "reason": options.get("reason") if valid else options.get("reason") or "OPTIONS_IDENTITY_MISMATCH"}
            if valid:
                option_id = f"context:options:{selected_id}"
                from .screener_freshness import project_screener_response
                option_evidence = project_screener_response("/screener/options", options, now=generated)["decision_inputs"][0]
                clock = options.get("clock") or {}
                node(option_id, f'{row["symbol"]} options', "OPTIONS", "OPTION", "OPTIONS_CONTEXT",
                     state=options.get("state", "UNAVAILABLE"), source=(options.get("provider") or {}).get("id"),
                     as_of=clock.get("provider_as_of") or clock.get("latest_contract_trade_at"),
                     decision_evidence=option_evidence, received_at=clock.get("fetched_at"), facts={"nearest_expiry": options.get("selected_expiration"),
                     "summary": options.get("summary")})
                edge(option_id, selected_id, "UNDERLYING", "STRUCTURAL", "SELECTED_UNDERLYING",
                     "Option-chain context belongs to the selected underlying. No directional inference.",
                     "CONTEXT_ONLY" if available and options["state"] != "STALE" else "UNKNOWN" if available else "UNAVAILABLE",
                     {"instrument_id": instrument, "universe": universe, "clock": clock}, "XA01.UNDERLYING")

        family_ids: list[str] = []
        if universe == "US_EQUITIES":
            payload = _safe(self.futures_reader, instrument)
            context = payload.get("futures") or {}
            expected = {r.root: r for r in related_futures(sector=row.get("sector"), industry=row.get("industry"),
                        market_cap=(row.get("fields", {}).get("market_cap") or {}).get("value"))}
            items = context.get("items", []) if (payload.get("instrument") or {}).get("instrument_id") == instrument else []
            for item in items[:6]:
                root = item.get("root")
                if root not in expected or context.get("mapping_version") != MAPPING_VERSION:
                    continue
                family = register_future_family(family_root=root, registry=registry)
                family_ids.append(family)
                contract, fq = item.get("contract") or {}, item.get("quote") or {}
                node(family, root, "FUTURES", "FUTURE", "FUTURE_FAMILY", canonical=family,
                     state="REFERENCE_METADATA",
                     facts={"matched_sector": row.get("sector"), "matched_industry": row.get("industry"),
                            "matched_market_cap": (row.get("fields", {}).get("market_cap") or {}).get("value")})
                future_observation = fq.get("return_observation")
                if future_observation:
                    future_observation = {**future_observation, "stale_after_ms": 15_000}
                comparison = compare_direction(quote.get("return_observation"), future_observation, cutoff=generated) if fq else None
                if comparison and (quote.get("state") in ("STALE", "UNAVAILABLE", "DELAYED", "SESSION_CLOSED") or fq.get("state") not in ("LIVE", "CURRENT")):
                    comparison = {**comparison, "state": "UNKNOWN"}
                assessment = comparison["state"] if comparison and quote.get("return_observation") and fq.get("return_observation") else "UNKNOWN" if fq else "UNAVAILABLE"
                explanation = expected[root].reason + " Contextual relevance alone implies no directional conclusion."
                edge(selected_id, family, "REFERENCE_RELEVANT_TO", "CONTEXTUAL_MAPPING", MAPPING_VERSION,
                     explanation, "CONTEXT_ONLY" if assessment in ("CONFIRMING", "CONFLICTING") else assessment,
                     {"mapping_reason": expected[root].reason, "contract": contract,
                      "unavailable_reason": item.get("unavailable_reason")}, MAPPING_VERSION)
                if contract.get("state") == "CURRENT":
                    if not re.fullmatch(re.escape(root) + r"[FGHJKMNQUVXZ]\d{2}", str(contract.get("contract_id", ""))):
                        continue
                    try:
                        dated = register_future_contract_reference(contract_id=contract["contract_id"], family_root=root,
                            contract_month=contract["contract_month"], expiration=contract["last_trade_date"], registry=registry)
                    except (KeyError, ValueError):
                        continue
                    if datetime.fromisoformat(contract["last_trade_date"]).date() < datetime.fromisoformat(generated.replace("Z", "+00:00")).date():
                        continue
                    node(dated, contract["contract_id"], "FUTURES", "FUTURE", "FUTURE_CONTRACT", canonical=dated,
                         state=fq.get("state", "UNAVAILABLE"), source=fq.get("provider"), as_of=fq.get("as_of"), facts={"quote": fq, "contract": contract})
                    if comparison and assessment in ("CONFIRMING", "CONFLICTING"):
                        edge(selected_id, dated, "OBSERVED_DIRECTION_AGREEMENT", "DERIVED_COMPARISON",
                             comparison["basis"], comparison["explanation"], assessment,
                             {"left": quote["return_observation"], "right": fq["return_observation"]}, "OBSERVED_DIRECTION_V1")
                    edge(dated, family, "CONTRACT_ROOT", "STRUCTURAL", "XA01.CONTRACT_ROOT",
                         "Validated dated contract belongs to this family; the family is not executable.",
                         "CONTEXT_ONLY" if fq else "UNAVAILABLE", {"contract": contract}, "XA01.CONTRACT_ROOT")
            domains["FUTURES"] = {"state": "AVAILABLE" if any(n["domain"] == "FUTURES" and n["source"] for n in nodes.values()) else "UNAVAILABLE",
                                  "reason": None if items else "NO_SUPPORTED_RELATIONSHIP"}
        elif universe == "FUTURES" and row.get("root"):
            family = register_future_family(family_root=row["root"], registry=registry)
            family_ids.append(family)
            node(family, row["root"], "FUTURES", "FUTURE", "FUTURE_FAMILY", canonical=family)
            if family != selected_id:
                edge(selected_id, family, "CONTRACT_ROOT", "STRUCTURAL", "XA01.CONTRACT_ROOT",
                     "Selected dated contract belongs to this family; no reverse stock mapping is inferred.")

        catalog_definitions = build_catalog_relationships(xa_targets=bootstrap_xa_targets(registry))
        missing_references: set[str] = set()
        catalog_unavailable = False
        for target in list(dict.fromkeys([selected_id, *family_ids])):
            try:
                references = list(self.catalog.list_cross_asset_relationships_for_target(target))
            except Exception:  # catalog outage is explicit partial coverage
                references = []
                catalog_unavailable = True
            references += [r for r in catalog_definitions if r.target_xa_canonical_id == target]
            for ref in references[:6]:
                if (ref.valid_from and ref.valid_from > generated) or (ref.valid_to and ref.valid_to <= generated):
                    continue
                if ref.subject_type.value != "CANONICAL_INDICATOR":
                    continue
                try:
                    observation = self.catalog.latest_scalar_observation_as_of(generated, canonical_indicator_id=ref.subject_id)
                except Exception:
                    observation = None
                    catalog_unavailable = True
                if observation is None:
                    missing_references.add(ref.subject_id)
                identifier = f"indicator:{ref.subject_id}"
                node(identifier, ref.subject_id, "BONDS_RATES", "REFERENCE", "MACRO_INDICATOR",
                     state="PUBLICATION_BASED" if observation else "UNAVAILABLE",
                     source=observation.provenance.provider.value if observation else None,
                     as_of=observation.event_time if observation else None, received_at=observation.retrieval_time if observation else None,
                     facts={"value": observation.normalized_value, "units": observation.units, "available_time": observation.available_time,
                            "observation_id": observation.observation_id} if observation else {})
                edge(identifier, target, ref.relationship_type.value, "REFERENCE", ref.provenance_ref,
                     "XA reference metadata only; no causal claim or stock-direction inference.",
                     "CONTEXT_ONLY" if observation else "UNAVAILABLE",
                     {"relationship_id": ref.relationship_id, "provenance_ref": ref.provenance_ref}, "XA02/1")

        if any(n["domain"] == "BONDS_RATES" and n["state"] == "PUBLICATION_BASED" for n in nodes.values()):
            domains["BONDS_RATES"] = {"state": "AVAILABLE", "reason": None}
        elif catalog_unavailable or missing_references:
            domains["BONDS_RATES"] = {"state": "UNAVAILABLE",
                "reason": "CATALOG_UNAVAILABLE" if catalog_unavailable else "NO_ADMITTED_OBSERVATION"}
        domains["BONDS_RATES"]["missing_references"] = sorted(missing_references)
        domains["BONDS_RATES"]["catalog_unavailable"] = catalog_unavailable

        if universe == "BONDS":
            rates = _safe(self.rates_reader, instrument)
            selected = rates.get("selected") or {}
            reference = selected.get("reference") or {}
            if selected.get("instrument_id") == instrument and reference.get("state") == "REFERENCE":
                identifier = f'context:curve:{reference.get("curve")}:{reference.get("tenor")}'
                node(identifier, f'Treasury {reference.get("tenor")} par reference', "BONDS_RATES", "REFERENCE", "CURVE_REFERENCE",
                     state="PUBLICATION_BASED", source="US_TREASURY_DAILY_RATES", as_of=reference.get("publication_date"), facts=reference)
                edge(identifier, selected_id, "BENCHMARK_FOR", "REFERENCE", "NEAREST_PUBLISHED_TENOR",
                     "Existing Rates & Curve maturity reference; not this security's yield.", provenance=reference,
                     version="screener-rates-curve/1.0.0")
                domains["BONDS_RATES"].update(state="AVAILABLE", reason=None)
        return dict(schema_version=SCHEMA_VERSION, instrument_id=instrument, universe=universe,
                    selected_instrument=nodes[selected_id], nodes=list(nodes.values()), edges=edges,
                    completeness={"requested_domains": list(DOMAINS), "domains": domains}, generated_at=generated,
                    causal_note="Research context only. Reference relevance and observed agreement do not establish causality or predict returns.")


def _row(instrument, universe):
    from .screener_multi import multi_screener_service
    return multi_screener_service().row_for(instrument, universe=universe)[0]


def _quote(instrument, universe):
    from .screener_multi import multi_screener_service
    return multi_screener_service().quote_for(instrument, universe=universe)


def _options(instrument, universe):
    from .screener_options import read_options
    return read_options(instrument, universe=universe, view="summary")


def _futures(instrument):
    from .screener_preview import preview_service
    return preview_service().futures_context(instrument)


def _rates(instrument):
    from .screener_bonds import bond_screener_service
    return bond_screener_service().rates_curve(instrument)
