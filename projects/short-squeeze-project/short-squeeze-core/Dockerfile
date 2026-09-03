# ─── Stage 1: Builder ──────────────────────────────────────────────────
# Install Python dependencies and build any compiled extensions.
FROM python:3.12-slim AS builder

WORKDIR /build

# Install the package into an isolated prefix so the runtime stage can
# copy only what it needs — no build toolchain carried into the final image.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . --prefix /install

# ─── Stage 2: Runtime ──────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app

# Copy the installed package (and all its dependencies) from the builder.
COPY --from=builder /install /usr/local

# Copy application code, scripts, and bundled frozen-demo data.
COPY --chown=app:app apps ./apps
COPY --chown=app:app scripts ./scripts

# Create export directory with correct ownership.
RUN mkdir -p /app/exports/research-screener \
    && chown -R app:app /app/exports

USER app

EXPOSE 8080

# Mode is determined entirely by the SQUEEZE_APP_MODE env var at runtime.
# docker-compose.yml sets SQUEEZE_APP_MODE=CLOUD_PROVIDER_MODE by default.
# The local override (docker-compose.local.yml) changes it to LOCAL_FULL.
CMD ["python", "-m", "apps.research_screener", "--mode", "CLOUD_PROVIDER_MODE", "--no-browser"]
