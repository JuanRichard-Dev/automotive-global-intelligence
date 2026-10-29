# API REST independente do runtime Java do ETL.
FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN python -m pip install --no-cache-dir \
    fastapi==0.162.0 pydantic==2.14.1 'psycopg[binary]==3.3.6' \
    uvicorn==0.54.0 numpy==2.5.4 \
    && useradd --system --uid 10001 --create-home automotive
COPY api ./api
COPY data/media ./data/media
USER automotive
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
