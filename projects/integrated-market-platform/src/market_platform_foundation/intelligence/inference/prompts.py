"""Governed prompt registry with deterministic versioning and hashes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import IntelligenceTaskType
from .hashing import prompt_hash


OUTPUT_SCHEMA_VERSION = "intelligence/inference/output/1.0.0"


_COMMON_RULES = """
Rules (mandatory):
1. Use ONLY the curated articles and metadata supplied below.
2. Do NOT search the web, fetch URLs, or assume information beyond the packet.
3. Do NOT assume future information beyond the as-of time.
4. Respect the as-of time when reasoning about event relevance.
5. Return ONLY valid JSON matching the required schema — no markdown fences.
6. Distinguish uncertainty; do not claim certainty unsupported by input.
7. Do NOT generate trading orders, position sizes, or execution instructions.
8. Do NOT output BUY, SELL, SHORT, LONG, QUANTITY, or LIMIT_PRICE fields.
9. Do NOT treat source trust tier as proof of truth.
10. Do NOT invent missing facts.
11. Preserve distinction between deterministic catalyst matches and your interpretation.
12. Model confidence is self-reported and NOT empirically calibrated probability.
""".strip()


@dataclass(frozen=True, slots=True)
class PromptDefinition:
    prompt_id: str
    task_type: IntelligenceTaskType
    version: str
    template: str
    output_schema_version: str = OUTPUT_SCHEMA_VERSION
    description: str = ""

    @property
    def content_hash(self) -> str:
        return prompt_hash(
            prompt_id=self.prompt_id,
            version=self.version,
            template=self.template,
        )


def _news_sentiment_template() -> str:
    return (
        "You are a read-only market intelligence analyst for a governed trading research platform.\n"
        "Authority: ANALYSIS_ONLY — zero broker, Paper, Live, or execution authority.\n\n"
        + _COMMON_RULES
        + """

Task: NEWS_SENTIMENT — classify aggregate sentiment from curated catalyst-filtered news.

Required JSON schema:
{
  "sentiment_label": "VERY_BEARISH|BEARISH|NEUTRAL|BULLISH|VERY_BULLISH",
  "sentiment_score": number between -1.0 and 1.0,
  "rationale": "concise explanation",
  "model_confidence": number between 0.0 and 1.0,
  "warnings": ["optional warning strings"]
}

As-of time: {{as_of}}
Instrument context: {{instrument_ids}}
Articles (JSON): {{articles_json}}
"""
    )


def _news_catalyst_template() -> str:
    return (
        "You are a read-only market intelligence analyst for a governed trading research platform.\n"
        "Authority: ANALYSIS_ONLY — zero broker, Paper, Live, or execution authority.\n\n"
        + _COMMON_RULES
        + """

Task: NEWS_CATALYST_ANALYSIS — interpret deterministic catalyst matches without overwriting them.

Required JSON schema:
{
  "catalyst_interpretation": "higher-level interpretation of catalyst relevance",
  "catalyst_strength": "NONE|LOW|MODERATE|HIGH",
  "sentiment_label": "VERY_BEARISH|BEARISH|NEUTRAL|BULLISH|VERY_BULLISH",
  "rationale": "concise explanation",
  "model_confidence": number between 0.0 and 1.0,
  "warnings": ["optional warning strings"]
}

As-of time: {{as_of}}
Instrument context: {{instrument_ids}}
Articles (JSON): {{articles_json}}
"""
    )


def _news_market_impact_template() -> str:
    return (
        "You are a read-only market intelligence analyst for a governed trading research platform.\n"
        "Authority: ANALYSIS_ONLY — zero broker, Paper, Live, or execution authority.\n\n"
        + _COMMON_RULES
        + """

Task: NEWS_MARKET_IMPACT — assess likely non-executable market impact categories only.

Required JSON schema:
{
  "market_impact_level": "NONE|LOW|MODERATE|HIGH",
  "impact_horizon": "INTRADAY|SHORT_TERM|MEDIUM_TERM|UNKNOWN",
  "sentiment_label": "VERY_BEARISH|BEARISH|NEUTRAL|BULLISH|VERY_BULLISH",
  "rationale": "concise explanation",
  "model_confidence": number between 0.0 and 1.0,
  "warnings": ["optional warning strings"]
}

As-of time: {{as_of}}
Instrument context: {{instrument_ids}}
Articles (JSON): {{articles_json}}
"""
    )


DEFAULT_PROMPTS: tuple[PromptDefinition, ...] = (
    PromptDefinition(
        prompt_id="news.sentiment.v1",
        task_type=IntelligenceTaskType.NEWS_SENTIMENT,
        version="1.0.0",
        template=_news_sentiment_template(),
        description="Aggregate sentiment from curated news articles",
    ),
    PromptDefinition(
        prompt_id="news.catalyst.v1",
        task_type=IntelligenceTaskType.NEWS_CATALYST_ANALYSIS,
        version="1.0.0",
        template=_news_catalyst_template(),
        description="Interpret deterministic catalyst matches",
    ),
    PromptDefinition(
        prompt_id="news.market_impact.v1",
        task_type=IntelligenceTaskType.NEWS_MARKET_IMPACT,
        version="1.0.0",
        template=_news_market_impact_template(),
        description="Non-executable market impact assessment",
    ),
)


class PromptRegistry:
    """Versioned prompt lookup — content changes require explicit version bumps."""

    def __init__(self, prompts: tuple[PromptDefinition, ...] | None = None) -> None:
        self._prompts = prompts or DEFAULT_PROMPTS
        self._by_task: dict[IntelligenceTaskType, PromptDefinition] = {}
        self._by_id: dict[str, PromptDefinition] = {}
        for prompt in self._prompts:
            self._by_task[prompt.task_type] = prompt
            self._by_id[prompt.prompt_id] = prompt

    def get_for_task(self, task_type: IntelligenceTaskType) -> PromptDefinition:
        prompt = self._by_task.get(task_type)
        if prompt is None:
            raise KeyError(f"PROMPT_NOT_FOUND:{task_type.value}")
        return prompt

    def get_by_id(self, prompt_id: str) -> PromptDefinition:
        prompt = self._by_id.get(prompt_id)
        if prompt is None:
            raise KeyError(f"PROMPT_NOT_FOUND:{prompt_id}")
        return prompt

    def render(
        self,
        prompt: PromptDefinition,
        *,
        as_of: str,
        instrument_ids: tuple[str, ...],
        articles_json: str,
    ) -> str:
        return (
            prompt.template.replace("{{as_of}}", as_of)
            .replace("{{instrument_ids}}", ", ".join(instrument_ids) or "NONE")
            .replace("{{articles_json}}", articles_json)
        )

    def list_prompts(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "prompt_id": prompt.prompt_id,
                "task_type": prompt.task_type.value,
                "version": prompt.version,
                "content_hash": prompt.content_hash,
                "output_schema_version": prompt.output_schema_version,
                "description": prompt.description,
            }
            for prompt in self._prompts
        )


__all__ = [
    "DEFAULT_PROMPTS",
    "OUTPUT_SCHEMA_VERSION",
    "PromptDefinition",
    "PromptRegistry",
]
