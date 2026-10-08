"""What each hosted Claude model accepts on the Messages API, and the request built from it.

This is the only place a Claude model id decides a request parameter. A model's row records just the
capabilities IMP uses. A model with no row has no known request shape: it is refused before any network
call, never sent a guessed body and never replaced by another model.

``build_request`` returns the generation body. ``count_request`` is that same body without the fields the
token-count endpoint does not take, so a count measures the request that would be generated from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import IntelligenceTaskType

TOOL_NAME = "record_synthesis"
UNSUPPORTED = "MODEL_REQUEST_CONTRACT_UNSUPPORTED"
# The structured-output contract of each task. A model that cannot meet a task's contract is refused for that task.
STRICT_TOOL_SCHEMA = "STRICT_TOOL_SCHEMA"      # the tool input is grammar-constrained to the exact schema
TOOL_SCHEMA = "TOOL_SCHEMA"                    # the tool input is schema-typed; the application validator decides
# Output room for a model that reasons before it answers: max_tokens caps reasoning and answer together.
THINKING_HEADROOM = 8_192
SYSTEM = "You write grounded evidence syntheses. Use only the supplied packet and record the result with the tool."
# Where the tool call cannot be forced, the instruction asks for it and a reply without the call is rejected.
SYSTEM_TOOL_REQUIRED = (SYSTEM + f" You must answer by calling the {TOOL_NAME} tool exactly once. Never answer in text.")
# Fields of a generation body that the token-count endpoint does not accept.
COUNT_EXCLUDED = ("max_tokens", "temperature")


@dataclass(frozen=True, slots=True)
class ClaudeModel:
    model: str
    temperature: bool            # accepts an explicit temperature
    forced_tool_choice: bool     # accepts tool_choice {"type": "tool"}
    strict_tools: bool           # accepts strict tool input schemas
    thinks_by_default: bool      # reasons before answering when no thinking field is sent
    count_tokens: bool           # served by the token-count endpoint
    context_window: int          # input tokens


# Every Claude model the engine picker offers (synthesis_engines.ENGINE_SPECS["anthropic"]).
CLAUDE_MODELS: dict[str, ClaudeModel] = {item.model: item for item in (
    ClaudeModel("claude-haiku-4-5-20251001", temperature=True, forced_tool_choice=True, strict_tools=True,
                thinks_by_default=False, count_tokens=True, context_window=200_000),
    # Sonnet 5.5 and Opus 5.5 reject an explicit temperature and a forced tool call, and always reason first.
    ClaudeModel("claude-sonnet-5-5", temperature=False, forced_tool_choice=False, strict_tools=True,
                thinks_by_default=True, count_tokens=True, context_window=1_000_000),
    ClaudeModel("claude-opus-5-5", temperature=False, forced_tool_choice=False, strict_tools=True,
                thinks_by_default=True, count_tokens=True, context_window=1_000_000),
)}


class ModelRequestContractUnsupported(ValueError):
    """The selected model cannot carry the task's request contract. Carries what the operator needs to know."""

    def __init__(self, model: str, contract: str, capability: str) -> None:
        super().__init__(UNSUPPORTED)
        self.model, self.contract, self.capability = model, contract, capability

    def details(self) -> dict[str, Any]:
        return {"selected_model": self.model, "required_contract": self.contract,
                "unsupported_capability": self.capability}


def required_contract(task_type: IntelligenceTaskType) -> str:
    return STRICT_TOOL_SCHEMA if task_type == IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION else TOOL_SCHEMA


def model_contract(model: str, task_type: IntelligenceTaskType) -> ClaudeModel:
    """The model's capabilities for this task, or ``ModelRequestContractUnsupported``."""

    contract = required_contract(task_type)
    capabilities = CLAUDE_MODELS.get(model)
    if capabilities is None:
        raise ModelRequestContractUnsupported(model, contract, "MODEL_NOT_IN_CAPABILITY_TABLE")
    if contract == STRICT_TOOL_SCHEMA and not capabilities.strict_tools:
        raise ModelRequestContractUnsupported(model, contract, "STRICT_TOOL_SCHEMA")
    return capabilities


def contract_status(model: str, task_type: IntelligenceTaskType) -> dict[str, Any]:
    """Whether the model can run the task, as data. Calls nothing."""

    try:
        model_contract(model, task_type)
    except ModelRequestContractUnsupported as exc:
        return {"supported": False, "reason": UNSUPPORTED, **exc.details()}
    return {"supported": True, "reason": None, "selected_model": model,
            "required_contract": required_contract(task_type), "unsupported_capability": None}


def output_tokens(model: str, max_tokens: int) -> int:
    """The request's max_tokens: the answer bound, plus reasoning room where the model reasons by default."""

    capabilities = CLAUDE_MODELS.get(model)
    return int(max_tokens) + (THINKING_HEADROOM if capabilities is not None and capabilities.thinks_by_default else 0)


def build_request(model: str, *, task_type: IntelligenceTaskType, input_schema: dict[str, Any], rendered_prompt: str,
                  max_tokens: int) -> dict[str, Any]:
    """The Messages API body for this model and task. Only parameters the model accepts are present."""

    capabilities = model_contract(model, task_type)
    tool: dict[str, Any] = {"name": TOOL_NAME, "description": "Record the grounded synthesis of the supplied evidence.",
                            "input_schema": input_schema}
    if required_contract(task_type) == STRICT_TOOL_SCHEMA:
        tool["strict"] = True
    body: dict[str, Any] = {"model": model, "max_tokens": output_tokens(model, max_tokens)}
    if capabilities.temperature:
        body["temperature"] = 0
    body["system"] = SYSTEM if capabilities.forced_tool_choice else SYSTEM_TOOL_REQUIRED
    body["messages"] = [{"role": "user", "content": rendered_prompt}]
    body["tools"] = [tool]
    body["tool_choice"] = ({"type": "tool", "name": TOOL_NAME} if capabilities.forced_tool_choice
                           else {"type": "auto", "disable_parallel_tool_use": True})
    return body


def count_request(body: dict[str, Any]) -> dict[str, Any]:
    """The token-count body for a generation body: identical but for the fields that endpoint does not take."""

    return {key: value for key, value in body.items() if key not in COUNT_EXCLUDED}


__all__ = ["CLAUDE_MODELS", "COUNT_EXCLUDED", "STRICT_TOOL_SCHEMA", "SYSTEM", "SYSTEM_TOOL_REQUIRED",
           "THINKING_HEADROOM", "TOOL_NAME", "TOOL_SCHEMA", "UNSUPPORTED", "ClaudeModel",
           "ModelRequestContractUnsupported", "build_request", "contract_status", "count_request",
           "model_contract", "output_tokens", "required_contract"]
