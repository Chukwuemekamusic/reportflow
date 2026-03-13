FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
# libpq-dev + gcc: PostgreSQL client + compilation
# curl: health checks
# WeasyPrint deps: libpango, cairo, gdk-pixbuf (HTML/CSS → PDF rendering)
RUN apt-get update && apt-get install -y \
    libpq-dev gcc curl \
    libpango-1.0-0 libpangoft2-1.0-0 \
    libcairo2 libgdk-pixbuf-2.0-0 \
    libffi-dev \
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
