# Contribution Opportunities

Curated tasks aligned with the NucleusIQ monorepo layout and the public roadmap.

**Agent coverage (shipped vs planned):** [NucleusIQ Agent Coverage on Nucleusbox](https://www.nucleusbox.com/nucleusiq-agent-coverage/) — interactive scorecard for **v0.7.12** today and **v0.8–v0.9** targets (no separate docs path in this repo).

**How to start:** pick one item below → comment on [GitHub Issues](https://github.com/nucleusbox/NucleusIQ/issues) or [Discussion #37](https://github.com/nucleusbox/NucleusIQ/discussions/37) → branch `yourname/short-description` → PR (see [CONTRIBUTING.md](CONTRIBUTING.md)).

**Labels:** `good first issue` · `help wanted` · `documentation` · `challenge`

---

## Monorepo layout

```
src/
  nucleusiq/                          # PyPI: nucleusiq (core)
    core/
      agents/                         # Agent, modes, context, observability, structured output
      prompts/                        # Prompt techniques
      tools/                          # BaseTool, @tool, builtin file tools, ExpandableTool
      memory/                         # Memory strategies
      llms/                           # BaseLLM, retry, errors
      plugins/                        # Plugin system + built-ins
      streaming/                      # Stream events
      utilities/
    tests/
  providers/
    llms/openai/                      # PyPI: nucleusiq-openai
    llms/gemini/                      # PyPI: nucleusiq-gemini
    llms/anthropic/                   # PyPI: nucleusiq-anthropic
    inference/groq/                   # PyPI: nucleusiq-groq
    inference/ollama/                 # PyPI: nucleusiq-ollama
    tools/mcp/                        # PyPI: nucleusiq-mcp
    dbs/pinecone/                     # PyPI stub: nucleusiq-pinecone (early)
    dbs/chroma/                       # PyPI stub: nucleusiq-chroma (early)
notebooks/agents/                     # Example notebooks + Agent Engineering Challenge
scripts/                              # verify_core_package_layout.py, release helpers
```

Published docs live in the separate [nucleusiq-docs](https://nucleusbox.github.io/nucleusiq-docs/) repository.

---

## 1. Core — `src/nucleusiq` (`nucleusiq`)

### 1.1 Agents & execution modes — `core/agents/`, `core/agents/modes/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P0 | **Critic/Refiner native-tool routing audit** — server tool results visible in validation loops | v0.7.13+ | Medium | `modes/autonomous/critic_runner.py`, `refiner_runner.py` |
| P1 | **`agent.execute("plain text")` overload** — sugar over `Task(objective=...)` | v0.8.0 | Small | `agent.py` |
| P1 | **Tool-call dedup cache** (opt-in via `AgentConfig` / `@tool(idempotent=True)`) | v0.7.x | ~1 day | Executor path; tracer `tool_cache_hit` |
| P1 | **Agent Types matrix** — ReAct, CoT, and documented mode combinations | v0.8.0 | Large | `react_agent.py`, mode docs |
| P2 | **Devil's advocate notebook — Anthropic variant** | v0.7.x | Small | `notebooks/agents/investment_board_devils_advocate/` |
| P2 | **Streaming parity** — ensure `execute_stream()` telemetry matches non-stream | v0.7.x | Medium | All three modes |

### 1.2 Context management — `core/agents/context/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P0 | **Context telemetry in challenge scorecard** — surface `cache_read_input_tokens` / `cache_creation_input_tokens` from `LLMCallRecord` | v0.7.13 | Small | Community feedback; fields exist in core |
| P1 | **Context Window Management v2** — remaining design steps | v0.8.0 | Large | `engine.py`, `compactor.py`, `observation_masker.py` |
| P2 | **`DocumentIndexProvider`** — hierarchical document navigator (beyond L5 corpus) | v0.8.0 | Large | `document_search.py`, `document_corpus_tools.py` |
| P2 | **Evidence gate / phase control** hardening + tests | v0.7.x | Medium | `phase_control.py`, `evidence.py` |

### 1.3 Observability — `core/agents/observability/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P1 | **OpenTelemetry exporter** implementing `ExecutionTracerProtocol` | v0.9.0+ | Large | `protocol.py`, `default_tracer.py` |
| P2 | **Optional LangFuse / observability plugin** — export `AgentResult` + traces | v0.9.0+ | Medium | `plugins/` |
| P2 | **Context telemetry pretty-printer** example script | v0.7.x | Small | Educational; no core API change |

### 1.4 Tools — `core/tools/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P1 | **Third-party tool adapter** via `ExpandableTool` protocol | v0.8.0 | Medium | `protocols.py`; pattern same as MCP expand |
| P2 | **Builtin file tools** — more formats / edge-case tests | v0.7.x | Small | `builtin/file_extract.py`, etc. |
| P2 | **`@tool` context_policy** docs + examples | v0.7.x | Small | `decorators.py`, context `policy.py` |

### 1.5 LLM layer — `core/llms/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P1 | **`TurnBoundary` on `ModelRequest`** (`START` / `CONTINUE` / `SCOPED`) | v0.7.13+ | 2–3 days | Stateful providers (OpenAI Responses) |
| P2 | **Shared retry policy** tests for new status codes | v0.7.x | Small | `retry_policy` (used by all providers) |

### 1.6 Memory — `core/memory/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P2 | **Memory strategy examples** — one notebook per strategy | v0.7.x | Small | `factory.py`, strategies |
| P3 | **Cross-session persistence** design spike | v0.9.0+ | Large | Backlog research |

### 1.7 Prompts — `core/prompts/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P2 | **Prompt technique cookbook** — minimal example per technique | v0.7.x | Small | ZeroShot, CoT, RAG, Composer, etc. |
| P3 | **`prompt_technique` on `LLMCallRecord`** — wire from modes | v0.8.0 | Medium | Field stub exists in changelog |

### 1.8 Plugins — `core/plugins/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P2 | **New builtin plugin** — e.g. budget alert on `context_telemetry` | v0.7.x | Medium | `builtin/` |
| P2 | **Plugin authoring guide** in nucleusiq-docs | v0.7.x | Small | Docs repo PR |

### 1.9 Structured output — `core/agents/structured_output/`

| Priority | Feature / task | Target version | Effort | Notes |
|----------|----------------|----------------|--------|-------|
| P2 | **Resolver tests** for new provider aliases | v0.7.x | Small | `resolver.py` |
| P2 | **AUTO vs NATIVE vs JSON** decision tree doc | v0.7.x | Small | Docs repo |

---

## 2. Providers — `src/providers/`

Each provider is an independent package with `pyproject.toml`, `tests/`, and `examples/`. Floor dependency: `nucleusiq>=0.7.12` unless noted.

### 2.1 `nucleusiq-openai` — `src/providers/llms/openai/`

| Priority | Feature / task | Target version | Effort |
|----------|----------------|----------------|--------|
| P0 | **Web Search GA parity** — full wire + example (deferred from v0.7.12) | v0.7.13+ | Medium |
| P1 | **Responses API `TurnBoundary` support** | v0.7.13+ | Medium |
| P1 | **Live integration test** expansion (mirror Anthropic Phase B suite) | v0.7.x | Small |
| P2 | **Example per native tool** — web_search, code_interpreter, file_search | v0.7.x | Small |

### 2.2 `nucleusiq-anthropic` — `src/providers/llms/anthropic/`

| Priority | Feature / task | Target version | Effort |
|----------|----------------|----------------|--------|
| P0 | **Phase C server tools** — Memory, `computer_use`, `bash` (design + spike) | v0.7.13+ | Large |
| P1 | **Additional live integration tests** for edge beta headers | v0.7.x | Small |
| P2 | **Example #13+** — one script per new native tool | v0.7.x | Small |

### 2.3 `nucleusiq-gemini` — `src/providers/llms/gemini/`

| Priority | Feature / task | Target version | Effort |
|----------|----------------|----------------|--------|
| P1 | **Native-tool routing** in Autonomous Critic/Refiner (with core audit) | v0.7.13+ | Medium |
| P1 | **Grounding / URL context** example scripts | v0.7.x | Small |
| P2 | **Live integration test** coverage increase | v0.7.x | Medium |

### 2.4 `nucleusiq-groq` — `src/providers/inference/groq/`

| Priority | Feature / task | Target version | Effort |
|----------|----------------|----------------|--------|
| P1 | **Phase B** — Responses API, hosted tools, remote MCP | v0.2.x | Large |
| P2 | **Integration tests** with `pytest -m integration` + `GROQ_API_KEY` | v0.7.x | Small |
| P2 | **Compound / hosted tool** observability hardening | v0.7.x | Medium |

### 2.5 `nucleusiq-ollama` — `src/providers/inference/ollama/`

| Priority | Feature / task | Target version | Effort |
|----------|----------------|----------------|--------|
| P1 | **Embeddings API** — wire + tests (beyond chat + vision) | v0.7.x | Medium |
| P2 | **Vision example notebook** | v0.7.x | Small |
| P2 | **Structured output** live test on local model | v0.7.x | Small |

### 2.6 `nucleusiq-mcp` — `src/providers/tools/mcp/`

| Priority | Feature / task | Target version | Effort |
|----------|----------------|----------------|--------|
| P1 | **Additional auth mode tests** (OAuth PKCE edge cases) | v0.7.x | Medium |
| P2 | **Example: GitHub + Postgres MCP** in one agent | v0.7.x | Small |
| P2 | **Health check / reconnect** documentation | v0.7.x | Small |

### 2.7 Database providers (stubs) — `src/providers/dbs/`

| Priority | Feature / task | Target version | Effort |
|----------|----------------|----------------|--------|
| P3 | **`nucleusiq-pinecone`** — minimal vector store adapter | v0.9.0+ | Large |
| P3 | **`nucleusiq-chroma`** — minimal vector store adapter | v0.9.0+ | Large |

---

## 3. Notebooks & challenge — `notebooks/agents/`

| Priority | Feature / task | Path | Effort |
|----------|----------------|------|--------|
| P1 | **Challenge scorecard v1.1** — `cache_read_input_tokens`, `cache_creation_input_tokens` in `SCORECARD_SPEC.md` + `_template/run.py` | `agent_engineering_challenge/` | Small |
| P1 | **Reference submission: plain OpenAI SDK** | `submissions/plain_openai/` | Medium |
| P2 | **Reference submission: another stack** (post in Discussion first; PR by invite) | `submissions/<name>/` | Medium |
| P2 | **Unit tests for `_template/run.py` `produce_scorecard()`** | `submissions/_template/` | Small |
| P2 | **Context management showcase** refresh for v0.7.12 telemetry fields | `context_management_*.ipynb` | Medium |

---

## 4. Tooling & CI — `scripts/`, `.github/workflows/`

| Priority | Feature / task | Effort |
|----------|----------------|--------|
| P2 | **Extend `verify_core_package_layout.py`** for new provider packages | Small |
| P2 | **Issue templates** — link to this file from Feature Request template | Small |
| P3 | **Release checklist automation** (optional) | Medium |

---

## 5. Documentation — [nucleusiq-docs](https://nucleusbox.github.io/nucleusiq-docs/) (separate repo)

| Priority | Feature / task | Effort |
|----------|----------------|--------|
| P1 | **Agent Engineering Challenge** guide page (task, data, scorecard, Discussion link) | Small |
| P1 | **Per-provider guides** sync with v0.7.12 stable matrix | Medium |
| P2 | **Context management** — telemetry field glossary | Small |
| P2 | **Contributing** page pointing to `CONTRIBUTION_OPPORTUNITIES.md` | Small |

---

## Good first issues (recommended entry points)

| # | Task | Where |
|---|------|-------|
| 1 | Challenge scorecard cache token fields | `notebooks/agents/agent_engineering_challenge/` |
| 2 | Context telemetry pretty-printer script | `core/agents/observability/` or `examples/` |
| 3 | One new Anthropic/Gemini/OpenAI example script | `src/providers/*/examples/` |
| 4 | `_template/run.py` unit tests | `submissions/_template/` |
| 5 | Provider README typo / install command fixes | `src/providers/*/README.md` |
| 6 | Prompt technique minimal example | `core/prompts/` + notebook |
| 7 | MCP dual-server example | `src/providers/tools/mcp/examples/` |

---

## Roadmap summary

See **[Agent coverage map](https://www.nucleusbox.com/nucleusiq-agent-coverage/)** for per–agent-type scores (research, multi-agent, coding, etc.).

| Version | Focus |
|---------|--------|
| **v0.7.13+** | OpenAI Web Search GA; Critic/Refiner native-tool audit; Anthropic Phase C start; `TurnBoundary` |
| **v0.7.x** | Groq Phase B; Ollama embeddings; tool dedup cache; challenge + examples |
| **v0.8.0** | `execute("prompt")`; Context Mgmt v2; Agent Types matrix; `DocumentIndexProvider`; Agent-as-Tool; structured sub-agent handoff |
| **v0.9.0+** | OpenTelemetry tracer; observability export plugins; Pinecone/Chroma providers; A2A (thin adapter) |

---

## After you pick a task

1. Comment: *“Taking: &lt;task name&gt; in &lt;path&gt;”*.
2. One concern per PR; add tests for core/provider behavior changes.
3. Update `CHANGELOG.md` under `[Unreleased]` for user-facing changes.
4. **Challenge submissions:** default is Discussion [#37](https://github.com/nucleusbox/NucleusIQ/discussions/37); maintainer may invite a PR into `submissions/` after review.
