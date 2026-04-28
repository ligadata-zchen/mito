# ─────────────────────────────────────────────────────────────────────────────
# Mito AI fork — single-stage Dockerfile
#
# Installs mito-ai-core + mito-ai from this fork's git source (so all the
# fork-specific extensions ship in the labextension bundle), plus mitosheet
# from PyPI (unchanged by the fork). Final image runs JupyterLab on :8888.
#
# Image size: ~1.5 GB. For a slimmer ~600 MB runtime, see Dockerfile.slim.
#
# Build:
#   docker build -t mito-fork:latest .
#   docker build -t mito-fork:latest --build-arg MITO_REF=feat/my-branch .
#
# Run:
#   docker run --rm -p 8888:8888 \
#       -e ANTHROPIC_API_KEY=sk-ant-... \
#       -v "$PWD:/workspace" \
#       mito-fork:latest
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/ligadata-zchen/mito"
LABEL org.opencontainers.image.description="Mito AI (fork) — Jupyter extensions with extended LLM provider, OLAP/Spark connectors, and MLflow observability"
LABEL org.opencontainers.image.licenses="AGPL-3.0-only"

# ── Build args ─────────────────────────────────────────────────────────────
# Which git ref of the fork to install. Override at build time:
#   docker build --build-arg MITO_REF=v0.1.0 ...
ARG MITO_REF=main
# Toggle the optional connector + MLflow extras. "all" pre-installs every
# database driver and mlflow so the image works fully offline.
ARG MITO_EXTRAS=all
# Set this to a single-line value to bake an API key in (NOT recommended;
# pass at run time via -e ANTHROPIC_API_KEY=... instead).
# ARG ANTHROPIC_API_KEY=

# ── System dependencies ────────────────────────────────────────────────────
# - curl + ca-certificates: needed for the NodeSource setup script
# - git: pip clones the fork during install
# - build-essential: native extensions (psycopg2-binary, etc.) compile here
# - nodejs (20.x): hatch-jupyter-builder shells out to jlpm during pip install
#                  of mito-ai. Without Node, the labextension bundle is missing
#                  and the fork's TypeScript changes (model picker, DB forms)
#                  silently don't ship.
# - libsasl2-dev + sasl modules: required for Hive/Spark Thrift LDAP/Kerberos
# - unixodbc-dev: required for pyodbc (MSSQL connector)
# - default-jre-headless: required by embedded PySpark (SparkSession needs JVM)
# - libpq-dev: pinned source build of psycopg2 needs libpq headers
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential \
        libsasl2-dev libsasl2-modules-gssapi-mit \
        unixodbc-dev libpq-dev \
        default-jre-headless \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify Node is on PATH before the JupyterLab build runs.
RUN node --version && npm --version

# ── Python install ─────────────────────────────────────────────────────────
# Upgrade pip first; build isolation needs a recent pip.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install order matters: mito-ai depends on mito-ai-core. mito-ai-core is
# installed without extras here; if MITO_EXTRAS includes "all" or "mlflow",
# mito-ai's extras pull mito-ai-core[mlflow] transitively.
#
# The `[${MITO_EXTRAS}]` interpolation lets you build a slim image:
#   docker build --build-arg MITO_EXTRAS= ...           # no extras
#   docker build --build-arg MITO_EXTRAS=hive ...       # just hive
#   docker build --build-arg MITO_EXTRAS=hive,bigquery  # subset
#   docker build --build-arg MITO_EXTRAS=all ...        # everything (default)
RUN pip install --no-cache-dir \
        "mito-ai-core @ git+https://github.com/ligadata-zchen/mito.git@${MITO_REF}#subdirectory=mito-ai-core"
RUN pip install --no-cache-dir \
        "mito-ai${MITO_EXTRAS:+[${MITO_EXTRAS}]} @ git+https://github.com/ligadata-zchen/mito.git@${MITO_REF}#subdirectory=mito-ai"
RUN pip install --no-cache-dir mitosheet

# ── Sanity checks ─────────────────────────────────────────────────────────
# Fail the build early if anything is wrong with the install.
RUN python -c "import mito_ai_core; import mito_ai; import mitosheet; print('mito_ai_core', mito_ai_core.__name__); print('mito_ai', mito_ai.__name__); print('mitosheet', mitosheet.__name__)"
RUN jupyter labextension list 2>&1 | grep -E "mito-ai|mitosheet" || (echo "labextensions not registered" && exit 1)
RUN jupyter server extension list 2>&1 | grep -i "mito" || (echo "server extensions not registered" && exit 1)

# ── Runtime ───────────────────────────────────────────────────────────────
EXPOSE 8888
WORKDIR /workspace

# Default: bind to all interfaces, no token. Override -e/-p for production.
CMD ["jupyter", "lab", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--allow-root", \
     "--ServerApp.token=", \
     "--ServerApp.password=", \
     "--ServerApp.root_dir=/workspace"]
