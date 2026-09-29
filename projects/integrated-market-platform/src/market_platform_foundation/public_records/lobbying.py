"""Lobbying Disclosure Act filings (lda.gov, formerly lda.senate.gov) for a named client.

Source: ``GET https://lda.gov/api/v1/filings/?client_name=…&filing_year=…`` (keyless,
anonymous rate-limited). ``client_name`` is a contains-match over names typed by
registrants, so matches are entity-level and every row shows the client as filed.

Semantics kept exact:

* ``income`` is what an outside lobbying firm reported receiving from the client for
  the period; ``expenses`` is what a self-filing organization reported spending on its
  own lobbying, which *includes* its payments to outside firms. The two are never
  added together (that would double-count);
* issue codes, government entities contacted, and the filing period are as filed;
* lobbying activity is descriptive: it is not government support, not influence, and
  not an outcome. Individual lobbyists' names and prior positions are not carried —
  they are not needed to describe an issuer's lobbying activity.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from datetime import date
from typing import Any

from .http import PublicRecordsHttp

FILINGS_URL = "https://lda.gov/api/v1/filings/"
PARSER_VERSION = "public_records.lobbying/1.0.0"
PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class LobbyingFiling:
    filing_uuid: str
    filing_type: str
    filing_type_display: str
    filing_year: int | None
    filing_period_display: str
    posted_at: str | None
    registrant_name: str
    registrant_id: int | None
    client_name: str
    client_id: int | None
    self_filed: bool                 # the client is its own registrant (in-house lobbying)
    income: float | None
    expenses: float | None
    issues: tuple[dict[str, str], ...]
    government_entities: tuple[str, ...]
    document_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "filing_uuid": self.filing_uuid, "filing_type": self.filing_type,
            "filing_type_display": self.filing_type_display, "filing_year": self.filing_year,
            "filing_period": self.filing_period_display, "posted_at": self.posted_at,
            "registrant_name": self.registrant_name, "client_name": self.client_name, "self_filed": self.self_filed,
            "income": self.income, "expenses": self.expenses,
            "amount_note": ("Self-filed expenses (includes payments to outside firms)" if self.expenses is not None else
                            "Outside firm's reported income from this client" if self.income is not None else
                            "No amount reported (below the reporting threshold or not required for this filing type)"),
            "issues": list(self.issues), "government_entities": list(self.government_entities),
            "source_url": self.document_url,
        }


def _money(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def parse_filings(payload: Any) -> list[LobbyingFiling]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("LDA_MALFORMED")
    filings = []
    for item in payload["results"]:
        if not isinstance(item, dict) or not item.get("filing_uuid"):
            continue
        registrant = item.get("registrant") if isinstance(item.get("registrant"), dict) else {}
        client = item.get("client") if isinstance(item.get("client"), dict) else {}
        issues: dict[str, dict[str, str]] = {}
        entities: dict[str, None] = {}
        for activity in item.get("lobbying_activities") or []:
            if not isinstance(activity, dict):
                continue
            code = str(activity.get("general_issue_code") or "")
            if code:
                issues.setdefault(code, {"code": code, "label": str(activity.get("general_issue_code_display") or code)})
            for entity in activity.get("government_entities") or []:
                if isinstance(entity, dict) and entity.get("name"):
                    entities[str(entity["name"])] = None
        registrant_name = str(registrant.get("name") or "")
        client_name = str(client.get("name") or "")
        year = item.get("filing_year")
        filings.append(LobbyingFiling(
            filing_uuid=str(item["filing_uuid"]), filing_type=str(item.get("filing_type") or ""),
            filing_type_display=str(item.get("filing_type_display") or ""),
            filing_year=int(year) if isinstance(year, int) else None,
            filing_period_display=str(item.get("filing_period_display") or ""),
            posted_at=str(item.get("dt_posted")) if item.get("dt_posted") else None,
            registrant_name=registrant_name, registrant_id=registrant.get("id") if isinstance(registrant.get("id"), int) else None,
            client_name=client_name, client_id=client.get("id") if isinstance(client.get("id"), int) else None,
            self_filed=bool(registrant_name) and registrant_name.upper() == client_name.upper(),
            income=_money(item.get("income")), expenses=_money(item.get("expenses")),
            issues=tuple(issues.values()), government_entities=tuple(entities),
            document_url=str(item.get("filing_document_url") or "")))
    return filings


def filings_url(client: str, *, year: int) -> str:
    query = urllib.parse.urlencode({"client_name": client, "filing_year": year, "ordering": "-dt_posted",
                                    "page_size": PAGE_SIZE})
    return f"{FILINGS_URL}?{query}"


class LobbyingClient:
    def __init__(self, http: PublicRecordsHttp | None = None) -> None:
        # Anonymous LDA access is rate limited: keep requests sparse.
        self._http = http or PublicRecordsHttp(min_interval_s=4.0)

    def client_filings(self, client: str, *, today: date) -> tuple[list[LobbyingFiling], int]:
        """The current and previous filing year's newest filings, plus the API's total count."""

        filings: list[LobbyingFiling] = []
        total = 0
        for year in (today.year, today.year - 1):
            payload = self._http.get_json(filings_url(client, year=year))
            total += int(payload.get("count") or 0) if isinstance(payload, dict) else 0
            filings.extend(parse_filings(payload))
        filings.sort(key=lambda item: (item.posted_at or "", item.filing_uuid), reverse=True)
        return filings, total


__all__ = ["FILINGS_URL", "LobbyingClient", "LobbyingFiling", "PARSER_VERSION", "filings_url", "parse_filings"]
