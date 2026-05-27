FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY packages/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    fastapi==0.111.0 uvicorn[standard]==0.30.0 celery==5.3.6 \
    prometheus-fastapi-instrumentator==7.0.0 python-jose[cryptography]==3.3.0 \
    'sqlalchemy[asyncio]==2.0.30' asyncpg==0.29.0 \
    jsonschema==4.23.0 deal==4.24.4 psycopg2-binary==2.9.9 \
    opentelemetry-api==1.27.0 opentelemetry-sdk==1.27.0 \
    opentelemetry-instrumentation-fastapi==0.48b0 \
    opentelemetry-instrumentation-requests==0.48b0 \
    opentelemetry-exporter-otlp-proto-http==1.27.0

COPY packages/ /app/packages/
COPY api/ /app/api/
ENV PYTHONPATH=/app/packages:/app

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
