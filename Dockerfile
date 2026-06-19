# Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Installazione delle dipendenze di sistema necessarie per PostgreSQL e utilità varie
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia dei requisiti e installazione
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia del codice sorgente
COPY . .

# Il comando di default può essere sovrascritto dal docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]