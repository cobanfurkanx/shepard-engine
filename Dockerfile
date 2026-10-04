FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY sql ./sql
RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 engine
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001
EXPOSE 8080
CMD ["uvicorn", "shepard_engine.api:app", "--host", "0.0.0.0", "--port", "8080"]
