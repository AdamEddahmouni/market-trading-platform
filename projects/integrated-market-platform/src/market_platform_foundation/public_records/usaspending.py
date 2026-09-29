"""USAspending.gov federal award transactions (contracts and grants) for a named recipient.

Source: ``POST https://api.usaspending.gov/api/v2/search/spending_by_transaction/``
(keyless) and ``GET /api/v2/awards/last_updated/`` for the publication clock.

Why transactions, not awards: ``spending_by_award`` over a date window returns every
award with *any* activity in the window, carrying its cumulative lifetime amount — a
1990s contract modified last week would read as a multi-billion-dollar "recent award".
A transaction is one action (new award or modification) with its own action date and
its own federal obligation amount, which is what "recent government award activity"
can truthfully mean.

Semantics kept exact:

* ``obligation_amount`` is the federal action obligation of that one action; it is
  0 for no-cost modifications and negative for de-obligations. It is not revenue
  and not a contract ceiling (options and ceilings are not returned here);
* contracts (FPDS award types A–D) and grants/assistance (02–05) are separate
  families — a research grant is not commercial revenue;
* matching is USAspending's recipient-name search, which also returns
  parent-linked recipients (a subsidiary's actions for the parent name). Every row
  shows the recipient actually named on the award; the match is entity-level, never exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .http import PublicRecordsHttp

SEARCH_URL = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"
LAST_UPDATED_URL = "https://api.usaspending.gov/api/v2/awards/last_updated/"
AWARD_URL = "https://www.usaspending.gov/award/{generated_id}"
PARSER_VERSION = "public_records.usaspending/1.0.0"

CONTRACT_TYPES = ("A", "B", "C", "D")
GRANT_TYPES = ("02", "03", "04", "05")
FAMILIES = {"CONTRACT": CONTRACT_TYPES, "GRANT": GRANT_TYPES}
FIELDS = ["Award ID", "Mod", "Recipient Name", "Recipient UEI", "Action Date", "Transaction Amount",
          "Transaction Description", "Award Type", "Awarding Agency", "Awarding Sub Agency", "awarding_agency_id",
          "internal_id", "generated_internal_id", "naics_code", "product_or_service_code"]
DEFAULT_WINDOW_DAYS = 90
PAGE_LIMIT = 50


@dataclass(frozen=True, slots=True)
class AwardTransaction:
    family: str                         # CONTRACT / GRANT
    award_id: str
    modification: str | None
    generated_award_id: str
    recipient_name: str
    recipient_uei: str | None
    action_date: str | None
    obligation_amount: float | None     # USD, signed; None when not reported
    award_type: str
    description: str | None
    awarding_agency: str
    awarding_sub_agency: str | None
    awarding_agency_id: int | None
    naics: str | None
    psc: str | None
    source_row_id: str

    @property
    def award_url(self) -> str:
        return AWARD_URL.format(generated_id=self.generated_award_id) if self.generated_award_id else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family, "award_id": self.award_id, "modification": self.modification,
            "recipient_name": self.recipient_name, "recipient_uei": self.recipient_uei, "action_date": self.action_date,
            "obligation_amount": self.obligation_amount, "obligation_currency": "USD",
            "obligation_note": "Federal obligation of this action (signed); not revenue, not a ceiling.",
            "award_type": self.award_type, "description": self.description, "awarding_agency": self.awarding_agency,
            "awarding_sub_agency": self.awarding_sub_agency, "naics": self.naics, "psc": self.psc,
            "source_url": self.award_url, "source_row_id": self.source_row_id,
        }


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def parse_transactions(payload: Any, *, family: str) -> list[AwardTransaction]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("USASPENDING_MALFORMED")
    rows = []
    for item in payload["results"]:
        if not isinstance(item, dict):
            continue
        generated = str(item.get("generated_internal_id") or "")
        award_id = str(item.get("Award ID") or "")
        if not award_id and not generated:
            continue
        action = _text(item.get("Action Date"))
        try:
            action = date.fromisoformat(action[:10]).isoformat() if action else None
        except ValueError:
            action = None
        agency_id = item.get("awarding_agency_id")
        rows.append(AwardTransaction(
            family=family, award_id=award_id, modification=_text(item.get("Mod")), generated_award_id=generated,
            recipient_name=str(item.get("Recipient Name") or ""), recipient_uei=_text(item.get("Recipient UEI")),
            action_date=action, obligation_amount=_float(item.get("Transaction Amount")),
            award_type=str(item.get("Award Type") or ""), description=_text(item.get("Transaction Description")),
            awarding_agency=str(item.get("Awarding Agency") or ""), awarding_sub_agency=_text(item.get("Awarding Sub Agency")),
            awarding_agency_id=int(agency_id) if isinstance(agency_id, int) else None,
            naics=_text(item.get("naics_code")), psc=_text(item.get("product_or_service_code")),
            source_row_id=str(item.get("internal_id") or "")))
    return rows


def dedupe_transactions(rows: list[AwardTransaction]) -> list[AwardTransaction]:
    """One row per (award, modification, action date); the API can repeat an action across pages."""

    seen: dict[tuple[str, str | None, str | None], AwardTransaction] = {}
    for row in rows:
        seen.setdefault((row.generated_award_id or row.award_id, row.modification, row.action_date), row)
    return sorted(seen.values(), key=lambda row: (row.action_date or "", row.award_id), reverse=True)


def search_body(recipient: str, *, family: str, start: date, end: date, limit: int = PAGE_LIMIT) -> dict[str, Any]:
    return {"filters": {"recipient_search_text": [recipient], "award_type_codes": list(FAMILIES[family]),
                        "time_period": [{"start_date": start.isoformat(), "end_date": end.isoformat()}]},
            "fields": FIELDS, "sort": "Action Date", "order": "desc", "limit": limit, "page": 1}


def has_next_page(payload: Any) -> bool:
    meta = payload.get("page_metadata") if isinstance(payload, dict) else None
    return bool(isinstance(meta, dict) and meta.get("hasNext"))


def parse_last_updated(payload: Any) -> str | None:
    raw = str((payload or {}).get("last_updated") or "") if isinstance(payload, dict) else ""
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


class UsaSpendingClient:
    def __init__(self, http: PublicRecordsHttp | None = None) -> None:
        self._http = http or PublicRecordsHttp(min_interval_s=0.5)

    def last_updated(self) -> str | None:
        return parse_last_updated(self._http.get_json(LAST_UPDATED_URL))

    def recipient_transactions(self, recipient: str, *, today: date,
                               window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, dict[str, Any]]:
        """Newest actions per family: ``{family: {"rows": [...], "has_more": bool}}`` (one page each)."""

        start = today - timedelta(days=window_days)
        out: dict[str, dict[str, Any]] = {}
        for family in FAMILIES:
            payload = self._http.post_json(SEARCH_URL, search_body(recipient, family=family, start=start, end=today))
            out[family] = {"rows": dedupe_transactions(parse_transactions(payload, family=family)),
                           "has_more": has_next_page(payload)}
        return out


__all__ = ["AWARD_URL", "AwardTransaction", "CONTRACT_TYPES", "DEFAULT_WINDOW_DAYS", "FAMILIES", "GRANT_TYPES",
           "PARSER_VERSION", "UsaSpendingClient", "dedupe_transactions", "has_next_page", "parse_last_updated", "parse_transactions",
           "search_body"]
