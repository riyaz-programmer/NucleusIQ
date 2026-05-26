# nucleusiq-ollama

Alpha provider for running **NucleusIQ** agents against [Ollama](https://docs.ollama.com/) (local or hosted).

## Install

**Alpha** on PyPI (**`0.1.0a1`**). Requires **`nucleusiq>=0.7.10`** (pulled in automatically by `pip`).

```bash
pip install nucleusiq-ollama
```

Requires a running Ollama server unless you point `OLLAMA_HOST` at a remote instance. Optional: `OLLAMA_API_KEY` for authenticated endpoints.

## Usage

```python
from nucleusiq_ollama import BaseOllama, OllamaLLMParams

llm = BaseOllama(model_name="llama3.2", llm_params=OllamaLLMParams(think=True))
```

Runnable scripts (smoke, Agent DIRECT, streaming) live under **`examples/`** — see [`examples/README.md`](examples/README.md).

See [OLLAMA_PROVIDER.md](https://github.com/nucleusbox/NucleusIQ/blob/main/docs/design/OLLAMA_PROVIDER.md) for capability matrix, environment variables, and roadmap.

## Status

**0.2.0** — **Development Status :: 5 - Production/Stable**. First stable line.

- **Chat + streaming + tools + structured outputs** (JSON schema / `format`) + `think` pass-through.
- **Vision (image messages)** in the wire layer — OpenAI-style multimodal content lists with `image_url` parts whose URL is a `data:image/*;base64,...` data URL are converted to Ollama's `message.images` shape; HTTP(S) URLs are skipped with a warning (pre-encode them as data URLs to send images).
- **Observability** — every Ollama LLM call now lands in `AgentResult.llm_calls` with `provider="ollama"` populated automatically by the core agent loop.
- Floor `nucleusiq>=0.7.12`. **98 unit tests, coverage 99.85%** (gate ≥ 95%).
- Embeddings + web search remain planned follow-ups for `0.2.x` / `0.3.x`.
