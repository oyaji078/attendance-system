FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/apps/api-python:/app/apps/worker-python

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY apps/api-python ./apps/api-python
COPY apps/worker-python ./apps/worker-python
COPY services ./services
COPY db ./db

RUN pip install --upgrade pip \
    && pip install .

CMD ["python", "-m", "worker.main"]

