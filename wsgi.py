"""Punto de entrada WSGI para servidores de producción (gunicorn).

Uso:  gunicorn wsgi:app
El entorno se toma de FLASK_ENV (por defecto 'prod' en este entrypoint).
"""
import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "prod"))
