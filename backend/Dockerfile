# ---------- Stage 1: Build ----------
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# Optimized UV configuration
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# Install dependencies into a standard location for easy copying
ENV UV_PROJECT_ENVIRONMENT="/venv"

WORKDIR /app

# Only copy lockfiles first to maximize layer cache
# If these haven't changed, Docker skips the 'uv sync' step entirely
COPY pyproject.toml uv.lock ./

# Synchronize dependencies
RUN uv sync --frozen --no-dev --no-install-project

# ---------- Stage 2: Runtime ----------
FROM python:3.14-slim AS final

# Standard Python optimizations
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# Add the venv to the path so 'uvicorn', 'alembic', and 'python' refer to the venv versions
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

# Copy the pre-built virtual environment
COPY --from=builder /venv /venv

# Copy only the necessary application source code
COPY . .

EXPOSE 8000

# Execute the startup script instead of launching uvicorn directly
CMD ["sh", "scripts/start.sh"]
