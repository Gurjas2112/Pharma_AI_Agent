# ---- Repurpora agent server (Aegra + LangGraph) ------------------------------
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    MPLBACKEND=Agg PATH="/app/.venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv
WORKDIR /app

# deps layer (cached)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# app
COPY src ./src
COPY aegra.json langgraph.json ./
COPY scripts ./scripts
RUN uv sync --frozen --no-dev \
 && python -m repurpora.ml.opportunity_scorer --train > /dev/null \
 && useradd -m -u 10001 app && mkdir -p /app/reports_out /app/data/index && chown -R app /app
USER app
EXPOSE 2026
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD curl -fs http://localhost:${PORT:-2026}/health || exit 1
CMD ["sh", "-c", "aegra serve --host 0.0.0.0 --port ${PORT:-2026}"]
