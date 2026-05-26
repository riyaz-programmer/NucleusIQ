# nucleusiq-groq

**Groq inference provider** for [NucleusIQ](https://github.com/nucleusbox/NucleusIQ): Chat Completions via Groq’s **OpenAI-compatible** API, using Groq’s official **`groq`** Python SDK (`AsyncGroq` / `Groq`).

**Status:** **0.1.0b1** (public **beta** / pre-release). Requires **`nucleusiq>=0.7.9`**.

Design, phased roadmap (Phase A vs B), and API caveats: [`docs/design/GROQ_PROVIDER.md`](../../../../docs/design/GROQ_PROVIDER.md) (repo root).

---

## Install

**PyPI (when published):**

```bash
pip install nucleusiq nucleusiq-groq
```

**Monorepo (editable):**

```bash
cd src/providers/inference/groq
uv sync --group dev
```

Core is pulled via `[tool.uv.sources]` as an editable path dependency; for `pip`-only local installs, install `nucleusiq` from `src/nucleusiq` first, then this package.

---

## Configuration

| Variable | Purpose |
|----------|---------|
| **`GROQ_API_KEY`** | Required. Groq API key. |
| **`GROQ_MODEL`** | Optional. Default for chat/tool examples: `llama-3.3-70b-versatile`. |
| **`GROQ_MODEL_STRUCTURED`** | Optional. Model for **`json_schema`** structured output (example `05` defaults to `openai/gpt-oss-20b` if unset). |

Unsupported Chat Completions fields (e.g. `logit_bias`, `messages[].name`) are stripped or rejected at the wire layer; see the design doc.

---

## Usage

```python
import asyncio
from nucleusiq.agents import Agent
from nucleusiq.agents.config import AgentConfig, ExecutionMode
from nucleusiq.agents.task import Task
from nucleusiq.prompts.zero_shot import ZeroShotPrompt
from nucleusiq_groq import BaseGroq, GroqLLMParams

async def main() -> None:
    llm = BaseGroq(model_name="llama-3.3-70b-versatile", async_mode=True)
    agent = Agent(
        name="demo",
        prompt=ZeroShotPrompt(),
        llm=llm,
        config=AgentConfig(
            execution_mode=ExecutionMode.DIRECT,
            llm_params=GroqLLMParams(temperature=0.2),
        ),
    )
    await agent.initialize()
    result = await agent.execute(Task(id="1", objective="Capital of France in one short phrase."))
    print(result.output)

asyncio.run(main())
```

---

## Phase A (this stable line — `0.1.0`)

- **`BaseGroq`** — `call` / `call_stream`, tool calling, structured output (`response_format` / Pydantic).
- **`GroqLLMParams`** — typed, `extra="forbid"`; merges into provider calls.
- **Local function tools** — OpenAI-style tool JSON; assistant `tool_calls` normalized for Groq before each request.
- **Retries** — rate-limit and transient errors with exponential backoff; **429** + **`Retry-After`** on non-stream and **streaming open**; errors mapped to NucleusIQ `LLMError` types.
- **Hosted tool IDs** — `nucleusiq_groq.tools.GROQ_COMPOUND_HOSTED_TOOL_IDS` / `GROQ_GPT_OSS_HOSTED_TOOL_IDS` mirror [Groq built-in docs](https://console.groq.com/docs/tool-use/built-in-tools) for reference only (**not** wired into `call` yet).
- **Native-tool observability** — `GroqLLMResponse.server_tool_calls` is populated from `message.executed_tools` when Groq surfaces hosted/compound tool invocations on the chat completion. The core agent loop then auto-emits `ToolCallRecord(executed_by="provider")` so you can split local vs server cost / latency without provider-specific code. `LLMCallRecord.provider="groq"` is also populated automatically.
- **Status & gates** — promoted from **Beta (`0.1.0b1`) → Stable (`0.1.0`)**; classifier `Development Status :: 5 - Production/Stable`; floor `nucleusiq>=0.7.12`. **79 unit tests, coverage 92.51%** (gate ≥ 90%).

**Groq constraints you should respect:** per [Structured outputs](https://console.groq.com/docs/structured-outputs), **streaming** and **tool use** are not currently supported **with** Structured Outputs on the same request — use non-streaming `call` for `response_format`, or skip structured output when streaming / using tools.

**Not in Phase A:** automatic pass-through for **`compound_custom`**, Groq **Responses API**, and **remote MCP** — these target Phase B (`nucleusiq-groq 0.2.x`); the observability surface is already wired so Phase B will not require further agent-loop changes.

**Integration tests (optional):** from `src/providers/inference/groq`, with **`GROQ_API_KEY`** in the environment:

```bash
uv run pytest tests/integration -m integration
```

Default `pytest` / CI uses **`-m "not integration"`** so live calls are optional.

---

## Examples

Runnable agents (real API): [`examples/README.md`](examples/README.md).

```bash
cd src/providers/inference/groq
uv run python examples/agents/01_groq_direct.py
```

---

## Development

From this directory:

```bash
uv sync --group dev
uvx ruff check nucleusiq_groq tests examples
uvx pyrefly check
uv run pytest
```

---

## License

MIT — same as the NucleusIQ monorepo.
