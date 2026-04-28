# Mito AI — Architecture & Design

This document describes the architecture of the two packages that make up the Mito AI stack:

- [`mito-ai-core`](mito-ai-core/) — pure-Python LLM provider layer (no Jupyter / Tornado dependency).
- [`mito-ai`](mito-ai/) — JupyterLab extension that exposes the AI layer over WebSocket / REST handlers, plus database connection management and Streamlit conversion.

It also documents the extensions added in this fork:

| Area | Addition | Files |
|---|---|---|
| Anthropic | Claude Opus 4.6 model | [`mito-ai-core/mito_ai_core/utils/model_utils.py`](mito-ai-core/mito_ai_core/utils/model_utils.py), [`mito-ai/src/utils/models.ts`](mito-ai/src/utils/models.ts), [`mito-ai/src/components/ModelSelector.tsx`](mito-ai/src/components/ModelSelector.tsx) |
| Open-source LLMs | Ollama multi-model router (Qwen, DeepSeek, Kimi, …) | [`provider_manager.py`](mito-ai-core/mito_ai_core/provider_manager.py), [`openai_client.py`](mito-ai-core/mito_ai_core/clients/openai_client.py), [`open_ai_utils.py`](mito-ai-core/mito_ai_core/clients/open_ai_utils.py), [`constants.py`](mito-ai-core/mito_ai_core/constants.py) |
| OLAP databases | Hive, Trino, Presto, BigQuery | [`mito-ai/mito_ai/db/crawlers/`](mito-ai/mito_ai/db/crawlers/), [`db/utils.py`](mito-ai/mito_ai/db/utils.py), [`database/model.ts`](mito-ai/src/Extensions/SettingsManager/database/model.ts) |
| Big data | Spark SQL Thrift Server + embedded PySpark | [`crawlers/spark.py`](mito-ai/mito_ai/db/crawlers/spark.py) |
| Observability | MLflow tracing of LLM completions (cost, tokens, latency) | [`utils/mlflow_observability.py`](mito-ai-core/mito_ai_core/utils/mlflow_observability.py) |

---

## 1. Repository layout

```
mito/
├── mito-ai-core/         # Pure-Python AI provider layer
│   └── mito_ai_core/
│       ├── agent/                  # Agent runner + tool executor
│       ├── clients/                # One client per provider (OpenAI, Anthropic, Gemini, Copilot)
│       ├── completions/            # Message history, prompt builders, models
│       ├── copilot/                # GitHub Copilot model id catalog
│       ├── enterprise/             # LiteLLM + Abacus enterprise routers
│       ├── utils/                  # Telemetry, tokens, model registry, MLflow
│       ├── constants.py            # Env-driven provider config
│       └── provider_manager.py     # Top-level dispatch
├── mito-ai/              # JupyterLab extension
│   └── mito_ai/
│       ├── completions/            # WebSocket handler for AI chat
│       ├── db/                     # Database connection + schema crawlers
│       ├── chat_history/           # Persisted thread storage
│       ├── settings/               # Settings UI backend
│       ├── streamlit_conversion/   # Notebook → Streamlit app
│       └── ...
├── mito-ai-cli/          # Standalone CLI wrapping mito-ai-core
├── mito-ai-mcp/          # MCP server exposing Mito tools
├── mito-ai-python-tool-executor/  # Tool execution sandbox
├── mitosheet/            # Spreadsheet UI / pandas codegen (separate product line)
└── ...
```

This document focuses on `mito-ai-core` and `mito-ai`. For the spreadsheet (`mitosheet`), see [`mitosheet/README.md`](mitosheet/README.md).

---

## 2. `mito-ai-core` — provider layer

### 2.1 Top-level dispatch

[`ProviderManager`](mito-ai-core/mito_ai_core/provider_manager.py) is the single entry point for all LLM calls. Two methods:

- `request_completions(...)` — non-streaming, with retry loop.
- `stream_completions(...)` — streaming via a `reply_fn` callback.

Both perform the same routing:

```
selected_model
   │
   ▼ get_fast_model_for_selected_model / get_smartest_model_for_selected_model
resolved_model
   │
   ▼ get_model_provider(resolved_model)   # "openai" | "claude" | "gemini" | "ollama" |
   │                                        "copilot" | "abacus" | "litellm"
model_type
   │
   ▼ dispatch on model_type
provider_client.request_completions(...)
```

The dispatch table lives inside `ProviderManager.request_completions` and `stream_completions`. Each branch instantiates the provider client and forwards the call.

### 2.2 Model registry

[`utils/model_utils.py`](mito-ai-core/mito_ai_core/utils/model_utils.py) is the single source of truth for which models are exposed:

```python
ANTHROPIC_MODEL_ORDER = [
    "claude-haiku-4-5-20251001",  # Fastest
    "claude-opus-4-6",            # Smartest  (added)
]

STANDARD_MODELS = [
    "gpt-4.1", "gpt-5.2",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-6",            # added
    "gemini-3-flash-preview", "gemini-3.1-pro-preview",
]
```

`get_available_models()` returns the model list shown in the picker. Priority order:

1. **GitHub Copilot** — if the helper plugin is installed, use Copilot's API model list.
2. **Abacus** — enterprise router (highest enterprise priority).
3. **LiteLLM** — alternate enterprise router.
4. **Standard** — built-in OpenAI / Anthropic / Gemini models.
5. **+ Ollama** — when `OLLAMA_MODELS` is set, `ollama/<name>` entries are appended to (4).

`get_fast_model_for_selected_model` / `get_smartest_model_for_selected_model` find sibling models inside the same provider's order list, used by message-type optimization (e.g. inline completion always uses the fastest).

### 2.3 Provider routing — recognised model name prefixes

[`utils/provider_utils.py`](mito-ai-core/mito_ai_core/utils/provider_utils.py):

| Prefix | `model_type` | Client |
|---|---|---|
| `copilot/` | `copilot` | `CopilotClient` |
| `abacus/` | `abacus` | `OpenAIClient` (via Abacus base URL) |
| `litellm/` | `litellm` | `LiteLLMClient` |
| `claude` | `claude` | `AnthropicClient` |
| `gemini` | `gemini` | `GeminiClient` |
| `ollama/` | `ollama` | `OpenAIClient` (via Ollama base URL — added) |
| `gpt` | `openai` | `OpenAIClient` |

### 2.4 Client implementations

Each client encapsulates a single provider's API and falls back to the Mito-hosted server when no API key is configured:

- **[`OpenAIClient`](mito-ai-core/mito_ai_core/clients/openai_client.py)** — GPT, Azure, Abacus, **Ollama**. Constructor accepts `base_url` / `api_key` / `timeout` overrides so the same class powers multiple OpenAI-compatible endpoints.
- **[`AnthropicClient`](mito-ai-core/mito_ai_core/clients/anthropic_client.py)** — Claude with prompt caching (system + stable history), 1M extended context beta for Sonnet 4.5, and tool-use structured output.
- **[`GeminiClient`](mito-ai-core/mito_ai_core/clients/gemini_client.py)** — Google Gemini.
- **[`CopilotClient`](mito-ai-core/mito_ai_core/clients/copilot_client.py)** — GitHub Copilot (account-bound model list).
- **[`LiteLLMClient`](mito-ai-core/mito_ai_core/enterprise/litellm_client.py)** — provider-agnostic enterprise router.

#### Ollama router — design notes

Ollama's `/v1` endpoint is OpenAI-compatible, so we reuse `OpenAIClient` rather than write a new client:

- `OLLAMA_MODELS` (comma-separated env var) lists the models the user has pulled locally; each becomes `ollama/<name>` in `STANDARD_MODELS`.
- `provider_manager` constructs a per-call `OpenAIClient(base_url=OLLAMA_BASE_URL, api_key="ollama", timeout=300)`.
- Inside `OpenAIClient._adjust_model_for_provider`, `ollama/<name>` is stripped to `<name>` only when the override is set, so the legacy single-model `OLLAMA_MODEL` env var still works for existing installs.
- `get_open_ai_completion_function_params` switches to lenient `{"type": "json_object"}` for `ollama/` models because strict JSON schema support varies across open-source models.

Known gap: DeepSeek R1 emits `<think>…</think>` reasoning that leaks into chat output. A streaming filter for `ollama/deepseek-r1*` is a follow-up.

### 2.5 Retry, errors, and the Mito server fallback

`ProviderManager.request_completions` runs an exponential-backoff retry loop (default 3 retries). `PermissionError` for the Mito free-tier limit short-circuits the loop. All errors land in `self.last_error` and trigger a `traitlets`-style observer notification, which the WebSocket handler in `mito-ai` forwards to the client.

If no API key is configured for the chosen provider, the client transparently routes to the Mito-hosted completion server (`MITO_ANTHROPIC_URL`, `MITO_OPENAI_URL`, `MITO_GEMINI_URL` in [`constants.py`](mito-ai-core/mito_ai_core/constants.py)), preserving the same input/output contract.

### 2.6 Observability

Three independent layers, all called from the same telemetry sites in `provider_manager`:

1. **Mixpanel events** via [`utils/telemetry_utils.py`](mito-ai-core/mito_ai_core/utils/telemetry_utils.py) — `log_ai_completion_success/error/retry`.
2. **Local CSV** via [`utils/token_usage_logger.py`](mito-ai-core/mito_ai_core/utils/token_usage_logger.py) — appends to `~/.mito/token-usage-log.txt`.
3. **MLflow tracing** via [`utils/mlflow_observability.py`](mito-ai-core/mito_ai_core/utils/mlflow_observability.py) (added) — opt-in, fail-open.

#### MLflow integration

Patterned after [alphaiterations/agentic-ai-usecases — genai-observability](https://github.com/alphaiterations/agentic-ai-usecases/tree/main/advanced/genai-observability). Activated by `MITO_MLFLOW_ENABLED=true`. Reads `MLFLOW_TRACKING_URI` and `MLFLOW_EXPERIMENT` and emits one span per completion attempt with attributes:

```
model              claude-opus-4-6
message_type       chat | smartDebug | agent:execution | inline_completion | ...
status             ok | error
streaming          true | false
attempt            0..max_retries
duration_ms        wall-clock
ttft_ms            streaming-only: time to first token
tokens.input       rough estimate (chars/4)
tokens.output      rough estimate (chars/4)
bytes.output       len(completion)
cost.usd           input_tokens/1M * input_price + output_tokens/1M * output_price
error.type         on failure
error.message      on failure (truncated to 1000 chars)
```

Pricing table covers built-in model ids; unknown models (Ollama, LiteLLM-routed, Abacus-prefixed) fall back to a generic `$0.15/$1M input, $0.60/$1M output` so dashboards aren't broken by NULL `cost.usd`.

`record_completion(...)` is a fail-open post-hoc emitter that runs after the existing telemetry calls. `llm_span(...)` is also exposed for future agent-tool-level tracing.

### 2.7 Agent loop

[`agent/agent_runner.py`](mito-ai-core/mito_ai_core/agent/agent_runner.py) implements the agent's run-tool-loop. At each step the LLM returns an [`AgentResponse`](mito-ai-core/mito_ai_core/completions/models.py) (a discriminated union of `cell_update`, `get_cell_output`, `run_all_cells`, `finished_task`, …), the runner forwards the side-effect to the frontend, waits for confirmation/result, and feeds the outcome back into the next turn.

Structured output is enforced via:

- **Anthropic**: `tool_choice` forcing the model to call an `agent_response` tool whose schema is the Pydantic JSON schema.
- **OpenAI / Abacus / Ollama**: `response_format={"type": "json_schema", "strict": true, ...}`. Abacus and Ollama fall back to `{"type": "json_object"}` because of inconsistent strict-schema support.
- **Gemini**: native structured output schema.

---

## 3. `mito-ai` — JupyterLab extension

### 3.1 Backend: handlers, db, settings

The Python extension under [`mito-ai/mito_ai/`](mito-ai/mito_ai/) registers Tornado handlers under `/mito-ai/*`:

- [`completions/`](mito-ai/mito_ai/completions/) — WebSocket handler that bridges client messages to `ProviderManager.stream_completions`.
- [`db/`](mito-ai/mito_ai/db/) — REST handlers for database connections and schema crawls.
- [`settings/`](mito-ai/mito_ai/settings/) — settings.json read/write.
- [`chat_history/`](mito-ai/mito_ai/chat_history/) — persisted threads.
- [`streamlit_conversion/`](mito-ai/mito_ai/streamlit_conversion/), [`streamlit_preview/`](mito-ai/mito_ai/streamlit_preview/) — notebook-to-app conversion.

### 3.2 Database connector subsystem

The DB layer powers (a) the Mito spreadsheet's "Import from database" wizard and (b) the AI chat's schema-aware context (so the model knows your tables and columns).

```
POST /mito-ai/db/connections          { type: "...", ...fields }
       │
       ▼
ConnectionsHandler.post                ── handlers.py
       │
       ▼
install_db_drivers(db_type)            ── pip-installs SUPPORTED_DATABASES[type]["drivers"]
       │
       ▼
crawl_and_store_schema(...)            ── utils.py: dispatch on connection_details["type"]
       │
       ▼
crawler module                          ── crawlers/{base_crawler,snowflake,bigquery,spark}.py
       │
       ▼
~/.mito/db/schemas.json                 ── consumed by AI chat for table/column context
~/.mito/db/connections.json             ── connection metadata (passwords stored plaintext today)
```

#### Engine catalog

| Engine | Driver | Auth | Crawler | Status |
|---|---|---|---|---|
| PostgreSQL | `psycopg2-binary` | user/pass | `base_crawler` (information_schema) | original |
| MySQL | `PyMySQL` | user/pass | `base_crawler` (SHOW TABLES) | original |
| Microsoft SQL Server | `pyodbc` | user/pass | `base_crawler` (information_schema) | original |
| Oracle | `oracledb` | user/pass | `base_crawler` (user_tables) | original |
| SQLite | _stdlib_ | path | `base_crawler` (sqlite_master) | original |
| Snowflake | `snowflake-sqlalchemy` | user/pass | `crawlers/snowflake.py` (account_usage) | original |
| **Apache Hive** | `pyhive[hive]`, `thrift`, `thrift-sasl` | NONE / LDAP / Kerberos | `base_crawler` (information_schema) | **added** |
| **Trino** | `trino[sqlalchemy]` | basic, http/https | `base_crawler` (information_schema) | **added** |
| **Presto** | `pyhive[presto]` | basic | `base_crawler` (information_schema) | **added** |
| **Google BigQuery** | `sqlalchemy-bigquery`, `google-cloud-bigquery` | service-account JSON or ADC | `crawlers/bigquery.py` (per-dataset INFORMATION_SCHEMA) | **added** |
| **Spark SQL (Thrift Server)** | `pyhive[hive]`, `thrift`, `thrift-sasl` | NONE / LDAP / Kerberos | `crawlers/spark.py:crawl_spark_sql` (`SHOW TABLES IN`, `DESCRIBE`) | **added** |
| **Embedded PySpark** | `pyspark` | local SparkSession + optional Hive metastore | `crawlers/spark.py:crawl_pyspark` (`spark.catalog.*`) | **added** |

#### Design choices for the new engines

- **Reuse SQLAlchemy where possible.** Hive / Trino / Presto / BigQuery all flow through `base_crawler.crawl_db()` with `information_schema` queries. The base crawler grew an optional `connect_args` parameter and a parameterised `schema_name` to support per-engine quirks (Hive's `auth=LDAP`, Trino's `http_scheme`).
- **Custom crawlers only when SQLAlchemy can't carry it.** BigQuery's `INFORMATION_SCHEMA` lives under `<project>.<dataset>` and can't be parameterised in a `FROM` clause, so [`bigquery.py`](mito-ai/mito_ai/db/crawlers/bigquery.py) builds the query with backtick-quoted identifiers (validated for backtick-injection). Spark's `information_schema` is unreliable across versions, so [`spark.py`](mito-ai/mito_ai/db/crawlers/spark.py) uses native `SHOW TABLES IN` + `DESCRIBE` + a `#`-prefix sentinel to skip Spark's partition-info section.
- **Embedded PySpark is a separate engine.** It doesn't go through SQLAlchemy at all — the crawler builds a `SparkSession` and walks `spark.catalog`. Importantly, it does **not** call `spark.stop()`: SparkSession is a JVM-level singleton and stopping it here would tear down a notebook kernel that happens to share the JVM.
- **Identifier safety.** All dynamic FROM-clause identifiers (BigQuery project/dataset, Spark database/table) are validated against a conservative regex and rejected if they contain backticks, before being baked into queries.

#### Frontend: connection forms

[`mito-ai/src/Extensions/SettingsManager/database/model.ts`](mito-ai/src/Extensions/SettingsManager/database/model.ts) declaratively describes each engine's UI fields. The shared [`ConnectionForm.tsx`](mito-ai/src/Extensions/SettingsManager/database/ConnectionForm.tsx) renders the form from this descriptor, with a `'textarea'` field type added for BigQuery's service-account JSON.

### 3.3 Chat plumbing — front to back

```
Frontend (React)                                Backend (Tornado)               Provider
──────────────────────────                       ───────────────────────         ────────
ChatTaskpane                                                                   
   │ user types prompt                                                         
   ▼                                                                           
WebSocket "completion_request"  ──────────►  CompletionWebSocketHandler        
                                                  │                           
                                                  │ build CompletionRequest    
                                                  ▼                           
                                              ProviderManager.stream_completions
                                                  │                           
                                                  ▼                           
                                              <provider client>  ────────────► Anthropic / OpenAI / …
                                                  │                           
                                              ◄───┘ chunks via reply_fn       
   ◄──── CompletionStreamChunk ──────────────────┘                           
ChatMessage renders incremental tokens                                         
```

The same handler also services `agent:execution`, `smartDebug`, `inline_completion`, etc. — they're discriminated by `MessageType` on the incoming request.

### 3.4 Notebook context + AI rules

- [`Extensions/ContextManager/`](mito-ai/src/Extensions/ContextManager/) — collects the current notebook's variables, imports, files, and active cell so prompts can be context-aware.
- [`mito_ai/rules/`](mito-ai/mito_ai/rules/) — user-defined rules appended to the system prompt.
- [`db/schemas.json`](#32-database-connector-subsystem) — table/column metadata for connected DBs, automatically merged into prompts that mention SQL-style operations.

---

## 4. Cross-cutting flows

### 4.1 First-run → first prompt

```
1. pip install mito-ai mitosheet
2. jupyter lab
3. JupyterLab loads mito-ai server extension          → registers handlers
4. JupyterLab loads mito-ai frontend extension        → renders chat panel
5. User types prompt
6. Frontend ChatTaskpane → WebSocket → CompletionWebSocketHandler
7. ProviderManager picks `claude-haiku-4-5-20251001`  (default)
8. AnthropicClient.stream_completions → Anthropic API (or Mito server)
9. Streaming chunks → reply_fn → WebSocket → React state → rendered tokens
10. On completion, telemetry fires (Mixpanel + token CSV + MLflow if enabled)
```

### 4.2 Adding a new database connection

```
1. User opens Settings → Databases → Add Connection
2. Frontend reads databaseConfigs[selectedType] → renders fields
3. User submits   POST /mito-ai/db/connections   { type, ...fields }
4. ConnectionsHandler.post:
     install_db_drivers(type)                  via pip
     crawl_and_store_schema(connection_id, ...) via crawlers/<engine>
5. On success: schemas.json updated, connection_id returned
6. AI chat now sees the schema in subsequent prompts
```

### 4.3 Picking the smartest model for an agent step

```
selected_model = "claude-haiku-4-5-20251001"   (user's pick)
use_smartest_model = True                      (agent step requested it)
   │
   ▼ get_smartest_model_for_selected_model
ANTHROPIC_MODEL_ORDER[-1] = "claude-opus-4-6"
   │
   ▼ ProviderManager.request_completions(model=claude-opus-4-6, ...)
   ▼ get_model_provider("claude-opus-4-6") → "claude"
AnthropicClient.request_completions
```

The fast/smart helpers also exist for OpenAI and Gemini but **not** for Ollama (open-source models are user-supplied with no canonical fast/smart ordering — the helpers return the input unchanged for `ollama/` prefixes).

---

## 5. Configuration reference

| Env var | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI direct | unset → Mito server fallback |
| `ANTHROPIC_API_KEY` | Anthropic direct | unset → Mito server fallback |
| `GEMINI_API_KEY` | Google direct | unset → Mito server fallback |
| `AZURE_OPENAI_API_KEY` etc. | Azure OpenAI | unset |
| `OLLAMA_MODEL` | **legacy** single-model Ollama | unset |
| `OLLAMA_MODELS` | comma-separated multi-model Ollama (added) | unset |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434/v1` |
| `LITELLM_BASE_URL` / `LITELLM_API_KEY` / `LITELLM_MODELS` | LiteLLM router (enterprise) | unset |
| `ABACUS_BASE_URL` / `ABACUS_API_KEY` / `ABACUS_MODELS` | Abacus router (enterprise) | unset |
| `MITO_MLFLOW_ENABLED` | Toggle MLflow tracing (added) | `false` |
| `MLFLOW_TRACKING_URI` | MLflow server URL | unset → mlflow's default |
| `MLFLOW_EXPERIMENT` | MLflow experiment name | `mito-ai` |

When more than one provider is configured, priority is:

```
GitHub Copilot (helper installed)
  > Abacus (enterprise + configured)
  > LiteLLM (enterprise + configured)
  > OpenAI key
  > Anthropic key
  > Gemini key
  > Ollama (multi-model OLLAMA_MODELS or legacy OLLAMA_MODEL)
  > Mito-hosted server (fallback)
```

`ProviderManager.capabilities` reports which one is active.

---

## 6. Extension points

If you're adding to this codebase, here are the natural seams:

### Add a new LLM provider
1. Add a client in [`mito-ai-core/mito_ai_core/clients/<your_provider>.py`](mito-ai-core/mito_ai_core/clients/) implementing `request_completions` and `stream_completions`.
2. Add a prefix branch in [`utils/provider_utils.py`](mito-ai-core/mito_ai_core/utils/provider_utils.py).
3. Register models in [`utils/model_utils.py`](mito-ai-core/mito_ai_core/utils/model_utils.py) (`STANDARD_MODELS`, fast/smart order list).
4. Add a routing arm in `ProviderManager.request_completions` and `stream_completions`.
5. Add UI display name + icon mapping in [`mito-ai/src/components/ModelSelector.tsx`](mito-ai/src/components/ModelSelector.tsx).
6. Add env vars in [`constants.py`](mito-ai-core/mito_ai_core/constants.py).

### Add a new database engine
1. Add a `SUPPORTED_DATABASES[<type>]` entry in [`crawlers/constants.py`](mito-ai/mito_ai/db/crawlers/constants.py) with `drivers` + queries (or leave queries empty if you'll write a custom crawler).
2. If `information_schema` works, no new file needed — just add a branch in [`db/utils.py:crawl_and_store_schema`](mito-ai/mito_ai/db/utils.py) calling `base_crawler.crawl_db(...)`.
3. Otherwise, add `crawlers/<engine>.py` and dispatch to it.
4. Add a `databaseConfigs` entry in [`database/model.ts`](mito-ai/src/Extensions/SettingsManager/database/model.ts) with the form fields.

### Add a new observability backend
- **OpenTelemetry**: set `MLFLOW_TRACING_OTEL_EXPORTER_OTLP_ENDPOINT` alongside `MITO_MLFLOW_ENABLED=true`. MLflow ≥ 2.14 forwards spans natively.
- **Custom backend**: mirror `utils/mlflow_observability.py` — a fail-open `record_completion` hook called from `provider_manager`'s telemetry sites.

### Tweak prompt templates
[`mito-ai-core/mito_ai_core/completions/prompt_builders/`](mito-ai-core/mito_ai_core/completions/prompt_builders/). Each `MessageType` has a builder; the registry in `prompt_section_registry.py` controls which sections are trim-able under context pressure.

---

## 7. Glossary

- **Completion** — a single LLM call. May be streamed or one-shot.
- **Thread** — a persistent chat conversation, identified by `ThreadID`. Stored in `~/.mito/chat-history/`.
- **Agent execution** — multi-step tool-using LLM run. Uses structured output to emit tool calls.
- **Crawler** — code that introspects a database to produce a `TableSchema` or `WarehouseDetails`.
- **Capabilities** — `AICapabilities(provider, configuration)`; reported to the frontend on capability negotiation.
- **Key type** — `USER_KEY` (caller-provided API key) or `MITO_SERVER_KEY` (proxied through Mito's free-tier server).
- **Router prefix** — `abacus/`, `litellm/`, `copilot/`, `ollama/`. Models with these prefixes go through a special routing arm.
- **Span** — an MLflow trace unit. One span per completion attempt.

---

## 8. Known gaps and follow-ups

- **DeepSeek R1 `<think>` tags** leak into chat output via the Ollama path. A streaming filter for `ollama/deepseek-r1*` is the obvious fix.
- **BigQuery** crawls a single dataset per connection. A multi-dataset crawl using the `WarehouseDetails` shape (like Snowflake) is a one-screen change.
- **Trino auth** is basic-only. JWT / Kerberos / OAuth2 need a Trino-specific crawler that builds the auth object before construction (not expressible via JSON connection details alone).
- **PySpark install is heavy** (~300 MB + Java). Documenting a Docker image with Java preinstalled is more reliable than depending on `install_db_drivers` to fetch it.
- **Pricing overrides** for MLflow `cost.usd` are list-price only. A `MITO_MODEL_PRICING_OVERRIDES` JSON env var would let enterprises substitute negotiated rates.
- **Async concurrency for MLflow spans** — MLflow spans are thread-local. Concurrent in-process LLM calls (e.g. via `asyncio.gather`) on the same thread could interleave; explicit `parent_id` linking would solve it.
