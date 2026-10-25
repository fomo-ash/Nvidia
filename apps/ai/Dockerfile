FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_SYSTEM_PYTHON=1
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml ./
COPY app ./app
RUN uv pip install --no-cache .

RUN chown -R app:app /app
USER app
EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS development
USER root
COPY tests ./tests
RUN uv pip install --no-cache '.[dev]'
USER app

FROM base AS runtime
