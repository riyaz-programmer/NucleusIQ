"""
NucleusIQ framework showcase — devil's advocate agent.

Demonstrates: Agent, ExecutionMode, ZeroShotPrompt, @tool pack tools,
ModelCallLimitPlugin, ToolCallLimitPlugin, ToolRetryPlugin, MemoryFactory
(sliding_window | summary | summary_window | full_history | token_budget).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from nucleusiq.agents.agent import Agent
from nucleusiq.agents.config import AgentConfig, ExecutionMode
from nucleusiq.agents.task import Task
from nucleusiq.agents.usage.pricing import CostTracker
from nucleusiq.memory.factory import MemoryFactory, MemoryStrategy
from nucleusiq.plugins.builtin.model_call_limit import ModelCallLimitPlugin
from nucleusiq.plugins.builtin.tool_call_limit import ToolCallLimitPlugin
from nucleusiq.plugins.builtin.tool_retry import ToolRetryPlugin
from nucleusiq.prompts.zero_shot import ZeroShotPrompt
from pydantic import BaseModel, Field

from .pack_tools import PackContext, make_pack_tools
from .paths import OBJECTIONS_OUTPUT, PACK_OUTPUT, PREBRIEF_OUTPUT

# ---------------------------------------------------------------------------
# Structured preload output (optional parse)
# ---------------------------------------------------------------------------


class ObjectionRow(BaseModel):
    theme: str
    severity: str
    claim: str
    section_id: str
    challenge_question: str


class ObjectionRegister(BaseModel):
    objections: list[ObjectionRow] = Field(min_length=3, max_length=12)
    top_questions_for_chair: list[str] = Field(min_length=3, max_length=8)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CHAIR_SYSTEM = """You are the board CHAIR's devil's advocate — not a neutral summarizer.

Your job: argue why the chair should NOT approve the deal as presented (full $1M, RM's $900K, or credit's $600K without proof).

Pack includes:
- credit_memo, rm_memo, credit_analysis, commentary_thread
- analyst_memos (five board analysts), issuers / FY2025 financials

Rules:
- Use tools first. ONLY facts from the pack; cite section_id on every material point.
- Lead with numbered objections. End with 3 sharp questions for the chair.
- Exploit MEMO_MISMATCH between credit, RM, analysts, and financials.
- MISSING_INFO when data is absent — never invent market prices.
- Tone: direct, skeptical, professional."""

PRELOAD_TASK = """Read the frozen pack (tools: summarize_credit_and_rm, list_commentary_thread, get_pack_section).

Produce a T-1 chair pre-brief attacking the APPROVE case:
1) Credit vs RM mismatch (amounts, TCS/HCL tilt)
2) Credit/RM claims vs FY2025 financial extracts
3) Why $1M or $900K today is wrong; conditions to vote yes

Be adversarial. Cite section_ids. Include 5+ objections and 5 chair questions."""


# ---------------------------------------------------------------------------
# Framework wiring
# ---------------------------------------------------------------------------

MEMORY_CHOICES = {
    "sliding_window": MemoryStrategy.SLIDING_WINDOW,
    "summary": MemoryStrategy.SUMMARY,
    "summary_window": MemoryStrategy.SUMMARY_WINDOW,
    "full_history": MemoryStrategy.FULL_HISTORY,
    "token_budget": MemoryStrategy.TOKEN_BUDGET,
}


def gemini_llm():
    from nucleusiq_gemini import BaseGemini

    return BaseGemini(
        model_name=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        temperature=float(os.environ.get("GEMINI_TEMPERATURE", "0.2")),
    )


def showcase_plugins(*, max_model_calls: int = 25, max_tool_calls: int = 35) -> list:
    """NucleusIQ safety + retry plugins (no hand-rolled retry loops)."""
    return [
        ModelCallLimitPlugin(max_calls=max_model_calls),
        ToolCallLimitPlugin(max_calls=max_tool_calls),
        ToolRetryPlugin(
            max_retries=int(os.environ.get("TOOL_MAX_RETRIES", "2")),
            base_delay=float(os.environ.get("TOOL_RETRY_DELAY", "1.0")),
        ),
    ]


def create_memory(strategy_key: str | None = None):
    """MemoryFactory — default sliding_window; override with MEMORY_STRATEGY env."""
    key = (strategy_key or os.environ.get("MEMORY_STRATEGY", "sliding_window")).lower()
    if key not in MEMORY_CHOICES:
        raise ValueError(f"MEMORY_STRATEGY must be one of: {', '.join(MEMORY_CHOICES)}")

    strategy = MEMORY_CHOICES[key]
    llm = gemini_llm()

    if strategy == MemoryStrategy.SLIDING_WINDOW:
        return MemoryFactory.create_memory(
            strategy, window_size=int(os.environ.get("MEMORY_WINDOW_SIZE", "24"))
        )
    if strategy == MemoryStrategy.SUMMARY:
        return MemoryFactory.create_memory(strategy, llm=llm, summary_max_tokens=512)
    if strategy == MemoryStrategy.SUMMARY_WINDOW:
        return MemoryFactory.create_memory(
            strategy,
            llm=llm,
            window_size=int(os.environ.get("MEMORY_WINDOW_SIZE", "10")),
        )
    if strategy == MemoryStrategy.TOKEN_BUDGET:
        return MemoryFactory.create_memory(
            strategy, max_tokens=int(os.environ.get("MEMORY_MAX_TOKENS", "4096"))
        )
    return MemoryFactory.create_memory(strategy)


def chair_system_prompt() -> str:
    base = CHAIR_SYSTEM
    if PREBRIEF_OUTPUT.is_file():
        base += (
            "\n\n--- T-1 PRE-BRIEF (context only; still cite pack section_ids) ---\n"
            + PREBRIEF_OUTPUT.read_text(encoding="utf-8")[:6000]
        )
    return base


def build_showcase_agent(
    ctx: PackContext,
    mode: ExecutionMode,
    *,
    memory=None,
    name: str = "devils-advocate-showcase",
) -> Agent:
    """Single Agent factory used by preload and console chat."""
    config = AgentConfig(
        execution_mode=mode,
        llm_max_output_tokens=int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "8192")),
        verbose=os.environ.get("AGENT_VERBOSE", "").lower() in {"1", "true", "yes"},
    )
    return Agent(
        name=name,
        role="Chair devil's advocate assistant",
        objective="NucleusIQ showcase — stress-test IT allocation using frozen committee pack.",
        llm=gemini_llm(),
        tools=make_pack_tools(ctx),
        memory=memory,
        prompt=ZeroShotPrompt().configure(
            system=chair_system_prompt(),
            user=(
                "Live board meeting chat. Use pack tools. "
                "Conversation memory is handled by NucleusIQ MemoryFactory — use prior context."
            ),
        ),
        config=config,
        plugins=showcase_plugins(
            max_model_calls=30 if mode == ExecutionMode.STANDARD else 20,
        ),
    )


def format_usage(agent: Agent) -> str:
    try:
        u = agent.last_usage
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        breakdown = CostTracker().estimate(u, model=model)
        if breakdown.pricing_available:
            return (
                f"tokens in={u.total.prompt_tokens} out={u.total.completion_tokens} "
                f"| est. ${breakdown.total_cost:.4f}"
            )
        return f"tokens in={u.total.prompt_tokens} out={u.total.completion_tokens}"
    except Exception:
        return "usage n/a"


# ---------------------------------------------------------------------------
# Preload (Standard mode, no session memory)
# ---------------------------------------------------------------------------


async def run_preload(pack_path: Path | None = None) -> dict[str, Any]:
    path = pack_path or PACK_OUTPUT
    ctx = PackContext(path)
    agent = build_showcase_agent(
        ctx, ExecutionMode.STANDARD, name="devils-advocate-preload"
    )
    await agent.initialize()

    result = await agent.execute(
        Task(id="preload-devils-advocate", objective=PRELOAD_TASK)
    )
    text = str(result.output or "")
    PREBRIEF_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PREBRIEF_OUTPUT.write_text(text, encoding="utf-8")

    try:
        start, end = text.find("{"), text.rfind("}") + 1
        if start >= 0 < end:
            reg = ObjectionRegister.model_validate_json(text[start:end])
            OBJECTIONS_OUTPUT.write_text(
                reg.model_dump_json(indent=2), encoding="utf-8"
            )
    except Exception:
        OBJECTIONS_OUTPUT.write_text(
            json.dumps({"raw": text}, indent=2), encoding="utf-8"
        )

    return {
        "status": str(result.status),
        "prebrief_path": str(PREBRIEF_OUTPUT),
        "usage": format_usage(agent),
        "framework": {
            "mode": "STANDARD",
            "plugins": ["ModelCallLimit", "ToolCallLimit", "ToolRetry"],
            "memory": None,
        },
    }


# ---------------------------------------------------------------------------
# Console chat (Direct mode + MemoryFactory)
# ---------------------------------------------------------------------------


class ChairChatSession:
    """One Agent + one memory strategy for multi-turn chair chat."""

    def __init__(
        self, pack_path: Path | None = None, memory_strategy: str | None = None
    ) -> None:
        self.pack_path = pack_path or PACK_OUTPUT
        self.memory_strategy = memory_strategy or os.environ.get(
            "MEMORY_STRATEGY", "sliding_window"
        )
        self.ctx = PackContext(self.pack_path)
        self.memory = create_memory(self.memory_strategy)
        self.agent = build_showcase_agent(
            self.ctx,
            ExecutionMode.DIRECT,
            memory=self.memory,
            name="devils-advocate-chat",
        )
        self.cost_tracker = CostTracker()
        self._initialized = False
        self._turn = 0

    @property
    def framework_info(self) -> dict[str, str]:
        return {
            "execution_mode": "DIRECT",
            "memory": self.memory_strategy,
            "memory_class": type(self.memory).__name__,
            "plugins": "ModelCallLimit, ToolCallLimit, ToolRetry",
        }

    async def start(self) -> None:
        if not self._initialized:
            await self.agent.initialize()
            self._initialized = True

    async def ask(self, user_message: str) -> tuple[str, str]:
        """Returns (reply, usage_summary). Retries are handled by ToolRetryPlugin."""
        await self.start()
        self._turn += 1
        result = await self.agent.execute(
            Task(id=f"chair-chat-{self._turn}", objective=user_message)
        )
        reply = str(result.output or "(no response)")
        return reply, format_usage(self.agent)

    def reset_memory(self) -> None:
        self.memory.clear()
        self._turn = 0
