from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from apps.research_screener.config import SAFE_DEFAULTS, resolve_application_config
from apps.research_screener.sentiment_live import (
    FINBERT_HUB_DEFAULT,
    KeywordSentimentProvider,
    LocalFinbertProvider,
    SentimentAnalyzer,
    resolve_sentiment_model_path,
)


def test_resolve_sentiment_model_path_prefers_explicit_directory(tmp_path: Path):
    model_dir = tmp_path / "finbert"
    model_dir.mkdir()
    (model_dir / "config.json").write_text(json.dumps({"id2label": {"0": "positive"}}))
    resolved = resolve_sentiment_model_path(str(model_dir))
    assert resolved == str(model_dir.resolve())


def test_resolve_sentiment_model_path_falls_back_to_hub():
    assert resolve_sentiment_model_path(None) == FINBERT_HUB_DEFAULT


def test_local_finbert_provider_lazy_loads_via_analyzer(tmp_path: Path):
    model_dir = tmp_path / "checkpoint"
    model_dir.mkdir()
    provider = LocalFinbertProvider(model_path=str(model_dir))
    analyzer = SentimentAnalyzer(provider=provider)
    mock_pipeline = MagicMock(
        return_value=[{"label": "positive", "score": 0.91}]
    )
    provider._model_loaded = True
    provider._pipeline = mock_pipeline

    results = analyzer.analyze_headlines([{"headline": "Stock surges on upgrade"}])

    assert results[0]["sentiment_label"] == "positive"
    mock_pipeline.assert_called()


def test_build_sentiment_analyzer_uses_local_finbert_by_default():
    config = resolve_application_config(
        environ={
            **SAFE_DEFAULTS,
            "SQUEEZE_APP_MODE": "LOCAL_FULL",
            "SENTIMENT_ENABLED": "true",
            "SENTIMENT_PROVIDER": "local_finbert",
        },
    )
    analyzer = config.build_sentiment_analyzer()
    assert isinstance(analyzer._provider, LocalFinbertProvider)
    assert analyzer._provider._model_path == FINBERT_HUB_DEFAULT


def test_build_sentiment_analyzer_keyword_override():
    config = resolve_application_config(
        environ={
            **SAFE_DEFAULTS,
            "SQUEEZE_APP_MODE": "LOCAL_FULL",
            "SENTIMENT_ENABLED": "true",
            "SENTIMENT_PROVIDER": "keyword",
        },
    )
    analyzer = config.build_sentiment_analyzer()
    assert isinstance(analyzer._provider, KeywordSentimentProvider)
