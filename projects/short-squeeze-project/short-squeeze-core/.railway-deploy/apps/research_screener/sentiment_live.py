"""Sentiment analysis integration layer.

Provides LocalFinbertProvider (lazy-loads the fine-tuned FinBERT) and
NullSentimentProvider. SentimentAnalyzer wraps a provider for the screener.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FINBERT_HUB_DEFAULT = "ProsusAI/finbert"


def _config_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = str(value).strip()
    if not stripped:
        return True
    return stripped.lower().startswith("replace_with")


def _core_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_sentiment_model_path(explicit: str | None = None) -> str | None:
    """Resolve a local FinBERT checkpoint directory or Hugging Face model id."""

    def _usable(raw: str | None) -> str | None:
        if raw is None or _config_placeholder(raw):
            return None
        text = str(raw).strip()
        expanded = Path(text).expanduser()
        if expanded.is_dir():
            return str(expanded.resolve())
        if "/" in text and not expanded.exists():
            return text
        return None

    for candidate in (
        explicit,
        os.environ.get("SENTIMENT_MODEL_PATH"),
        os.environ.get("FINBERT_MODEL_PATH"),
    ):
        resolved = _usable(candidate)
        if resolved:
            return resolved

    root = _core_package_root()
    for relative in (
        "models/finbert_finetuned",
        "model/finbert_finetuned",
        "data/finbert_finetuned",
    ):
        path = root / relative
        if path.is_dir() and (path / "config.json").is_file():
            return str(path.resolve())

    archived = root / "models" / "finbert_finetuned"
    if archived.is_dir() and (archived / "config.json").is_file():
        return str(archived.resolve())

    return FINBERT_HUB_DEFAULT


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _headline_hash(text: str) -> str:
    return hashlib.sha256(
        " ".join(str(text).lower().split()).encode("utf-8")
    ).hexdigest()


class SentimentProviderBase(ABC):
    @property
    @abstractmethod
    def configured(self) -> bool:
        pass

    @property
    def model_id(self) -> str:
        return type(self).__name__

    @abstractmethod
    def analyze_headlines(
        self, headlines: list[str]
    ) -> list[dict[str, Any]]:
        pass

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.model_id,
            "configured": self.configured,
        }

    def ensure_loaded(self) -> bool:
        return getattr(self, "model_loaded", self.configured)


class NullSentimentProvider(SentimentProviderBase):
    @property
    def configured(self) -> bool:
        return False

    @property
    def model_id(self) -> str:
        return "none"

    def analyze_headlines(
        self, headlines: list[str]
    ) -> list[dict[str, Any]]:
        return []

    def status(self) -> dict[str, Any]:
        return {"provider": "none", "configured": False, "model_loaded": False}


class KeywordSentimentProvider(SentimentProviderBase):
    """Lightweight keyword-based sentiment provider. No ML dependencies."""

    POSITIVE_KEYWORDS = {
        "squeeze", "short squeeze", "gamma squeeze", "moon", "rocket",
        "breakout", "surge", "rally", "spike", "gap up", "upgrade",
        "buyout", "acquisition", "beat", "beat estimates", "guidance raise",
        "fda approval", "breakthrough", "partnership", "contract",
        "buyback", "repurchase", "dividend", "positive", "profit",
        "record revenue", "record high", "all time high", "new high",
        "green", "bull", "bullish", "outperform", "overweight",
        "strong buy", "price target raised",
    }

    NEGATIVE_KEYWORDS = {
        "crash", "collapse", "plunge", "tumble", "drop", "decline",
        "downgrade", "selloff", "bankruptcy", "chapter 11", "layoff",
        "loss", "losses", "debt", "default", "delist", "delisting",
        "warning", "guidance cut", "miss", "missed estimates",
        "investigation", "lawsuit", "sec", "subpoena", "fraud",
        "dilution", "offering", "share sale", "insider sale",
        "red", "bear", "bearish", "underperform", "underweight",
        "sell", "short", "weak", "concern", "risk",
    }

    @property
    def configured(self) -> bool:
        return True

    @property
    def model_id(self) -> str:
        return "keyword-v1"

    @property
    def model_loaded(self) -> bool:
        return True

    def analyze_headlines(
        self, headlines: list[str]
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for text in headlines:
            t = str(text).lower()
            pos_hits = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in t)
            neg_hits = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in t)
            if pos_hits > neg_hits:
                label = "positive"
                score = min(0.99, 0.51 + (pos_hits - neg_hits) * 0.05)
            elif neg_hits > pos_hits:
                label = "negative"
                score = min(0.99, 0.51 + (neg_hits - pos_hits) * 0.05)
            else:
                label = "neutral"
                score = 0.5
            results.append({
                "label": label,
                "score": round(score, 4),
                "keyword_hits": {"positive": pos_hits, "negative": neg_hits},
            })
        return results

    def status(self) -> dict[str, Any]:
        return {
            "provider": "keyword-v1",
            "configured": True,
            "model_loaded": True,
            "model_id": "keyword-v1",
            "load_error": None,
        }


class LocalFinbertProvider(SentimentProviderBase):
    def __init__(
        self,
        *,
        model_path: str | None = None,
        batch_size: int = 8,
    ) -> None:
        self._model_path = model_path
        self._batch_size = max(1, int(batch_size))
        self._pipeline: Any = None
        self._labels: dict[int, str] = {}
        self._model_loaded = False
        self._load_error: str | None = None
        self._load_time_s: float | None = None
        self._model_id_text: str = "FinBERT-finetuned-local"

    @property
    def configured(self) -> bool:
        return bool(self._model_path and str(self._model_path).strip())

    @property
    def model_id(self) -> str:
        return self._model_id_text

    @property
    def model_loaded(self) -> bool:
        return self._model_loaded

    @property
    def load_error(self) -> str | None:
        return self._load_error

    @property
    def batch_size(self) -> int:
        return self._batch_size

    def status(self) -> dict[str, Any]:
        return {
            "provider": "FinBERT (local)",
            "configured": self.configured,
            "model_loaded": self._model_loaded,
            "model_id": self._model_id_text,
            "model_path": self._model_path,
            "load_error": self._load_error,
            "load_time_s": self._load_time_s,
            "batch_size": self._batch_size,
            "labels": dict(self._labels),
        }

    def ensure_loaded(self) -> bool:
        return self._load_model()

    def _resolve_label(self, raw_label: str) -> str:
        raw = str(raw_label).lower().strip()
        if raw in ("positive", "negative", "neutral"):
            return raw
        for _idx, label in self._labels.items():
            if str(label).lower() == raw:
                return str(label).lower()
        return raw

    def _load_model(self) -> bool:
        if self._model_loaded:
            return True
        if not self.configured:
            self._load_error = "No FinBERT model path configured"
            return False
        raw_path = str(self._model_path).strip()
        local = Path(raw_path).expanduser()
        model_ref = str(local.resolve()) if local.is_dir() else raw_path
        t0 = datetime.now(tz=UTC)
        try:
            from transformers import pipeline

            config_path = local / "config.json" if local.is_dir() else None
            if config_path is not None and config_path.is_file():
                with open(config_path, encoding="utf-8") as f:
                    cfg = json.load(f)
                self._labels = {
                    int(k): str(v) for k, v in cfg.get("id2label", {}).items()
                }
                self._model_id_text = (
                    cfg.get("_name_or_path") or local.name or "FinBERT-finetuned-local"
                )
            elif "/" in raw_path:
                self._model_id_text = raw_path

            self._pipeline = pipeline(
                "sentiment-analysis",
                model=model_ref,
                tokenizer=model_ref,
                device=-1,
            )
            t1 = datetime.now(tz=UTC)
            self._load_time_s = (t1 - t0).total_seconds()
            self._model_loaded = True
            self._load_error = None
            return True
        except ImportError as exc:
            self._load_error = (
                "transformers/torch not available — install with "
                f"pip install 'short-squeeze-core[sentiment]': {exc}"
            )
            return False
        except Exception as exc:
            self._load_error = f"Model load: {type(exc).__name__}: {exc}"
            return False

    def analyze_headlines(
        self, headlines: list[str]
    ) -> list[dict[str, Any]]:
        if not headlines or not self.configured:
            return []
        if not self._model_loaded:
            self._load_model()
        if not self._model_loaded or self._pipeline is None:
            return [
                {
                    "headline": h,
                    "sentiment_label": "unknown",
                    "score": None,
                    "model_id": self._model_id_text,
                    "evaluated_at": _now(),
                    "headline_hash": _headline_hash(h),
                    "reason": self._load_error or "Model not loaded",
                }
                for h in headlines
            ]

        results: list[dict[str, Any]] = []
        evaluated_at = _now()

        for batch_start in range(0, len(headlines), self._batch_size):
            batch_end = min(batch_start + self._batch_size, len(headlines))
            batch = headlines[batch_start:batch_end]
            try:
                raw = self._pipeline(batch, truncation=True)
            except Exception as exc:
                emsg = f"{type(exc).__name__}: {exc}"
                for h in batch:
                    results.append({
                        "headline": h,
                        "sentiment_label": "error",
                        "score": None,
                        "model_id": self._model_id_text,
                        "evaluated_at": evaluated_at,
                        "headline_hash": _headline_hash(h),
                        "error": emsg,
                    })
                continue
            for j, item in enumerate(raw):
                rlabel = self._resolve_label(str(item.get("label", "")))
                score = float(item.get("score", 0.0))
                htext = batch[j]
                results.append({
                    "headline": htext,
                    "sentiment_label": rlabel,
                    "score": round(score, 4),
                    "model_id": self._model_id_text,
                    "evaluated_at": evaluated_at,
                    "headline_hash": _headline_hash(htext),
                })
        return results


class SentimentAnalyzer:
    def __init__(self, *, provider: SentimentProviderBase | None = None) -> None:
        self._provider = provider or NullSentimentProvider()
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self._cache_hits = 0
        self._total_inference_ms: float = 0.0
        self._inference_count = 0
        self._batch_size = (
            provider.batch_size
            if hasattr(provider, "batch_size") else 8
        )

    @property
    def enabled(self) -> bool:
        return self._provider.configured

    @property
    def configured(self) -> bool:
        return self._provider.configured

    @property
    def model_loaded(self) -> bool:
        return getattr(self._provider, "model_loaded", False)

    @property
    def model_id(self) -> str:
        return self._provider.model_id

    @property
    def load_error(self) -> str | None:
        return getattr(self._provider, "load_error", None)

    def status(self) -> dict[str, Any]:
        base = {
            "enabled": self.enabled,
            "model_loaded": self.model_loaded,
            "model_id": self._provider.model_id,
            "batch_size": self._batch_size,
            "cache_hits": self._cache_hits,
            "inference_count": self._inference_count,
            "total_inference_ms": round(self._total_inference_ms, 1),
        }
        if hasattr(self._provider, "status"):
            base["provider"] = self._provider.status()
        if self.load_error:
            base["load_error"] = self.load_error
        return base

    def _ensure_ready(self) -> bool:
        if not self._provider.configured:
            return False
        ensure = getattr(self._provider, "ensure_loaded", None)
        if callable(ensure):
            return bool(ensure())
        return bool(getattr(self._provider, "model_loaded", False))

    def analyze_headlines(
        self, headlines: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not headlines or not self._provider.configured:
            return self._empty_results(headlines)

        texts = [
            str(item.get("headline", "")) if isinstance(item, dict)
            else str(item)
            for item in headlines
        ]

        if not self._ensure_ready():
            reason = self.load_error or "Sentiment not configured or model not loaded"
            return [
                {
                    "headline": item.get("headline", "") if isinstance(item, dict) else str(item),
                    "sentiment_label": "unknown",
                    "score": None,
                    "model_id": self._provider.model_id if self._provider.configured else "",
                    "evaluated_at": _now(),
                    "headline_hash": _headline_hash(texts[i]),
                    "reason": reason,
                }
                for i, item in enumerate(headlines)
            ]

        results: list[dict[str, Any]] = []
        uncached_idx: list[int] = []
        uncached_texts: list[str] = []

        with self._lock:
            for i, item in enumerate(headlines):
                htext = texts[i]
                h = _headline_hash(htext)
                key = f"{self._provider.model_id}:{h}"
                if key in self._cache:
                    cached = dict(self._cache[key])
                    if isinstance(item, dict):
                        cached["headline"] = item.get("headline", htext)
                    cached["retrieved_from_cache"] = True
                    results.append(cached)
                    self._cache_hits += 1
                else:
                    results.append({})
                    uncached_idx.append(i)
                    uncached_texts.append(htext)

        if not uncached_texts:
            return results

        evaluated_at = _now()
        try:
            bsz = max(1, self._batch_size)
            for batch_start in range(0, len(uncached_texts), bsz):
                batch_end = min(batch_start + bsz, len(uncached_texts))
                batch = uncached_texts[batch_start:batch_end]
                batch_indices = uncached_idx[batch_start:batch_end]

                t0 = datetime.now(tz=UTC)
                raw = self._provider.analyze_headlines(batch)
                t1 = datetime.now(tz=UTC)
                self._total_inference_ms += (t1 - t0).total_seconds() * 1000
                self._inference_count += len(batch)

                for j, r in enumerate(raw):
                    orig_idx = batch_indices[j]
                    if isinstance(item := headlines[orig_idx], dict):
                        r["headline"] = item.get("headline", "")
                        r["url"] = item.get("url")
                        r["source"] = item.get("source")
                    r["evaluated_at"] = evaluated_at
                    if "sentiment_label" not in r and r.get("label") is not None:
                        r["sentiment_label"] = str(r["label"]).lower()
                    if "sentiment_label" not in r:
                        r["sentiment_label"] = "unknown"
                    results[orig_idx] = r
                    h = _headline_hash(r.get("headline", ""))
                    with self._lock:
                        key = f"{self._provider.model_id}:{h}"
                        self._cache[key] = dict(r)
                        self._cache.move_to_end(key)
                        while len(self._cache) > 4096:
                            self._cache.popitem(last=False)
        except Exception as exc:
            emsg = f"{type(exc).__name__}: {exc}"
            for idx in uncached_idx:
                htext = uncached_texts[uncached_idx.index(idx)]
                results[idx] = {
                    "headline": htext,
                    "sentiment_label": "error",
                    "score": None,
                    "model_id": self._provider.model_id,
                    "evaluated_at": evaluated_at,
                    "headline_hash": _headline_hash(htext),
                    "error": emsg,
                }
        return results

    def _empty_results(
        self, headlines: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return [
            {
                "headline": item.get("headline", "") if isinstance(item, dict) else str(item),
                "sentiment_label": "unknown",
                "score": None,
                "model_id": "",
                "evaluated_at": _now(),
                "headline_hash": _headline_hash(
                    str(item.get("headline", "")) if isinstance(item, dict) else str(item)
                ),
                "reason": "Sentiment not configured or model not loaded",
            }
            for item in headlines
        ]

    def analyze_symbol(
        self, symbol: str, headlines: list[dict[str, Any]]
    ) -> dict[str, Any]:
        results = self.analyze_headlines(headlines)
        positive = sum(1 for r in results if r.get("sentiment_label") == "positive")
        neutral = sum(1 for r in results if r.get("sentiment_label") == "neutral")
        negative = sum(1 for r in results if r.get("sentiment_label") == "negative")
        analyzed = sum(
            1 for r in results
            if r.get("sentiment_label") not in ("unknown", "error")
        )

        if analyzed == 0:
            dominant = "UNKNOWN"
        else:
            counts = {"positive": positive, "negative": negative, "neutral": neutral}
            max_count = max(counts.values())
            top = [l for l, c in counts.items() if c == max_count]
            dominant = "MIXED" if len(top) > 1 else top[0]

        return {
            "symbol": symbol,
            "positive_count": positive,
            "neutral_count": neutral,
            "negative_count": negative,
            "dominant_label": dominant,
            "headline_count": len(headlines),
            "analyzed_count": analyzed,
            "analyzed": analyzed,
            "model_id": self._provider.model_id if self._provider.configured else "",
            "model_status": "READY" if self.model_loaded else "NOT_LOADED",
            "evaluated_at": _now(),
            "results": results,
            "note": "EXPERIMENTAL NEWS SENTIMENT",
        }


_ANALYZER: SentimentAnalyzer | None = None
_AN_LOCK = threading.Lock()


def get_sentiment_analyzer() -> SentimentAnalyzer:
    global _ANALYZER
    with _AN_LOCK:
        if _ANALYZER is None:
            _ANALYZER = SentimentAnalyzer()
        return _ANALYZER


def configure_sentiment(analyzer: SentimentAnalyzer) -> SentimentAnalyzer:
    global _ANALYZER
    with _AN_LOCK:
        _ANALYZER = analyzer
        return _ANALYZER


def warm_sentiment_analyzer(analyzer: SentimentAnalyzer | None = None) -> dict[str, Any]:
    """Eager-load the configured sentiment model (FinBERT) when possible."""
    target = analyzer or get_sentiment_analyzer()
    ready = target._ensure_ready() if target.enabled else False
    return {
        "enabled": target.enabled,
        "model_loaded": target.model_loaded,
        "model_id": target.model_id,
        "load_error": target.load_error,
        "ready": ready,
    }


__all__ = [
    "FINBERT_HUB_DEFAULT",
    "LocalFinbertProvider",
    "NullSentimentProvider",
    "SentimentAnalyzer",
    "SentimentProviderBase",
    "configure_sentiment",
    "get_sentiment_analyzer",
    "resolve_sentiment_model_path",
    "warm_sentiment_analyzer",
]
