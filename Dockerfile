FROM python:3.13-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


FROM base AS backend
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]



FROM base AS worker
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libxcb1 \
    libxext6 \
    libsm6 \
    libxrender1 \
    libglib2.0-0 \
    libgl1 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-base.txt requirements-worker.txt ./
RUN pip install --no-cache-dir -r requirements-base.txt -r requirements-worker.txt
COPY . .