FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY --chown=app:app apps ./apps
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app tools ./tools
RUN mkdir -p /app/exports/research-screener \
    && chown -R app:app /app/exports

USER app

EXPOSE 8080

CMD ["python", "-m", "apps.research_screener", "--mode", "CLOUD_PROVIDER_MODE", "--no-browser"]
