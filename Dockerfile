# Imagem da API Alerta Cheia (inclui dados e modelos gerados no build)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/alerta_cheia.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bigdata/ bigdata/
COPY ia/ ia/
COPY iot/ iot/
COPY app/ app/
COPY frontend/ frontend/
COPY scripts/ scripts/

# gera bronze/silver/gold e treina os modelos dentro da imagem (reprodutível: semente fixa)
RUN python -m scripts.preparar \
    && rm -rf bigdata/data/bronze \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /data && chown -R app:app /data /app

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
