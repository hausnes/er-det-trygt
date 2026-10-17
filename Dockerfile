# Byggjer frontend-en og pakkar han saman med backend-en i eitt image.
# Fungerer på både Intel/AMD (amd64) og ARM (arm64), som er dei vanlege NAS-prosessorane.

# --- Frontend ---
# Resultatet er berre statiske filer, så dette steget kan alltid køyre på byggjemaskina sin arkitektur
FROM --platform=$BUILDPLATFORM node:24-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Backend + ferdigbygd frontend ---
FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend /src/dist ./static

RUN useradd --system --no-create-home app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
# --proxy-headers: tenesta står bak NAS-en sin reverse proxy, som tek seg av HTTPS
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
