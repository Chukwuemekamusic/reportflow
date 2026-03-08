FROM python:3.12-slim

WORKDIR /app

# install system dependencies (WeasyPrint needs these in phase 3)

RUN apt-get update && apt-get install -y \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*


# install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files first (Docker layer cache — only re-runs uv sync
# when pyproject.toml or uv.lock changes, not when source code changes)
COPY pyproject.toml uv.lock ./

# Install dependencies into the container's system Python
# --frozen ensures exact versions from uv.lock (no version drift)
# --no-dev skips test dependencies in production
RUN uv sync --frozen --no-dev

# Now copy the rest of the source code
COPY . .
