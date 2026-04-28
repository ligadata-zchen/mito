<h1 align="center">
  <img src="https://www.trymito.io/_next/image?url=%2FMito.svg&w=128&q=75" alt="Mito Logo">
  Mito
</h1>
<p align="center">
  Forked from <a href="https://github.com/mito-ds/mito">mito-ds/mito</a>. This fork extends the AI layer with additional LLM providers, OLAP database connectors, Spark, and MLflow-based observability. For Mito's product documentation see the <a href="https://docs.trymito.io">original docs</a>.
</p>
<p align="center">
  Jupyter extensions that make you work faster.
</p>
<p align="center">
  <a href="https://github.com/mito-ds/monorepo/actions/workflows/deploy-mitosheet-mitoinstaller.yml">
    <img src="https://github.com/mito-ds/monorepo/actions/workflows/deploy-mitosheet-mitoinstaller.yml/badge.svg" alt="Deploy mitosheet and mitoinstaller">
  </a>
  <a href="https://github.com/mito-ds/monorepo/actions/workflows/test-mito-ai.yml">
    <img src="https://github.com/mito-ds/monorepo/actions/workflows/test-mito-ai.yml/badge.svg" alt="Test Mito AI">
  </a>
  <img src="https://img.shields.io/pypi/dm/mitosheet" alt="PyPI - Downloads">
</p>

<h1></h1>


Mito is a set of Jupyter extensions desgined to help you write Python code faster. There are 3 main pieces of Mito.
1. [Mito AI](https://docs.trymito.io/mito-ai/data-copilot): Tools like context-aware AI Chat and error debugging to help you get the most from LLMs. No more copying and pasting between Jupyter and ChatGPT/Claude.
2. [Mito Spreadsheet](https://docs.trymito.io/how-to/importing-data-to-mito/importing-csv-files): Explore your data in an interactive spreadsheet interface. Write spreadsheet formulas like VLOOKUP, apply filters, build pivot tables, and create graphs all in the spreadsheet.  Every edit you make in the Mito spreadsheet is automatically converted to production-ready Python code
3. [Mito for Streamlit and Dash](https://docs.trymito.io/mito-for-streamlit/getting-started-with-mito-for-streamlit): Add a fully-featured spreadsheet to your dashboards in just two lines of code.
Mito is an open source tool (look around...), and will always be built by and for our community. See our [plans page](https://www.trymito.io/plans) for more detail about our features, and consider purchasing Mito Pro to help fund development.

## What's added in this fork

| Area | Addition | Default | Reference |
|---|---|---|---|
| LLM | Claude **Opus 4.6** registered alongside Haiku 4.5 | available in picker | [ARCHITECTURE.md §2.2](ARCHITECTURE.md#22-model-registry) |
| LLM | **Ollama multi-model router** for local open-source models (Qwen, DeepSeek, Kimi, …) | opt-in via `OLLAMA_MODELS` | [ARCHITECTURE.md §2.4](ARCHITECTURE.md#24-client-implementations) |
| Database | **Apache Hive, Trino, Presto, Google BigQuery** connectors | available in Settings → Databases | [ARCHITECTURE.md §3.2](ARCHITECTURE.md#32-database-connector-subsystem) |
| Database | **Spark SQL Thrift Server** + **embedded PySpark** connectors | available in Settings → Databases | [ARCHITECTURE.md §3.2](ARCHITECTURE.md#32-database-connector-subsystem) |
| Observability | **MLflow** tracing of every LLM completion (cost, tokens, latency, errors) | opt-in via `MITO_MLFLOW_ENABLED=true` | [ARCHITECTURE.md §2.6](ARCHITECTURE.md#26-observability) |

Full design rationale and extension points are in [ARCHITECTURE.md](ARCHITECTURE.md). Developer-facing repo guide is in [CLAUDE.md](CLAUDE.md).

### Enabling the new features

```bash
# Local open-source models via Ollama
export OLLAMA_MODELS="qwen3:32b,deepseek-r1:32b,kimi-k2"
export OLLAMA_BASE_URL="http://localhost:11434/v1"

# MLflow tracing for LLM calls
pip install mlflow
export MITO_MLFLOW_ENABLED=true
export MLFLOW_TRACKING_URI=http://localhost:5000
mlflow ui --port 5000  # in another terminal

# Hive / Trino / Presto / BigQuery / Spark
# No env config needed — add a connection in Settings → Databases.
# Drivers are pip-installed automatically on first connection.
```

<br>

<div align="center">
  <a href="https://www.loom.com/share/3b6af8fd9bda4559918105424222b65c" target="_blank" rel="noopener">
    <img src="https://github.com/user-attachments/assets/2a02f9c0-fa4c-4b51-938b-55ce5fc95287" alt="Mito Demo">
  </a>
</div>

<br>

Mito is an open source tool (look around...), and will always be built by and for our community. See our [plans page](https://www.trymito.io/plans) for more detail about our features, and consider purchasing Mito Pro to help fund development.

## ⚡️ Install Mito
To get started, open a terminal, command prompt, or Anaconda Prompt. Then, run the command
```
python -m pip install mito-ai mitosheet
```
Then launch Jupyter by running the command
```
jupyter lab
```
This will install Mito for JupyterLab 4.0. More detailed installation instructions can also be found [here](https://docs.trymito.io/getting-started/installing-mito).

## 📚 Documentation
You can find all [Mito documentation available here](https://docs.trymito.io).

## ✋🏾 Getting Help
To get support, join our [Discord](https://discord.com/invite/XdJSZyejJU), [Slack](https://join.slack.com/t/trymito/shared_invite/zt-1h6t163v7-xLPudO7pjQNKccXz7h7GSg), or send us an [email](mailto:founders@sagacollab.com)

## 🙏 Acknowledgements

This fork builds on prior work from the open-source community. In particular:

- **[mito-ds/mito](https://github.com/mito-ds/mito)** — upstream Mito project; everything here started as a fork of Saga Inc.'s Jupyter extensions. AGPL-3.0 license preserved.
- **[Pinterest Querybook](https://github.com/pinterest/querybook)** — the engine catalog and connection-parameter shapes for **Apache Hive, Trino, Presto, and Google BigQuery** were informed by Querybook's `lib/query_executor/` modules. Mito uses SQLAlchemy + `information_schema` rather than raw DBAPI clients, but the parameter set, default ports, auth-mode list, and per-engine quirks (Hive LDAP/Kerberos modes, Trino `http_scheme`, BigQuery service-account JSON via ADC fallback) follow Querybook's conventions.
- **[alphaiterations/agentic-ai-usecases — genai-observability](https://github.com/alphaiterations/agentic-ai-usecases/tree/main/advanced/genai-observability)** — the **MLflow tracing layer** (cost / token / latency span attributes, lazy `_init_once`, fail-open decorator pattern, per-1M-tokens pricing table, `bytes.input`/`bytes.output`/`tokens.input`/`tokens.output`/`cost.usd`/`duration_ms` attribute schema) is patterned after this reference implementation.

Thanks to the maintainers and contributors of the projects above. Any bugs introduced in the integration are entirely this fork's, not theirs.
