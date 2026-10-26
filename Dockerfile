# syntax=docker/dockerfile:1.7
#
# The Salli server: the HTTP API, the MCP server and salli-server, from
# uv.lock exactly. Run it with compose.yaml (docs/self-host.md).
#
#   docker build -t salli .
#
# The image serves the HTTP API, the MCP server and the console (/console).
#
# Three stages: Node builds the console (packages/console) from
# package-lock.json; uv installs the locked dependencies and Salli into a
# virtual environment; and the final image is that environment on a slim
# Python, with the console's built files beside it (SALLI_CONSOLE_DIR), and
# no Node.js, no uv, no compiler and no source tree, running as an
# unprivileged user.

# Base images are pinned by digest, so a build is the same build tomorrow; the
# uv version matches CI's.
FROM ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff AS uv

# ── Build: the console ────────────────────────────────────────────────────────
# Static files, the same on every platform: built once, on the builder's own
# platform, and copied into each image (docs/design/console.md, section 9).
FROM --platform=$BUILDPLATFORM node:22.23.3-bookworm-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392 AS console

WORKDIR /src
# The workspace's manifests and lock first: npm ci installs exactly the
# console's locked dependencies, and runs no package's install scripts.
COPY package.json package-lock.json ./
COPY packages/sdk/package.json packages/sdk/
COPY packages/cli/package.json packages/cli/
COPY packages/console/package.json packages/console/
RUN --mount=type=cache,target=/root/.npm \
    npm ci --workspace @leafmonkeylabs/salli-console --ignore-scripts --no-audit --no-fund
# The console builds from the SDK's sources, as its tests do.
COPY tsconfig.base.json ./
COPY packages/sdk/src packages/sdk/src
COPY packages/console packages/console
# The build checks the budget (scripts/budget.mjs) and fails over it.
RUN npm run build --workspace @leafmonkeylabs/salli-console \
 && rm -rf packages/console/dist/.vite

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

# The base image's security fixes published since its digest (OpenSSL's,
# which the image scan holds it to).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libssl3=3.0.22-1~deb12u2 openssl=3.0.22-1~deb12u2 \
 && rm -rf /var/lib/apt/lists/*

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
# The console, served at /console (SALLI_CONSOLE_DIR); SALLI_CONSOLE=false
# switches it off.
COPY --from=console --chown=root:root /src/packages/console/dist /opt/salli-console

# Settings come from the environment only (docs/self-host.md lists them).
ENV PATH=/opt/salli/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/var/lib/salli \
    ENVIRONMENT=production \
    SALLI_STORAGE_DIR=/var/lib/salli/files \
    SALLI_CONSOLE_DIR=/opt/salli-console

# Numeric, so a runtime can tell it isn't root without resolving names.
USER 10001:10001
WORKDIR /var/lib/salli
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status != 200)"]

# Migrate (safe on every start: it does nothing at head, and holds a lock so
# two servers starting together migrate once), then serve.
CMD ["salli-server", "serve", "--migrate", "--host", "0.0.0.0", "--port", "8000"]
