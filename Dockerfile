FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations


FROM base AS development

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip install --upgrade pip \
    && pip install ".[dev]"

COPY tests ./tests

RUN mkdir -p /app/uploads && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "silly_teamwork.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM base AS production

RUN pip install --upgrade pip && pip install .

RUN mkdir -p /app/uploads && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "silly_teamwork.main:app", "--host", "0.0.0.0", "--port", "8000"]
