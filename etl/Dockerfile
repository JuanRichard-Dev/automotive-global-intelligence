# Spark 4.2.1 suporta Java17 e Python3.12. Debian12 fornece o JRE17 oficial.
FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SPARK_LOCAL_IP=127.0.0.1 \
    PYSPARK_PYTHON=python \
    JAVA_HOME=/opt/java
RUN apt-get update \
    && apt-get install --yes --no-install-recommends openjdk-17-jre-headless ca-certificates \
    && ln -s "$(dirname "$(dirname "$(readlink -f /usr/bin/java)")")" /opt/java \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="${JAVA_HOME}/bin:${PATH}"
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY etl ./etl
COPY db ./db
COPY data/raw ./data/raw
COPY data/seed ./data/seed
COPY data/media ./data/media
COPY notebooks ./notebooks
COPY tests ./tests
COPY api ./api
COPY docs ./docs
RUN mkdir -p /app/data/bronze /app/data/silver /app/data/analytics /app/data/quarantine /app/notebooks/resultados
CMD ["python", "-m", "etl.pipeline"]
