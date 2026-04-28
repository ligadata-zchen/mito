# Installation Guide

Mito's published PyPI packages (`mito-ai`, `mitosheet`) are upstream `mito-ds` builds. They do **not** include this fork's extensions:

- Claude Opus 4.6
- Ollama multi-model router (Qwen, DeepSeek, Kimi, …)
- Hive / Trino / Presto / BigQuery / Spark / PySpark database connectors
- MLflow tracing of LLM completions

To get those, install from this repo's source. Below are the four ways to do that, ordered by use case.

---

## TL;DR

| You want | Use |
|---|---|
| One command, throw-away container, see it run | [Docker single-stage](#docker--single-stage-recommended) |
| Production runtime image, smallest size | [Docker multi-stage](#docker--multi-stage-production) |
| Hack on the code, hot-reload | [Editable install from clone](#editable-install-from-clone) |
| Reproducible install in any clean Python env | [pip from git](#pip-from-git) |

---

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | **3.11** (`>=3.11`) | both `mito-ai-core` and `mito-ai` declare `requires-python = ">=3.11"` |
| JupyterLab | **4.1+** (`>=4.1.0,<5`) | pulled in transitively by `pip install mito-ai`; do not preinstall a 3.x lab |
| Node.js | ≥ 18 (20 recommended) | `pip install mito-ai` runs `jlpm build` for the labextension |
| Java (JRE) | **17** | required by PySpark 3.5+ for the embedded SparkSession connector |
| PySpark | **3.5+** | bundled by `mito-ai[spark]`; ships with the Spark 3.5 wire protocol |
| MLflow | **3.0+** | bundled by `mito-ai-core[mlflow]` / `mito-ai[mlflow]`; modern tracing API |
| `libsasl2-dev` + GSSAPI module | distro package | only if using Hive / Spark Thrift with LDAP/Kerberos |
| `unixodbc-dev` | distro package | only if using the MSSQL connector |

> Python 3.9 / 3.10 are no longer supported. PyPI's `pip install mito-ai-core` will refuse to install on those interpreters because of `requires-python = ">=3.11"`. Use `pyenv install 3.11` or the `python:3.11-slim` Docker base.

If Node.js is missing during `pip install mito-ai`, the build silently produces a stale labextension bundle and **the fork's UI changes (model picker entries, new DB connection forms) won't ship**. Backend Python still works, so this is a confusing class of bug. Always check `node --version` first.

---

## Docker — single-stage (recommended)

Drop-in image. Builds from your fork's git source, includes every connector and MLflow:

```bash
docker build -t mito-fork:latest .
```

Run JupyterLab on `:8888`:

```bash
docker run --rm -p 8888:8888 \
    -e ANTHROPIC_API_KEY=sk-ant-... \
    -v "$PWD:/workspace" \
    mito-fork:latest
```

Open http://localhost:8888/lab.

### Build-arg knobs

| Arg | Default | What it does |
|---|---|---|
| `MITO_REF` | `main` | Git ref (branch / tag / SHA) of the fork to install |
| `MITO_EXTRAS` | `all` | Which connector extras to bake in. See below. |

Examples:

```bash
# Pin to a specific commit
docker build --build-arg MITO_REF=fffa210 -t mito-fork:fffa210 .

# Slim image with just BigQuery and MLflow
docker build --build-arg MITO_EXTRAS=bigquery,mlflow -t mito-fork:slim .

# Absolute minimum — drivers will be lazy-installed at runtime by
# install_db_drivers() the first time a connection is created
docker build --build-arg MITO_EXTRAS= -t mito-fork:minimal .
```

### Environment variables for the running container

| Env var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | Provider keys (use any one or more) |
| `OLLAMA_MODELS` | Comma-separated list, e.g. `qwen3:32b,deepseek-r1:32b` |
| `OLLAMA_BASE_URL` | Default `http://localhost:11434/v1` — override to `http://host.docker.internal:11434/v1` to reach the host's Ollama from inside Docker |
| `MITO_MLFLOW_ENABLED` | `true` to enable MLflow tracing |
| `MLFLOW_TRACKING_URI` | e.g. `http://host.docker.internal:5000` |
| `MLFLOW_EXPERIMENT` | Default `mito-ai` |

Full env-var reference is in [ARCHITECTURE.md §5](ARCHITECTURE.md#5-configuration-reference).

---

## Docker — multi-stage (production)

Builds wheels in a heavy stage, copies them into a slim stage. Final image ~600 MB vs. ~1.5 GB for single-stage.

```bash
docker build -f Dockerfile.slim -t mito-fork:slim .
docker run --rm -p 8888:8888 -v "$PWD:/workspace" mito-fork:slim
```

Wheels are at `/wheels/` inside the builder stage if you need to extract them for a private package index.

---

## Editable install from clone

For iterating on the codebase. Requires Node.js 18+ and (if using PySpark) Java.

```bash
git clone https://github.com/ligadata-zchen/mito.git
cd mito

# Order matters: mito-ai depends on mito-ai-core.
pip install -e ./mito-ai-core
pip install -e "./mito-ai[test,all-connectors,mlflow]"

# Build the JupyterLab labextension once (then re-run on TS changes,
# or use `jlpm watch` for auto-rebuild).
cd mito-ai
touch yarn.lock                            # required for Yarn 3 first-run
jlpm install
jlpm build
jupyter labextension develop . --overwrite
jupyter server extension enable --py mito_ai

# Spreadsheet (unchanged in this fork — fine to install from PyPI)
pip install mitosheet

# Run
cd ..
jupyter lab
```

To hot-reload the frontend while developing:

```bash
# Terminal 1 — TypeScript watcher
cd mito-ai && jlpm watch

# Terminal 2 — JupyterLab with backend autoreload
jupyter lab --autoreload
```

---

## pip from git

For reproducible installs into any clean Python env (no clone, no Docker). Node.js is still required.

### Using the bundled requirements file

```bash
pip install -r requirements-docker.txt
```

This pins to `main`. To pin to a specific tag or commit, edit the `@main` references in `requirements-docker.txt` to `@v0.1.0` or `@<sha>`.

### Or one command at a time

```bash
pip install \
    "mito-ai-core @ git+https://github.com/ligadata-zchen/mito.git@main#subdirectory=mito-ai-core"
pip install \
    "mito-ai[all] @ git+https://github.com/ligadata-zchen/mito.git@main#subdirectory=mito-ai"
pip install mitosheet
```

The `[all]` extra pulls every connector + MLflow. Substitute `[hive]`, `[bigquery]`, `[spark]`, etc. if you want a slimmer install. With no extras, drivers are lazy-installed at runtime when the user first creates a connection of that type.

---

## Optional dependency extras

Both packages expose extras you can mix and match.

### `mito-ai-core` extras

| Extra | What it pulls | When to use |
|---|---|---|
| `mlflow` | `mlflow>=2.14.0` | If you want `MITO_MLFLOW_ENABLED=true` to actually emit spans |
| `litellm` | `litellm` | Enterprise LiteLLM router |
| `test` | pytest + mypy + types-* | Running the test suite |

### `mito-ai` extras

| Extra | What it pulls | Connector(s) it enables |
|---|---|---|
| `hive` | `pyhive[hive]` + `thrift` + `thrift-sasl` | Apache Hive |
| `trino` | `trino[sqlalchemy]` | Trino |
| `presto` | `pyhive[presto]` | Presto |
| `bigquery` | `sqlalchemy-bigquery` + `google-cloud-bigquery` | Google BigQuery |
| `spark` | `pyspark` + `pyhive[hive]` + `thrift` + `thrift-sasl` | Spark Thrift Server **and** embedded PySpark |
| `all-connectors` | union of the above | Every database connector |
| `mlflow` | `mito-ai-core[mlflow]` (transitive) | MLflow tracing |
| `all` | `all-connectors` + `mlflow` | Everything |
| `test`, `deploy` | dev tooling | (existing upstream extras) |

Combine with comma syntax: `pip install "mito-ai[hive,bigquery,mlflow]"`.

---

## Verification checklist

After installing by any of the methods above, run these to confirm the fork actually shipped:

```bash
# 1. Python packages report fork versions
python -c "import mito_ai_core, mito_ai; print(mito_ai_core.__version__, mito_ai.__version__)"

# 2. JupyterLab knows about both extensions
jupyter labextension list 2>&1 | grep -E "mito-ai|mitosheet"

# 3. Server extension is registered
jupyter server extension list 2>&1 | grep -i mito

# 4. The fork's models are in the registry
python -c "from mito_ai_core.utils.model_utils import STANDARD_MODELS; \
           assert 'claude-opus-4-6' in STANDARD_MODELS, STANDARD_MODELS; \
           print('Opus 4.6 registered')"

# 5. The fork's DB engines are in the SUPPORTED_DATABASES dict
python -c "from mito_ai.db.crawlers.constants import SUPPORTED_DATABASES; \
           need = {'hive','trino','presto','bigquery','spark_thrift','pyspark'}; \
           missing = need - set(SUPPORTED_DATABASES); \
           assert not missing, f'missing engines: {missing}'; \
           print('All fork DB engines present')"

# 6. MLflow observability module imports (does not require mlflow installed)
python -c "from mito_ai_core.utils import mlflow_observability as m; \
           print('enabled:', m.is_enabled())"
```

In the JupyterLab UI:

- **Model picker** → "Claude Opus 4.6" should appear. If `OLLAMA_MODELS` is set, also `ollama/<name>` entries.
- **Settings → Databases → Add Connection → Type dropdown** → should list Apache Hive, Trino, Presto, Google BigQuery, Spark SQL (Thrift Server), PySpark, alongside the original Postgres/MySQL/MSSQL/Oracle/SQLite/Snowflake.

---

## Troubleshooting

### "Loading models…" stuck or model picker shows only upstream models

The labextension bundle didn't build with the fork's TypeScript changes. Caused by Node.js missing during `pip install mito-ai`. Fix:

```bash
node --version    # must be ≥ 18
# Reinstall mito-ai with Node available
pip uninstall -y mito-ai
pip install "mito-ai[all] @ git+https://github.com/ligadata-zchen/mito.git@main#subdirectory=mito-ai"
```

In Docker, this almost always means the base image dropped Node.js between layers — check the Dockerfile.

### `pip install mito-ai` fails with `Cannot find module 'jlpm'`

JupyterLab not present in the build environment. Fix:

```bash
pip install jupyterlab>=4.1
```

(Normally pip fetches it automatically from `[build-system].requires`, but isolated build envs sometimes lose it.)

### Hive connection fails with `sasl/saslwrapper.h: No such file or directory`

System-level SASL libs missing. On Debian/Ubuntu:

```bash
apt-get install libsasl2-dev libsasl2-modules-gssapi-mit
pip install --force-reinstall thrift-sasl
```

### `OSError: [WinError 193] %1 is not a valid Win32 application` when starting PySpark

Java not on PATH. Install JDK/JRE 11+ and re-launch.

### MLflow spans not appearing

Either:
- `MITO_MLFLOW_ENABLED` not set to a truthy value, or
- `mlflow` package not installed (install with `pip install "mito-ai[mlflow]"` or `pip install mlflow`)

The mlflow_observability module is fail-open by design, so misconfiguration silently disables tracing rather than breaking LLM requests.

---

## See also

- [README.md](README.md) — high-level overview + what's added in this fork
- [ARCHITECTURE.md](ARCHITECTURE.md) — deep dive into provider routing, DB connectors, observability
- [CLAUDE.md](CLAUDE.md) — developer-facing repo guide (where things live, conventions)
- [mito-ai/CLAUDE.md](mito-ai/CLAUDE.md) — JupyterLab extension specifics
