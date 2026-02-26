# Build stage: install dependencies with uv
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Install dependencies into a virtual environment (no project code yet)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable --no-install-project

# Copy source and install the project itself
COPY . .
RUN uv sync --frozen --no-dev --no-editable

# Runtime stage: minimal image with only the venv
FROM python:3.13-slim-bookworm

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src ./src
COPY --from=builder /app/api.py ./api.py

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 80

CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
