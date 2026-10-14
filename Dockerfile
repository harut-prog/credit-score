FROM python:3.11-slim

ARG BUILD_GIT_SHA

ENV BUILD_GIT_SHA=${BUILD_GIT_SHA}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

COPY artifacts/ artifacts/

COPY .dvc/config .dvc/config
COPY data/*.dvc data/
RUN uv run --no-sync dvc config --local core.no_scm true

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "credit.service.app:app", "--host", "0.0.0.0", "--port", "8000"]
