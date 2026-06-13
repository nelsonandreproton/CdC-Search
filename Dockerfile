FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências de sistema mínimas (lxml precisa de libxml2/libxslt).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts

# Diretório de dados (SQLite) — montado como volume.
RUN mkdir -p /data

EXPOSE 8000

# Default: serve a aplicação web. O worker usa um command diferente.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
