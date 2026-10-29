FROM python:3.12-slim AS base
RUN pip install --no-cache-dir uv==0.9.17
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=0
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv sync --frozen --no-dev --no-editable
RUN chown -R app:app /app
USER app
EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]

FROM base AS development
USER root
COPY tests ./tests
RUN uv sync --frozen --extra dev --no-editable
USER app

FROM base AS runtime
