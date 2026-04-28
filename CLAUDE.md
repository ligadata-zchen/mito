# CLAUDE.md

Repo-wide guidance for Claude Code (and other coding agents) working in this monorepo.

For deeper architecture, read [ARCHITECTURE.md](ARCHITECTURE.md). For per-package developer setup, also see:

- [mito-ai/CLAUDE.md](mito-ai/CLAUDE.md) — JupyterLab extension build/test/lint commands.
- [mito-ai-core/README.md](mito-ai-core/README.md) — pure-Python AI layer.

---

## What this repo is

A monorepo for the Mito Jupyter extensions. There are several Python + TypeScript packages; the AI-relevant ones are:

| Package | Purpose | Language |
|---|---|---|
| [`mito-ai-core`](mito-ai-core/) | Provider-agnostic LLM layer (clients, models, prompts, telemetry). No Jupyter / Tornado deps. | Python |
| [`mito-ai`](mito-ai/) | JupyterLab extension. Wraps `mito-ai-core` in WebSocket / REST handlers. Owns DB connectors. | Python + TypeScript |
| [`mito-ai-cli`](mito-ai-cli/) | Standalone CLI on top of `mito-ai-core`. | Python |
| [`mito-ai-mcp`](mito-ai-mcp/) | MCP server exposing Mito tools to other LLM hosts. | Python |
| [`mito-ai-python-tool-executor`](mito-ai-python-tool-executor/) | Tool execution sandbox. | Python |
| [`mitosheet`](mitosheet/) | Spreadsheet UI (separate product, no AI dependency). | Python + TypeScript |

Most AI work lives in **`mito-ai-core`** (logic) and **`mito-ai`** (extension surface).

---

## Quick start: where things live

When the user asks about feature X, look here first:

| Question | Where to look |
|---|---|
| Which models are exposed? How is X routed? | [`mito-ai-core/mito_ai_core/utils/model_utils.py`](mito-ai-core/mito_ai_core/utils/model_utils.py), [`utils/provider_utils.py`](mito-ai-core/mito_ai_core/utils/provider_utils.py) |
| Top-level LLM dispatch | [`mito-ai-core/mito_ai_core/provider_manager.py`](mito-ai-core/mito_ai_core/provider_manager.py) |
| A specific provider's API call | [`mito-ai-core/mito_ai_core/clients/<provider>.py`](mito-ai-core/mito_ai_core/clients/) |
| Env vars / config | [`mito-ai-core/mito_ai_core/constants.py`](mito-ai-core/mito_ai_core/constants.py) |
| Prompt building per message type | [`mito-ai-core/mito_ai_core/completions/prompt_builders/`](mito-ai-core/mito_ai_core/completions/prompt_builders/) |
| Agent loop / tool execution | [`mito-ai-core/mito_ai_core/agent/`](mito-ai-core/mito_ai_core/agent/) |
| Telemetry events (Mixpanel) | [`mito-ai-core/mito_ai_core/utils/telemetry_utils.py`](mito-ai-core/mito_ai_core/utils/telemetry_utils.py) |
| Token usage CSV | [`mito-ai-core/mito_ai_core/utils/token_usage_logger.py`](mito-ai-core/mito_ai_core/utils/token_usage_logger.py) |
| MLflow tracing | [`mito-ai-core/mito_ai_core/utils/mlflow_observability.py`](mito-ai-core/mito_ai_core/utils/mlflow_observability.py) |
| Database drivers and crawlers | [`mito-ai/mito_ai/db/crawlers/`](mito-ai/mito_ai/db/crawlers/) |
| DB connection dispatch | [`mito-ai/mito_ai/db/utils.py`](mito-ai/mito_ai/db/utils.py) (function `crawl_and_store_schema`) |
| Frontend model picker | [`mito-ai/src/components/ModelSelector.tsx`](mito-ai/src/components/ModelSelector.tsx) |
| Frontend DB connection forms | [`mito-ai/src/Extensions/SettingsManager/database/model.ts`](mito-ai/src/Extensions/SettingsManager/database/model.ts) |
| Chat WebSocket handler | [`mito-ai/mito_ai/completions/`](mito-ai/mito_ai/completions/) |

---

## Development setup

### `mito-ai-core` only

```bash
cd mito-ai-core
pip install -e ".[test]"
pytest
```

### Both `mito-ai-core` and `mito-ai` (typical)

```bash
# From repo root. Order matters — mito-ai depends on mito-ai-core.
pip install -e ./mito-ai-core
pip install -e "./mito-ai[test]"

cd mito-ai
touch yarn.lock                                      # required for Yarn 3
jlpm install
jlpm build
jupyter labextension develop . --overwrite
jupyter server extension enable --py mito_ai

# Two terminals:
jlpm watch                                           # rebuilds on save
jupyter lab --autoreload                             # picks up Python changes
```

Full developer recipe is in [`mito-ai/CLAUDE.md`](mito-ai/CLAUDE.md) under "Development Commands".

### Tests

```bash
pytest mito-ai-core/                  # AI provider layer
pytest mito-ai/                       # extension backend
mypy mito_ai/ --ignore-missing-imports
cd mito-ai && jlpm test               # frontend Jest
```

---

## Architectural patterns to know

### 1. Provider routing is prefix-based

`get_model_provider(model)` returns a `model_type` string by inspecting the model id prefix. The routing table in [`provider_utils.py`](mito-ai-core/mito_ai_core/utils/provider_utils.py) is the single source of truth:

```
copilot/...   → "copilot"
abacus/...    → "abacus"
litellm/...   → "litellm"
ollama/...    → "ollama"
claude...     → "claude"
gemini...     → "gemini"
gpt...        → "openai"
```

`ProviderManager.request_completions` and `stream_completions` have parallel `if/elif` chains keyed on `model_type`. **Adding a new provider means adding a branch in both.**

### 2. The OpenAIClient is multi-purpose

Despite the name, [`OpenAIClient`](mito-ai-core/mito_ai_core/clients/openai_client.py) talks to OpenAI, Azure OpenAI, Abacus, **and** Ollama — all of which are OpenAI-compatible. The constructor takes optional `base_url` / `api_key` / `timeout` overrides; when set, they bypass env-var-driven detection. This is how the Ollama router constructs a per-call client without touching the global singleton.

### 3. Mito-server fallback is automatic

Each client checks for an API key; if none is configured, it routes to a Mito-hosted proxy (`MITO_OPENAI_URL`, `MITO_ANTHROPIC_URL`, `MITO_GEMINI_URL`). Don't break this fallback — it's the free-tier path.

### 4. Telemetry is multi-sink, fail-open

Three sinks fire from the same call sites in `provider_manager`:

- **Mixpanel** — analytics events.
- **Local CSV** — `~/.mito/token-usage-log.txt`.
- **MLflow** (opt-in via `MITO_MLFLOW_ENABLED=true`) — span per completion attempt with cost/tokens/duration.

All three swallow their own exceptions; **a telemetry failure must never break a user request**. When adding a fourth sink, follow the same pattern: try/except around the whole emission, debug-level log on failure, no re-raise.

### 5. Database connectors are mostly SQLAlchemy + information_schema

The base crawler [`crawlers/base_crawler.py`](mito-ai/mito_ai/db/crawlers/base_crawler.py) handles any engine that exposes `information_schema.tables` and `information_schema.columns`. Engine-specific quirks (auth modes, connect_args, schema names) are passed in as parameters. **Only write a custom crawler when SQLAlchemy + information_schema can't carry it** — currently Snowflake, BigQuery, and Spark have custom crawlers for documented reasons (see ARCHITECTURE.md §3.2).

### 6. Identifier safety in dynamic SQL

Some engines require dynamic FROM-clause values (BigQuery's `<project>.<dataset>.INFORMATION_SCHEMA`, Spark's `SHOW TABLES IN <db>`). These can't be parameterised, so they're baked into the query string — but only after **rejecting backticks and disallowed characters**. When adding a new engine that needs this, follow the validation pattern in [`crawlers/spark.py`](mito-ai/mito_ai/db/crawlers/spark.py:14) (`_validate_identifier`).

---

## Conventions

### Python

- Python 3.9+. `mypy` configured strictly in `mito-ai`.
- `from __future__ import annotations` is fine but not enforced everywhere; check the file.
- New env vars belong in [`mito-ai-core/mito_ai_core/constants.py`](mito-ai-core/mito_ai_core/constants.py).
- Prefer `Optional[X]` over `X | None` for consistency with existing code (3.9 compat).
- Telemetry helpers must never raise. Wrap their bodies in `try/except` at the call site if they don't already do so.

### TypeScript

- Strict mode. Interfaces start with `I` (e.g. `IConnection`).
- Single quotes, no trailing commas.
- Frontend reads model lists from the backend `available-models` endpoint — don't hardcode in TS unless adding a fallback.
- New form-field types in `database/model.ts` must also be handled in [`ConnectionForm.tsx`](mito-ai/src/Extensions/SettingsManager/database/ConnectionForm.tsx) (`renderField` switch).

### Commits and PRs

- Logical commits, not "WIP" dumps. Each commit should pass tests in isolation.
- Don't commit `.claude/` (local agent config) or `~/.mito/*` artifacts.
- Pre-commit hooks run mypy + eslint; if a hook fails, fix the issue, re-stage, and create a **new** commit (don't `--amend` after hook failure — the original commit didn't land).

### Adding a feature

Read [ARCHITECTURE.md §6 "Extension points"](ARCHITECTURE.md#6-extension-points) for the seams. New providers and new DB engines have established recipes; follow them rather than inventing a new shape.

---

## What's been added in this fork

This fork extends `mito-ds/mito` with:

| Feature | Status | Entry points |
|---|---|---|
| Anthropic Claude Opus 4.6 | merged | `model_utils.py`, `models.ts`, `ModelSelector.tsx` |
| Ollama multi-model router (Qwen / Kimi / DeepSeek / …) | merged | `provider_manager.py`, `openai_client.py`, `open_ai_utils.py`, `constants.py` |
| Hive / Trino / Presto / BigQuery DB engines | merged | `db/crawlers/`, `db/utils.py`, `database/model.ts` |
| Spark SQL Thrift Server + embedded PySpark | merged | `db/crawlers/spark.py` |
| MLflow LLM-call tracing | merged | `utils/mlflow_observability.py` |

See [ARCHITECTURE.md](ARCHITECTURE.md) for design rationale on each.

---

## Common gotchas

- **`gh` is not installed** in the default Windows shell; install via `winget install --id GitHub.cli` (user scope).
- **Yarn 3** in `mito-ai/`: must `touch yarn.lock` before `jlpm install` on first checkout.
- **`information_schema` on Spark is unreliable.** That's why `crawlers/spark.py` uses `SHOW TABLES` + `DESCRIBE`.
- **PySpark install needs Java.** `pip install pyspark` only fetches the Python wrapper; the JVM must be present at runtime.
- **MLflow is optional.** When `MITO_MLFLOW_ENABLED` is unset, the `mlflow` package is never imported. Don't make it a hard dependency.
- **The legacy `OLLAMA_MODEL` (singular) and the new `OLLAMA_MODELS` (plural) coexist.** Singular is single-model + force-override; plural is multi-model router. When both are set, plural wins. See [`openai_client.py`](mito-ai-core/mito_ai_core/clients/openai_client.py) `_adjust_model_for_provider`.
- **DeepSeek R1 emits `<think>` tags** that leak into chat output. Known issue, no filter yet.
- **AGPL-3.0 licensing.** Per-file `Copyright (c) Saga Inc.` headers are mandatory; preserve them when editing.

---

## When in doubt

1. Read [ARCHITECTURE.md](ARCHITECTURE.md) — it covers the why.
2. Grep for the feature near the most-recently-touched file (recent additions are usually the most readable).
3. Run the tests under `mito-ai-core/mito_ai_core/tests/` — they document the expected behavior of the provider routing and model registry.
