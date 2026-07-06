# ---------- Stage 1: Build ----------
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT="/venv"

WORKDIR /app

# Leverage Layer Caching for uv lockfiles
COPY pyproject.toml uv.lock ./

# Synchronize production dependencies (LangGraph, Celery, OpenAI SDK etc.)
RUN uv sync --frozen --no-dev --no-install-project

# ---------- Stage 2: Runtime ----------
FROM python:3.14-slim AS final

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

# Bring over the built environment containing your runtime libs
COPY --from=builder /venv /venv

# Copy source tree
COPY . .

CMD ["python", "main.py"]
