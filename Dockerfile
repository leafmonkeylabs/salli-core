# syntax=docker/dockerfile:1.7
#
# The Salli server: the HTTP API, the MCP server and salli-server, from
# uv.lock exactly. Run it with compose.yaml (docs/self-host.md).
#
#   docker build -t salli .
#
# Two stages: uv installs the locked dependencies and Salli into a virtual
# environment, and the final image is that environment on a slim Python, with
# no uv, no compiler and no source tree, running as an unprivileged user.

# Base images are pinned by digest, so a build is the same build tomorrow; the
# uv version matches CI's.
FROM ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc AS uv

# ── Build: the locked environment ─────────────────────────────────────────────
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS build

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/salli

WORKDIR /src

# The dependencies first, on their own layer: they change far less often than
# Salli does. --frozen: exactly uv.lock, or fail.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project

# Then Salli itself, installed as a package (not editable): the final image
# needs no source tree.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ── Run ───────────────────────────────────────────────────────────────────────
# The same base as the build stage: the environment's interpreter is its Python.
FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

ARG VERSION=dev
LABEL org.opencontainers.image.title="Salli" \
      org.opencontainers.image.description="Self-hosted personal finance: ledger, budgets, investments, tax and financial independence. The HTTP API and MCP server." \
      org.opencontainers.image.source="https://github.com/leafmonkeylabs/salli-core" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.version="${VERSION}"

# An unprivileged user, and the two places it writes: uploaded files, and the
# secrets `salli-server secrets init` generates on a first run. Compose mounts
# a named volume on each; a new volume takes this ownership.
RUN groupadd --system --gid 10001 salli \
 && useradd --system --uid 10001 --gid salli --home-dir /var/lib/salli \
      --no-create-home --shell /usr/sbin/nologin salli \
 && mkdir -p /var/lib/salli/files /var/lib/salli/secrets \
 && chown -R salli:salli /var/lib/salli \
 && chmod 0750 /var/lib/salli/files \
 && chmod 0755 /var/lib/salli/secrets

COPY --from=build --chown=root:root /opt/salli /opt/salli

# Settings come from the environment only (docs/self-host.md lists them).
ENV PATH=/opt/salli/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/var/lib/salli \
    ENVIRONMENT=production \
    SALLI_STORAGE_DIR=/var/lib/salli/files

USER salli:salli
WORKDIR /var/lib/salli
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status != 200)"]

# Migrate (safe on every start: it does nothing at head, and holds a lock so
# two servers starting together migrate once), then serve.
CMD ["salli-server", "serve", "--migrate", "--host", "0.0.0.0", "--port", "8000"]
