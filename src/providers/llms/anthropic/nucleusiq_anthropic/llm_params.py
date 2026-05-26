"""Optional merged kwargs for Claude (beta headers, sampling, Phase B knobs)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

#: Mapping from the friendly ``effort`` enum to the Anthropic
#: ``thinking.budget_tokens`` ranges suggested by the docs.  These are
#: starting points — users with strict cost budgets should pass
#: ``thinking={"type": "enabled", "budget_tokens": N}`` directly.
_THINKING_EFFORT_BUDGETS: dict[str, int] = {
    "low": 2_000,
    "medium": 8_000,
    "high": 32_000,
}


@dataclass
class AnthropicLLMParams:
    """Fine-grained Anthropic knobs merged into ``BaseAnthropic.call`` / streaming.

    Phase B (0.2.0) additions:

    * ``thinking`` — request extended-thinking content blocks. Accepts
      a dict literal (``{"type": "enabled", "budget_tokens": 8000}``),
      one of the ``"low" | "medium" | "high"`` effort presets, or
      ``True`` (alias for ``"medium"``).
    * ``cache_tools`` / ``cache_system`` — enable Anthropic prompt
      caching by attaching ``cache_control`` blocks to the last tool
      definition and/or the system prompt respectively.
    * ``strict_tools`` — request strict tool-use schema enforcement
      (forwarded onto every custom tool definition; ignored by models
      that do not support it).
    * ``disable_parallel_tool_use`` — request Claude *not* to emit
      parallel ``tool_use`` blocks in a single turn.
    """

    # --- legacy knobs (Phase A) -------------------------------------- #
    top_k: int | None = None
    anthropic_beta: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)

    # --- Phase B knobs ---------------------------------------------- #
    thinking: Any | None = None
    cache_tools: bool = False
    cache_system: bool = False
    strict_tools: bool = False
    disable_parallel_tool_use: bool = False

    def _resolved_thinking(self) -> dict[str, Any] | None:
        """Normalise ``thinking`` into the dict payload Anthropic expects."""
        t = self.thinking
        if t is None or t is False:
            return None
        if isinstance(t, bool):
            # ``True`` → medium-effort default
            return {
                "type": "enabled",
                "budget_tokens": _THINKING_EFFORT_BUDGETS["medium"],
            }
        if isinstance(t, str):
            level = t.strip().lower()
            budget = _THINKING_EFFORT_BUDGETS.get(level)
            if budget is None:
                raise ValueError(
                    "AnthropicLLMParams.thinking string must be one of "
                    f"{sorted(_THINKING_EFFORT_BUDGETS)} — got {t!r}."
                )
            return {"type": "enabled", "budget_tokens": budget}
        if isinstance(t, dict):
            payload = dict(t)
            payload.setdefault("type", "enabled")
            return payload
        raise TypeError(
            "AnthropicLLMParams.thinking must be None, bool, an effort string, "
            f"or a dict — got {type(t).__name__}."
        )

    def to_call_kwargs(self) -> dict[str, Any]:
        """Return kwargs merged upstream of ``build_create_kwargs``.

        Uses private keys prefixed with underscores so Anthropic rejects no
        parameters — :class:`~nucleusiq_anthropic.nb_anthropic.base.BaseAnthropic`
        strips ``_merged_extra_headers`` and the Phase B markers before the
        wire layer touches them.
        """

        merged: dict[str, Any] = {}
        if self.top_k is not None:
            merged["top_k"] = self.top_k
        beta = self.anthropic_beta
        if isinstance(beta, str) and beta.strip():
            merged["anthropic_beta"] = beta.strip()
        if self.extra_headers:
            merged["_merged_extra_headers"] = dict(self.extra_headers)

        thinking_payload = self._resolved_thinking()
        if thinking_payload is not None:
            merged["thinking"] = thinking_payload

        if self.cache_tools:
            merged["_cache_tools"] = True
        if self.cache_system:
            merged["_cache_system"] = True
        if self.strict_tools:
            merged["_strict_tools"] = True
        if self.disable_parallel_tool_use:
            merged["_disable_parallel_tool_use"] = True

        return merged


# Public alias for the literal type used by docs/typing — keeps the
# discoverable name short for users.
ThinkingEffort = Literal["low", "medium", "high"]

__all__ = ["AnthropicLLMParams", "ThinkingEffort"]
