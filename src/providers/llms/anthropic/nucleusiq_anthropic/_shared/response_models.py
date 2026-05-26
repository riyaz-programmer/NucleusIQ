"""Normalised Messages API responses matching the ``BaseLLM`` contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: str = "function"
    function: ToolCallFunction


class AssistantMessage(BaseModel):
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None

    model_config = ConfigDict(populate_by_name=True)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [tc.model_dump() for tc in self.tool_calls]
        return d


class UsageInfo(BaseModel):
    """Token usage roll-up surfaced on every normalised response.

    ``cached_tokens`` is the aggregate ``cache_read + cache_creation``
    figure (kept for backwards compatibility); ``cache_read_input_tokens``
    and ``cache_creation_input_tokens`` expose the breakdown for
    callers wiring NucleusIQ's ``LLMCallRecord`` enrichment.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class ServerToolCall(BaseModel):
    """A Claude server-side tool invocation (``web_search``, …).

    Anthropic executes these tools on its own infrastructure.  Surfaced
    separately from :class:`ToolCall` so the NucleusIQ agent loop can
    report them as ``ToolCallRecord(executed_by="provider")`` rather
    than try to dispatch them locally.
    """

    id: str
    name: str
    input: dict[str, Any] = {}
    result: Any | None = None


class _Choice(BaseModel):
    message: AssistantMessage


class AnthropicLLMResponse(BaseModel):
    """Structured response returned by ``BaseAnthropic.call``."""

    choices: list[_Choice]
    usage: UsageInfo | None = None
    model: str | None = None
    response_id: str | None = None
    # --- Phase B / 0.2.0 observability ------------------------------ #
    stop_reason: str | None = None
    organization_id: str | None = None
    server_tool_calls: list[ServerToolCall] = []
    # ``request_id`` is an alias for ``response_id`` for symmetry with
    # other providers (OpenAI exposes ``id`` which lines up); both
    # surface the same value.

    @property
    def request_id(self) -> str | None:
        return self.response_id
