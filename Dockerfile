# ── SIGIPLAN · imagen de producción ──────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencias de Python (capa cacheable)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código de la aplicación
COPY . .

# Usuario sin privilegios + carpeta de subidas
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/app/static/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# 2 workers sync: adecuado para un VPS básico. Sube --workers cuando crezca la carga.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "wsgi:app"]
