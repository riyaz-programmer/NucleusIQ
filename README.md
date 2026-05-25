<p align="center">
  <a href="https://github.com/nucleusbox/NucleusIQ">
    <img src="assets/images/nucleusiq-logo.png" alt="NucleusIQ logo" width="420" />
  </a>
</p>

<h3 align="center">Build AI agents like software systems — maintainable, testable, provider-portable.</h3>

<p align="center">
  <em>An open-source, agent-first Python framework for building AI agents that work in real environments — beyond demos — without creating a one-off system you will regret maintaining.</em>
</p>

<!-- Project status badges -->
<p align="center">
  <a href="https://github.com/nucleusbox/NucleusIQ/actions/workflows/ci.yml"><img src="https://github.com/nucleusbox/NucleusIQ/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/nucleusbox/NucleusIQ/actions/workflows/codeql.yml"><img src="https://github.com/nucleusbox/NucleusIQ/actions/workflows/codeql.yml/badge.svg" alt="CodeQL"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://pypi.org/project/nucleusiq/"><img src="https://img.shields.io/pypi/pyversions/nucleusiq" alt="Python versions"></a>
  <a href="https://nucleusbox.github.io/nucleusiq-docs/"><img src="https://img.shields.io/badge/docs-nucleusbox.github.io-blue" alt="Docs"></a>
  <a href="CONTRIBUTING.md"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs welcome"></a>
</p>

<!-- Per-package PyPI badges (Stable = green, Beta = yellow, Alpha = orange) -->
<p align="center">
  <a href="https://pypi.org/project/nucleusiq/"><img src="https://img.shields.io/pypi/v/nucleusiq?label=nucleusiq&color=brightgreen" alt="nucleusiq"></a>
  <a href="https://pypi.org/project/nucleusiq-openai/"><img src="https://img.shields.io/pypi/v/nucleusiq-openai?label=openai&color=brightgreen" alt="nucleusiq-openai"></a>
  <a href="https://pypi.org/project/nucleusiq-gemini/"><img src="https://img.shields.io/pypi/v/nucleusiq-gemini?label=gemini&color=brightgreen" alt="nucleusiq-gemini"></a>
  <a href="https://pypi.org/project/nucleusiq-anthropic/"><img src="https://img.shields.io/pypi/v/nucleusiq-anthropic?label=anthropic&color=orange" alt="nucleusiq-anthropic"></a>
  <a href="https://pypi.org/project/nucleusiq-groq/"><img src="https://img.shields.io/pypi/v/nucleusiq-groq?label=groq&color=yellow" alt="nucleusiq-groq"></a>
  <a href="https://pypi.org/project/nucleusiq-ollama/"><img src="https://img.shields.io/pypi/v/nucleusiq-ollama?label=ollama&color=orange" alt="nucleusiq-ollama"></a>
  <a href="https://pypi.org/project/nucleusiq-mcp/"><img src="https://img.shields.io/pypi/v/nucleusiq-mcp?label=mcp&color=yellow" alt="nucleusiq-mcp"></a>
</p>

<!-- Community badges -->
<p align="center">
  <a href="https://github.com/nucleusbox/NucleusIQ/stargazers"><img src="https://img.shields.io/github/stars/nucleusbox/NucleusIQ?style=social" alt="GitHub stars"></a>
  <a href="https://github.com/nucleusbox/NucleusIQ/network/members"><img src="https://img.shields.io/github/forks/nucleusbox/NucleusIQ?style=social" alt="GitHub forks"></a>
  <a href="https://github.com/nucleusbox/NucleusIQ/issues"><img src="https://img.shields.io/github/issues/nucleusbox/NucleusIQ" alt="GitHub issues"></a>
  <a href="https://github.com/nucleusbox/NucleusIQ/pulls"><img src="https://img.shields.io/github/issues-pr/nucleusbox/NucleusIQ" alt="GitHub PRs"></a>
</p>

<!-- Section navigation -->
<p align="center">
  <a href="#-quick-start">Quick Start</a> ·
  <a href="#-whats-inside">Features</a> ·
  <a href="#-execution-modes">Execution Modes</a> ·
  <a href="#-packages--ecosystem">Packages</a> ·
  <a href="https://nucleusbox.github.io/nucleusiq-docs/">Docs</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="docs/BACKLOG.md">Roadmap</a>
</p>

---

## ✨ What's New

> **`nucleusiq` 0.7.11 + `nucleusiq-mcp` 0.1.0b1 (Beta)** — May 2026
>
> - 🧩 **MCP Tool Adapter (Beta)** — Plug any [Model Context Protocol](https://modelcontextprotocol.io/) server (Slack, GitHub, Postgres, Stripe, …) into a NucleusIQ Agent in one line. Supports **stdio + Streamable HTTP + SSE**, **OAuth 2.1 / Bearer / Env** auth, graceful degradation, health checks, and full source-attributed tracing. 98.68% coverage, 235 unit + 13 live integration tests.
> - 🪝 **Core `ExpandableTool` protocol** — Any tool factory (like `MCPTool`) can expand into many `BaseTool` instances during `Agent.initialize()` — without the core knowing what MCP is.
> - 🔭 **`ToolCallRecord.source`** — Telemetry now records the origin of every tool call (e.g. `mcp://server=github (path=A)`).
> - 🛡️ **Parallel-safe initialization** — `Agent.initialize()` cleans up all expandable tools even when peers fail or the process is cancelled.
>
> See [CHANGELOG.md](CHANGELOG.md) for the full release notes.

---

## What Is NucleusIQ?

NucleusIQ is an **open-source, agent-first Python framework** for building AI agents that work in real environments — beyond demos — without creating a one-off system you will regret maintaining.

**In one line:**

> NucleusIQ helps developers build AI agents like software systems: maintainable, testable, provider-portable, and ready for real-world integration.

NucleusIQ is built on a simple belief:

> An agent is not a single model call. An agent is a managed runtime with memory, tools, policy, streaming, structure, and responsibilities.

### NucleusIQ Philosophy

A shared doctrine for what NucleusIQ stands for, why it exists, and how it should evolve over time.

See **[NucleusIQ_Philosphy.md](NucleusIQ_Philosphy.md)**.

---

## 🚀 Quick Start

### Install

```bash
# Core + OpenAI (most common)
pip install nucleusiq nucleusiq-openai

# Or with Google Gemini
pip install nucleusiq nucleusiq-gemini

# Or with Anthropic Claude (alpha)
pip install nucleusiq nucleusiq-anthropic

# Or with Groq inference (beta)
pip install nucleusiq nucleusiq-groq

# Or with Ollama for local models (alpha; requires nucleusiq >= 0.7.10 for structured output)
pip install "nucleusiq>=0.7.10" nucleusiq-ollama

# Or with the MCP tool adapter — plug any MCP server in as a tool (beta)
pip install nucleusiq[mcp] nucleusiq-anthropic   # or any provider

# uv works too
uv pip install nucleusiq nucleusiq-openai
```

### Hello agent

```python
import asyncio
from nucleusiq.agents import Agent
from nucleusiq.agents.config import AgentConfig, ExecutionMode
from nucleusiq_openai import BaseOpenAI

agent = Agent(
    name="analyst",
    llm=BaseOpenAI(model="gpt-4o-mini"),
    config=AgentConfig(execution_mode=ExecutionMode.STANDARD),
)

result = asyncio.run(agent.execute("What is the capital of France?"))
print(result.output)
```

### Hello agent + MCP tools

```python
import asyncio
from nucleusiq.agents import Agent
from nucleusiq.agents.config import AgentConfig, ExecutionMode
from nucleusiq_anthropic import BaseAnthropic
from nucleusiq_mcp import MCPTool

agent = Agent(
    name="researcher",
    llm=BaseAnthropic(model="claude-haiku-4-5"),
    tools=[
        # Transport is auto-detected from URL / command; auth is auto-wired
        MCPTool("npx -y @modelcontextprotocol/server-github"),
        MCPTool("https://mcp.slack.com/api", auth="xoxb-..."),
    ],
    config=AgentConfig(execution_mode=ExecutionMode.STANDARD, enable_tracing=True),
)

await agent.initialize()       # connects to MCP servers, discovers tools
result = await agent.execute("Summarise the last 5 issues in nucleusbox/NucleusIQ.")
print(result.output)
```

See [INSTALLATION.md](INSTALLATION.md) for full setup instructions (pip, uv, development mode).

---

## 🧩 What's Inside

| Component | What it does |
|-----------|-------------|
| **3 Execution Modes** | `DIRECT` (single call), `STANDARD` (tool loop), `AUTONOMOUS` (orchestration + validation + retry) |
| **Streaming** | `execute_stream()` — real-time token-by-token output with tool call visibility across all modes |
| **7 Prompt Techniques** | ZeroShot, FewShot, ChainOfThought, AutoCoT, RAG, PromptComposer, MetaPrompt |
| **Multimodal Attachments** | 7 attachment types (text, PDF, images, files) with provider-native optimisation |
| **Built-in File Tools** | `FileReadTool`, `FileSearchTool`, `DirectoryListTool`, `FileExtractTool` — sandboxed to workspace |
| **Tool System** | `BaseTool` interface + `@tool` decorator + provider native tools (OpenAI: code_interpreter, file_search, web_search; Gemini: Google Search, Code Execution, URL Context, Maps; Anthropic: tools + extended thinking) |
| **MCP Tool Adapter** | Connect any **Model Context Protocol** server (Slack, GitHub, Postgres, Stripe, …) as native tools — stdio + Streamable HTTP + SSE; OAuth/Bearer/Env auth |
| **Memory** | 5 strategies (full history, sliding window, summary, summary+window, token budget) with file-aware metadata |
| **Plugins** | 10 built-in: call limits, retry, fallback, PII guard, human approval, tool guard, attachment guard, context window, result validator |
| **Usage Tracking** | Token usage per call with purpose tagging (main, planning, tool loop, critic, refiner) and cost estimation |
| **Structured Output** | Schema-based output parsing with Pydantic, dataclass, TypedDict support |
| **Observability** | `ExecutionTracer` records every model call + tool call with `source` attribution (e.g. `mcp://server=github`) |
| **Provider Portability** | Swap providers (OpenAI, Gemini, Anthropic, Groq, Ollama, …) with one line — same agent code, same tools, same plugins |

---

## ⚙️ Execution Modes

NucleusIQ agents use the **Gearbox Strategy** — three execution modes that scale from simple chat to autonomous reasoning:

| Capability | Direct | Standard | Autonomous |
|---|---|---|---|
| Memory | Yes | Yes | Yes |
| Plugins | Yes | Yes | Yes |
| Tools | Yes (max 25) | Yes (max 80) | Yes (max 300) |
| Tool loop | Yes | Yes | Yes |
| Task decomposition | No | No | Yes |
| Independent verification (Critic) | No | No | Yes |
| Targeted correction (Refiner) | No | No | Yes |
| Validation pipeline | No | No | Yes |

Tool limits are configurable via `AgentConfig(max_tool_calls=N)`. The framework validates tool count at agent creation and raises a clear error if the limit is exceeded.

```python
# Direct: fast Q&A, simple lookups (max 25 tool calls)
AgentConfig(execution_mode=ExecutionMode.DIRECT)

# Standard: multi-step tool workflows (max 80 tool calls) — default
AgentConfig(execution_mode=ExecutionMode.STANDARD)

# Autonomous: orchestration + Critic/Refiner verification (max 300 tool calls)
AgentConfig(execution_mode=ExecutionMode.AUTONOMOUS)
```

See the [PE Due Diligence notebook](notebooks/agents/pe_due_diligence.ipynb) for a real-world demo of Autonomous mode achieving **100% accuracy** on 8 complex financial analyses with external validation.

---

## 📦 Packages & Ecosystem

NucleusIQ ships as a **core framework + thin provider/tool packages**. Install only what you need — every package can be added or removed independently.

### Core

| Package | Status | Version | Description |
|---|---|---|---|
| [`nucleusiq`](https://pypi.org/project/nucleusiq/) | 🟢 Stable | `0.7.11` | Core framework: agents, prompts, tools, memory, plugins, modes, tracing |

### LLM Providers

| Package | Status | Version | Description |
|---|---|---|---|
| [`nucleusiq-openai`](https://pypi.org/project/nucleusiq-openai/) | 🟢 Stable | `0.6.4` | OpenAI (gpt-4o, o-series); Responses API + Chat Completions; native `code_interpreter`, `file_search`, `web_search` |
| [`nucleusiq-gemini`](https://pypi.org/project/nucleusiq-gemini/) | 🟢 Stable | `0.2.6` | Google Gemini; native Google Search, Code Execution, URL Context, Maps grounding |
| [`nucleusiq-anthropic`](https://pypi.org/project/nucleusiq-anthropic/) | 🟠 Alpha | `0.1.0a1` | Anthropic Claude (Messages API); tools, streaming, prompt caching, extended thinking · [README](src/providers/llms/anthropic/README.md) |

### Inference Backends

| Package | Status | Version | Description |
|---|---|---|---|
| [`nucleusiq-groq`](https://pypi.org/project/nucleusiq-groq/) | 🟡 Beta | `0.1.0b1` | Groq inference (Chat Completions) via official `groq` SDK · [README](src/providers/inference/groq/README.md) · [Design](docs/design/GROQ_PROVIDER.md) |
| [`nucleusiq-ollama`](https://pypi.org/project/nucleusiq-ollama/) | 🟠 Alpha | `0.1.0a1` | Local/remote Ollama via official `ollama` SDK; structured output requires `nucleusiq>=0.7.10` · [README](src/providers/inference/ollama/README.md) · [Design](docs/design/OLLAMA_PROVIDER.md) |

### Tool Adapters

| Package | Status | Version | Description |
|---|---|---|---|
| [`nucleusiq-mcp`](https://pypi.org/project/nucleusiq-mcp/) | 🟡 Beta | `0.1.0b1` | **Model Context Protocol** adapter — turn any MCP server (Slack, GitHub, Postgres, Stripe, …) into NucleusIQ tools; stdio + Streamable HTTP + SSE; OAuth 2.1 / Bearer / Env auth · [README](src/providers/tools/mcp/README.md) · [Design](docs/design/MCP_INTEGRATION_DESIGN.md) |

**Maturity legend:** 🟢 Stable (production-ready, SemVer guarantees) · 🟡 Beta (API stable, watching for adoption feedback) · 🟠 Alpha (functional, API may evolve)

---

## 🗂️ Project Structure

```
src/
  nucleusiq/core/                # Core framework (agents, prompts, tools, memory, plugins, modes, tracing)
  providers/
    llms/
      openai/                    # nucleusiq-openai
      gemini/                    # nucleusiq-gemini
      anthropic/                 # nucleusiq-anthropic
    inference/
      groq/                      # nucleusiq-groq
      ollama/                    # nucleusiq-ollama
    tools/
      mcp/                       # nucleusiq-mcp (Model Context Protocol adapter)
notebooks/agents/                # Example notebooks (PE due diligence, MCP showcase, …)
docs/                            # Design docs, backlog, implementation tracker
scripts/                         # Repo-wide tooling (e.g. verify_core_package_layout.py)
```

---

## 🧪 Testing

```bash
# Monorepo: verify core setuptools packages + all Hatch provider/tool wheel roots
python scripts/verify_core_package_layout.py

# Core tests (1,795+ passing)
cd src/nucleusiq && python -m pytest tests/ -q

# OpenAI provider tests (224 passing)
cd src/providers/llms/openai && python -m pytest tests/ -q

# Gemini provider unit tests (221 passing)
cd src/providers/llms/gemini && python -m pytest tests/unit/ -q

# Anthropic provider tests (>=95% coverage gate)
cd src/providers/llms/anthropic && python -m pytest tests/ -q

# Groq provider tests (requires dev group / uv; >=90% coverage gate)
cd src/providers/inference/groq && uv run pytest -q

# Ollama provider tests (>=95% coverage gate; 100% line coverage on package)
cd src/providers/inference/ollama && uv run pytest -q

# MCP tool adapter — unit (235 passing; 98.68% coverage; >=90% gate)
cd src/providers/tools/mcp && python -m pytest tests/unit/ -q -m "not integration"

# MCP tool adapter — live integration (requires Node.js + npx)
cd src/providers/tools/mcp && python -m pytest tests/integration/ -m integration -v

# Gemini integration tests (requires GEMINI_API_KEY)
cd src/providers/llms/gemini && python -m pytest tests/integration/ -q
```

---

## 📚 Documentation

- **Published docs** — https://nucleusbox.github.io/nucleusiq-docs/
- **Docs repository** — https://github.com/nucleusbox/nucleusiq-docs
- [INSTALLATION.md](INSTALLATION.md) — Setup instructions (pip, uv, development)
- [CHANGELOG.md](CHANGELOG.md) — Release notes
- [RELEASE.md](RELEASE.md) — Release process and branching strategy
- [docs/BACKLOG.md](docs/BACKLOG.md) — Public roadmap
- [docs/IMPLEMENTATION_TRACKER.md](docs/IMPLEMENTATION_TRACKER.md) — What's shipped, what's next, per release
- [docs/design/MCP_INTEGRATION_DESIGN.md](docs/design/MCP_INTEGRATION_DESIGN.md) — MCP adapter design (full)
- [File handling guide](https://nucleusbox.github.io/nucleusiq-docs/python/nucleusiq/guides/file-handling/) — Attachment vs Tool vs Both decision guide

---

## 🤝 Contributing

1. Fork the repository
2. Create a branch: `git checkout -b yourname/my-feature main`
3. Make your changes and add tests
4. Submit a pull request to `main`

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details, coding standards, and the dev-setup walkthrough.

### Get in touch

- 🐛 Bugs & feature requests — [GitHub Issues](https://github.com/nucleusbox/NucleusIQ/issues)
- 💬 Questions & ideas — [GitHub Discussions](https://github.com/nucleusbox/NucleusIQ/discussions)
- ⭐ If NucleusIQ is useful to you, please consider starring the repo — it helps a lot.

---

## 📄 License

[MIT](LICENSE) © Nucleusbox
