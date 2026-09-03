# Railway GitHub integration builds from the monorepo root (not short-squeeze-core/).
# Paths are prefixed so COPY works with repository-root build context.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY short-squeeze-core/pyproject.toml short-squeeze-core/README.md ./
COPY short-squeeze-core/src ./src
RUN pip install --no-cache-dir .

COPY --chown=app:app short-squeeze-core/apps ./apps
COPY --chown=app:app short-squeeze-core/scripts ./scripts
COPY --chown=app:app short-squeeze-core/tools ./tools
RUN mkdir -p /app/exports/research-screener \
    && chown -R app:app /app/exports

USER app

EXPOSE 8080

CMD ["python", "-m", "apps.research_screener", "--mode", "CLOUD_PROVIDER_MODE", "--no-browser"]
