# Stage 1: Builder
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no dev group)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY codehive/ codehive/
COPY alembic.ini ./

# Install the project itself
RUN uv sync --frozen --no-dev


# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd --gid 1000 codehive && \
    useradd --uid 1000 --gid 1000 --create-home codehive

WORKDIR /app

# Copy the virtual environment and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/codehive /app/codehive
COPY --from=builder /app/alembic.ini /app/alembic.ini

# Copy entrypoint
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

EXPOSE 7433

# Switch to non-root user
USER codehive

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7433/api/health')" || exit 1

ENTRYPOINT ["/app/docker-entrypoint.sh"]
