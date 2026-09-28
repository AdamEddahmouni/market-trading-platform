"""Local FinBERT headline sentiment for Screener news (S11).

Adapted from the Short Squeeze donor's ``LocalFinbertProvider``
(``apps/research_screener/sentiment_live.py``) with its gaps closed:

* local files only — the model directory must be configured explicitly
  (``IMP_FINBERT_MODEL_PATH``); nothing is ever downloaded from a model hub;
* lazy load on first use, never at application start, under a lock;
* one batching layer, full class probabilities (``top_k=None``);
* explicit model identity: id, revision (hash of the model config), local path basis;
* a load or inference failure is a state, never a fabricated label.

Sentiment describes the language of a headline. It is not a forecast, a
trading signal, or a statement about future returns. "No score" is never
neutral: unscored items stay ``NOT_SCORED`` / ``NOT_CONFIGURED`` / ``UNAVAILABLE``.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

SENTIMENT_VERSION = "news/finbert-sentiment/1.0.0"
MODEL_PATH_ENV = "IMP_FINBERT_MODEL_PATH"
LABELS = ("positive", "neutral", "negative")
BATCH_SIZE = 16
CACHE_SIZE = 4096
MAX_TEXT_CHARS = 512
AGGREGATION_METHOD = ("Counts of FinBERT top labels over scored stories (one score per story, representative "
                      "headline). Dominant = the single most frequent label; a tie for most frequent is MIXED. "
                      "No weighting, no composite score. Language sentiment, not a return forecast.")

CURRENT, NOT_CONFIGURED, UNAVAILABLE, ERROR = "CURRENT", "NOT_CONFIGURED", "UNAVAILABLE", "ERROR"


@dataclass(frozen=True, slots=True)
class SentimentScore:
    label: str                                  # POSITIVE | NEUTRAL | NEGATIVE
    probabilities: dict[str, float]             # positive/neutral/negative, sum ~1
    model_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"state": "SCORED", "label": self.label,
                "probabilities": {key: round(value, 4) for key, value in self.probabilities.items()},
                "model_id": self.model_id}


@dataclass(frozen=True, slots=True)
class LoadedModel:
    classify: Callable[[list[str]], list[list[dict[str, Any]]]]
    model_id: str
    revision: str
    path: str


Loader = Callable[[Path], LoadedModel]


def _default_loader(path: Path) -> LoadedModel:
    # Imported lazily: torch/transformers are optional and heavy.
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline  # type: ignore[import-not-found]

    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(path), local_files_only=True)
    labels = {str(value).lower() for value in (getattr(model.config, "id2label", {}) or {}).values()}
    if not set(LABELS) <= labels:
        raise ValueError("UNSUPPORTED_LABELS")
    classifier = pipeline("text-classification", model=model, tokenizer=tokenizer, top_k=None, device=-1)
    config_bytes = (path / "config.json").read_bytes() if (path / "config.json").is_file() else b""
    name = str(getattr(model.config, "_name_or_path", "") or "")
    model_id = name if name and not Path(name).is_absolute() and not name.startswith((".", "/", "\\")) else path.name

    def classify(texts: list[str]) -> list[list[dict[str, Any]]]:
        return classifier(texts, batch_size=BATCH_SIZE, truncation=True)

    return LoadedModel(classify, model_id or "finbert", hashlib.sha256(config_bytes).hexdigest()[:12], str(path))


class FinbertSentiment:
    """Process-wide lazy FinBERT scorer. Thread-safe; a failed load is sticky until reset."""

    def __init__(self, *, model_path: str | None = None, loader: Loader | None = None,
                 env: Callable[[str], str | None] = os.environ.get) -> None:
        self._configured_path = model_path
        self._loader = loader or _default_loader
        self._env = env
        self._lock = threading.Lock()
        self._model: LoadedModel | None = None
        self._failure: tuple[str, str] | None = None   # (state, reason)
        self._cache: OrderedDict[tuple[str, str], SentimentScore] = OrderedDict()
        self.load_count = 0
        self.inference_calls = 0
        self.last_batch_ms: float | None = None

    def _path(self) -> str | None:
        value = self._configured_path if self._configured_path is not None else (self._env(MODEL_PATH_ENV) or "")
        return value.strip() or None

    def status(self) -> dict[str, Any]:
        """Configuration and load state without triggering a load."""

        path = self._path()
        if self._model is not None:
            return {"state": CURRENT, "reason": None, "model_id": self._model.model_id,
                    "model_revision": self._model.revision, "loaded": True}
        if path is None:
            return {"state": NOT_CONFIGURED, "reason": f"{MODEL_PATH_ENV}_NOT_SET", "model_id": None,
                    "model_revision": None, "loaded": False}
        if not Path(path).is_dir():
            return {"state": NOT_CONFIGURED, "reason": "MODEL_PATH_NOT_FOUND", "model_id": None,
                    "model_revision": None, "loaded": False}
        if self._failure is not None:
            return {"state": self._failure[0], "reason": self._failure[1], "model_id": None,
                    "model_revision": None, "loaded": False}
        return {"state": CURRENT, "reason": "NOT_LOADED_YET", "model_id": None, "model_revision": None, "loaded": False}

    def _ensure_loaded(self) -> LoadedModel | None:
        if self._model is not None or self._failure is not None:
            return self._model
        path = self._path()
        if path is None or not Path(path).is_dir():
            return None
        with self._lock:
            if self._model is not None or self._failure is not None:
                return self._model
            try:
                self.load_count += 1
                self._model = self._loader(Path(path))
            except ImportError:
                self._failure = (UNAVAILABLE, "TRANSFORMERS_NOT_INSTALLED")
            except ValueError as exc:
                self._failure = (UNAVAILABLE, "UNSUPPORTED_LABELS" if "UNSUPPORTED_LABELS" in str(exc) else "MODEL_LOAD_FAILED")
            except Exception:  # noqa: BLE001 — a model failure is a state, never a label
                self._failure = (UNAVAILABLE, "MODEL_LOAD_FAILED")
        return self._model

    def score(self, texts: Sequence[str]) -> list[dict[str, Any]]:
        """One result per text: a SCORED dict, or an explicit non-scored state."""

        status = self.status()
        if status["state"] == NOT_CONFIGURED:
            return [_unscored(NOT_CONFIGURED) for _ in texts]
        model = self._ensure_loaded()
        if model is None:
            state = self.status()["state"]
            return [_unscored(state if state != CURRENT else UNAVAILABLE) for _ in texts]
        results: list[dict[str, Any] | None] = [None] * len(texts)
        pending: list[tuple[int, str, str]] = []
        for index, raw in enumerate(texts):
            text = " ".join(str(raw or "").split())[:MAX_TEXT_CHARS]
            if not text:
                results[index] = _unscored("NOT_SCORED", model.model_id)
                continue
            key = (model.revision, hashlib.sha256(text.encode("utf-8")).hexdigest())
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                results[index] = cached.to_dict()
            else:
                pending.append((index, text, key[1]))
        if pending:
            started = time.perf_counter()
            try:
                self.inference_calls += 1
                outputs = model.classify([text for _, text, _ in pending])
            except Exception:  # noqa: BLE001 — batch failure: those items are ERROR, never a label
                for index, _, _ in pending:
                    results[index] = _unscored(ERROR, model.model_id)
                outputs = None
            self.last_batch_ms = round((time.perf_counter() - started) * 1000, 1)
            if outputs is not None:
                for (index, _text, digest), output in zip(pending, outputs):
                    parsed = _parse(output, model.model_id)
                    if parsed is None:
                        results[index] = _unscored(ERROR, model.model_id)
                        continue
                    self._cache[(model.revision, digest)] = parsed
                    if len(self._cache) > CACHE_SIZE:
                        self._cache.popitem(last=False)
                    results[index] = parsed.to_dict()
        return [item if item is not None else _unscored(ERROR, model.model_id) for item in results]


def _unscored(state: str, model_id: str | None = None) -> dict[str, Any]:
    return {"state": state, "label": None, "probabilities": None, "model_id": model_id}


def _parse(output: Any, model_id: str) -> SentimentScore | None:
    rows = output if isinstance(output, list) else [output]
    probabilities: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            return None
        label = str(row.get("label") or "").lower()
        try:
            probabilities[label] = float(row.get("score"))
        except (TypeError, ValueError):
            return None
    if not set(LABELS) <= set(probabilities):
        return None
    top = max(LABELS, key=lambda name: probabilities[name])
    return SentimentScore(top.upper(), {name: probabilities[name] for name in LABELS}, model_id)


def summarize(scores: Sequence[dict[str, Any]], *, model_status: dict[str, Any]) -> dict[str, Any]:
    """Transparent counts over per-story scores. No opaque composite score."""

    counts = {"positive": 0, "neutral": 0, "negative": 0}
    scored = 0
    for item in scores:
        if item.get("state") == "SCORED" and item.get("label"):
            counts[str(item["label"]).lower()] += 1
            scored += 1
    unscored = len(scores) - scored
    if model_status.get("state") == NOT_CONFIGURED:
        state, reason = NOT_CONFIGURED, model_status.get("reason")
    elif model_status.get("state") in (UNAVAILABLE, ERROR) and not scored:
        state, reason = UNAVAILABLE, model_status.get("reason")
    elif not scores:
        state, reason = "INSUFFICIENT_DATA", "NO_STORIES_IN_WINDOW"
    elif not scored:
        state, reason = UNAVAILABLE, "NO_STORY_SCORED"
    else:
        state, reason = ("CURRENT", None) if not unscored else ("PARTIAL", "SOME_STORIES_NOT_SCORED")
    dominant = None
    if scored:
        top = max(counts.values())
        leaders = [name for name, count in counts.items() if count == top]
        dominant = leaders[0].upper() if len(leaders) == 1 else "MIXED"
    return {"state": state, "reason": reason, "model_id": model_status.get("model_id"), "counts": counts,
            "scored": scored, "unscored": unscored, "dominant": dominant, "method": AGGREGATION_METHOD}


_DEFAULT: FinbertSentiment | None = None
_DEFAULT_LOCK = threading.Lock()


def finbert_sentiment() -> FinbertSentiment:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = FinbertSentiment()
        return _DEFAULT


__all__ = ["AGGREGATION_METHOD", "FinbertSentiment", "LABELS", "LoadedModel", "MODEL_PATH_ENV", "SENTIMENT_VERSION",
           "SentimentScore", "finbert_sentiment", "summarize"]
