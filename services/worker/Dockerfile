FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PIP_DEFAULT_TIMEOUT=180

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        git \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY services/worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY packages ./packages
COPY services/worker/app ./app

CMD ["celery", "-A", "app.worker:celery_app", "worker", "--loglevel=INFO", "--concurrency=1"]
