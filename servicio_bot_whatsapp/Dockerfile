FROM python:3.11-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir=/app/wheels -r requirements.txt


FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

COPY --chown=appuser:appgroup api/ api/
COPY --chown=appuser:appgroup core/ core/
COPY --chown=appuser:appgroup services/ services/
COPY --chown=appuser:appgroup workers/ workers/
COPY --chown=appuser:appgroup consumers/ consumers/
COPY --chown=appuser:appgroup *.py ./
COPY --chown=appuser:appgroup gunicorn_config.py .

RUN mkdir -p /app/temp_audio && chown appuser:appgroup /app/temp_audio

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["gunicorn", "-c", "gunicorn_config.py", "run:app"]
