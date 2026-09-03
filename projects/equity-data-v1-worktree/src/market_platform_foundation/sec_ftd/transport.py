"""SEC FTD archive retrieval with on-disk cache and hash comparison."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..canonical import sha256_bytes
from ..sec_edgar.transport import SecTransport
from .periods import FtdPeriod


@dataclass(frozen=True, slots=True)
class FtdArchiveCapture:
    period: FtdPeriod
    content_hash: str
    content_bytes: bytes
    source_url: str
    retrieved_time: str
    first_observed_time: str
    cache_path: str = ""
    replaced_prior_hash: str = ""


class FtdTransport:
    """Fetch immutable SEC FTD ZIP archives. Cache by content hash."""

    def __init__(
        self,
        transport: SecTransport,
        *,
        cache_root: Path | None = None,
    ) -> None:
        self.transport = transport
        self.cache_root = cache_root or Path("evidence/sec_ftd/captures")
        self._known_hashes: dict[str, str] = {}

    def fetch_archive(
        self,
        period: FtdPeriod,
        *,
        retrieved_time: str,
        first_observed_time: str | None = None,
    ) -> FtdArchiveCapture:
        url = period.download_url
        body = self.transport.get(url, immutable=True)
        content_hash = sha256_bytes(body)
        prior = self._known_hashes.get(period.period_key, "")
        observed = first_observed_time or retrieved_time
        cache_path = self._write_cache(period, content_hash, body)
        if prior and prior != content_hash:
            self._known_hashes[period.period_key] = content_hash
            return FtdArchiveCapture(
                period=period,
                content_hash=content_hash,
                content_bytes=body,
                source_url=url,
                retrieved_time=retrieved_time,
                first_observed_time=observed,
                cache_path=str(cache_path),
                replaced_prior_hash=prior,
            )
        self._known_hashes[period.period_key] = content_hash
        return FtdArchiveCapture(
            period=period,
            content_hash=content_hash,
            content_bytes=body,
            source_url=url,
            retrieved_time=retrieved_time,
            first_observed_time=observed,
            cache_path=str(cache_path),
        )

    def load_cached(self, period: FtdPeriod) -> FtdArchiveCapture | None:
        period_dir = self.cache_root / period.period_key
        if not period_dir.is_dir():
            return None
        zips = sorted(period_dir.glob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not zips:
            return None
        latest = zips[0]
        body = latest.read_bytes()
        content_hash = sha256_bytes(body)
        self._known_hashes[period.period_key] = content_hash
        return FtdArchiveCapture(
            period=period,
            content_hash=content_hash,
            content_bytes=body,
            source_url=period.download_url,
            retrieved_time="",
            first_observed_time="",
            cache_path=str(latest),
        )

    def _write_cache(self, period: FtdPeriod, content_hash: str, body: bytes) -> Path:
        period_dir = self.cache_root / period.period_key
        period_dir.mkdir(parents=True, exist_ok=True)
        target = period_dir / f"{content_hash[:16]}.zip"
        if not target.exists():
            target.write_bytes(body)
        return target


__all__ = ["FtdArchiveCapture", "FtdTransport"]
