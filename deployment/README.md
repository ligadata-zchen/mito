# Install & Deployment

This fork is **not published to PyPI**. The standard `pip install mito-ai mitosheet` command pulls upstream `mito-ds/mito` and will not include this fork's extensions (Opus 4.6 / Ollama / Hive / Trino / Presto / BigQuery / Spark / MLflow). To use the fork's features, install from source or run the bundled Docker image.

The full install reference is [`../INSTALL.md`](../INSTALL.md). This page is the short version.

---

## Install Mito — build from source

Requires Python ≥ 3.11 and Node.js ≥ 18 on PATH.

```bash
git clone https://github.com/ligadata-zchen/mito.git
cd mito

# Order matters: mito-ai depends on mito-ai-core.
pip install -e ./mito-ai-core
pip install -e "./mito-ai[all]"     # [all] = every connector + MLflow
pip install mitosheet               # spreadsheet (unchanged in this fork — fine from PyPI)

# Build the JupyterLab labextension once.
cd mito-ai
touch yarn.lock                     # required for Yarn 3 first-run
jlpm install
jlpm build
jupyter labextension develop . --overwrite
jupyter server extension enable --py mito_ai

# Run
cd ..
jupyter lab
```

The `[all]` extra pre-installs PySpark 3.5+, MLflow 3.0+, and every database connector driver. For a slimmer install, replace `[all]` with a subset like `[hive,bigquery,mlflow]` — see the extras matrix in [`../INSTALL.md`](../INSTALL.md#optional-dependency-extras).

For a non-editable install (no clone, just pip-from-git):

```bash
pip install -r ../requirements-docker.txt
```

---

## Install Mito — build and run with Docker

The fastest path. Single-stage Dockerfile bundles everything (~1.5 GB):

```bash
# From the repo root (where the Dockerfile lives).
docker build -t mito-fork:latest .

docker run --rm -p 8888:8888 \
    -e ANTHROPIC_API_KEY=sk-ant-... \
    -v "$PWD:/workspace" \
    mito-fork:latest

# → http://localhost:8888/lab
```

For a slimmer (~600 MB) production runtime image, use the multi-stage build:

```bash
docker build -f Dockerfile.slim -t mito-fork:slim .
docker run --rm -p 8888:8888 -v "$PWD:/workspace" mito-fork:slim
```

Build-arg knobs:

| Arg | Default | What it does |
|---|---|---|
| `MITO_REF` | `main` | Git ref (branch / tag / SHA) to install from the fork |
| `MITO_EXTRAS` | `all` | Which extras to bake in. Use `bigquery,mlflow` (or any subset) for a slimmer image, or `MITO_EXTRAS=` for an absolute-minimum install where drivers lazy-install on first connection |

Example: pin to a specific commit and bake in only BigQuery + MLflow:

```bash
docker build --build-arg MITO_REF=b5dc54d --build-arg MITO_EXTRAS=bigquery,mlflow -t mito-fork:slim .
```

Runtime environment variables (set with `-e` on `docker run`):

| Env var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | Provider keys |
| `OLLAMA_MODELS` | Comma-separated list, e.g. `qwen3:32b,deepseek-r1:32b` |
| `OLLAMA_BASE_URL` | Default `http://localhost:11434/v1`; override to `http://host.docker.internal:11434/v1` to reach the host's Ollama from inside Docker |
| `MITO_MLFLOW_ENABLED` | `true` to enable MLflow tracing |
| `MLFLOW_TRACKING_URI` | e.g. `http://host.docker.internal:5000` |
| `MLFLOW_EXPERIMENT` | Default `mito-ai` |

Full env-var reference: [`../ARCHITECTURE.md` § Configuration](../ARCHITECTURE.md#5-configuration-reference).

---

## Verifying the install

```bash
# Fork-specific models registered
python -c "from mito_ai_core.utils.model_utils import STANDARD_MODELS; \
           assert 'claude-opus-4-6' in STANDARD_MODELS; print('Opus 4.6 OK')"

# Fork-specific DB engines registered
python -c "from mito_ai.db.crawlers.constants import SUPPORTED_DATABASES; \
           need = {'hive','trino','presto','bigquery','spark_thrift','pyspark'}; \
           assert not (need - set(SUPPORTED_DATABASES)); print('all engines OK')"

# JupyterLab knows about the extension
jupyter labextension list 2>&1 | grep mito-ai
```

In the JupyterLab UI: model picker should list "Claude Opus 4.6", and **Settings → Databases → Add Connection** should list Apache Hive, Trino, Presto, Google BigQuery, Spark SQL (Thrift Server), and PySpark alongside the original engines.

---

## PyPI publishing scripts (maintainer notes)

The Python files in this folder (`deploy.py`, `deploy_hatch.py`, `bump_version.py`, `bump_pyproject_version.py`) are upstream Mito's release tooling for publishing `mito-ai` and `mitosheet` to PyPI / TestPyPI. **This fork does not publish to PyPI**, so those scripts are unused — kept for parity with upstream and as a reference if a private package index is ever introduced for `mito-ai-ligadata` or similar.

If you do want to publish a private wheel, build it from `mito-ai/` and upload to your private index:

```bash
cd mito-ai && python -m build --wheel
twine upload --repository-url https://your-index.example.com/ dist/*.whl
```

For now, the supported install paths are **source build** and **Docker** as documented above.
