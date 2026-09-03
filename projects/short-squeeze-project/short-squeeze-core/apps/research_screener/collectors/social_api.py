from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import requests

from .base import EvidenceCollector
from .models import CollectorRecord


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class RedditApiCollector(EvidenceCollector):
    name = "Reddit"

    def __init__(
        self,
        *,
        enabled: bool = False,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str = "ResearchScreener/1.0",
    ) -> None:
        self._enabled = enabled
        self._client_id = client_id or os.environ.get("REDDIT_CLIENT_ID")
        self._client_secret = client_secret or os.environ.get("REDDIT_SECRET")
        self._user_agent = user_agent
        self._token: str | None = None

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._client_id and self._client_secret)

    def _auth(self) -> str | None:
        if self._token:
            return self._token
        response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(self._client_id, self._client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": self._user_agent},
            timeout=20,
        )
        response.raise_for_status()
        self._token = response.json().get("access_token")
        return self._token

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        token = self._auth()
        if not token:
            return []
        received = _now()
        records: list[CollectorRecord] = []
        headers = {"Authorization": f"bearer {token}", "User-Agent": self._user_agent}
        for symbol in symbols:
            url = f"https://oauth.reddit.com/search?q={symbol}&limit=5"
            try:
                response = requests.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                children = response.json().get("data", {}).get("children", [])
            except Exception:
                continue
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"mention_count": len(children)},
                    received_at=received,
                    source_id=self.name,
                    field_hints={
                        "social_mention_count": len(children),
                        "research_admissibility": "RESEARCH_INADMISSIBLE",
                    },
                )
            )
        return records


class StocktwitsApiCollector(EvidenceCollector):
    name = "Stocktwits"

    def __init__(
        self,
        *,
        enabled: bool = False,
        access_token: str | None = None,
    ) -> None:
        self._enabled = enabled
        self._token = access_token or os.environ.get("STOCKTWITS_ACCESS_TOKEN")

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._token)

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        received = _now()
        records: list[CollectorRecord] = []
        headers = {"Authorization": f"Bearer {self._token}"}
        for symbol in symbols:
            url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
            try:
                response = requests.get(url, headers=headers, timeout=20)
                response.raise_for_status()
                messages = response.json().get("messages", [])
            except Exception:
                continue
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"mention_count": len(messages)},
                    received_at=received,
                    source_id=self.name,
                    field_hints={
                        "social_mention_count": len(messages),
                        "research_admissibility": "RESEARCH_INADMISSIBLE",
                    },
                )
            )
        return records


__all__ = ["RedditApiCollector", "StocktwitsApiCollector"]
