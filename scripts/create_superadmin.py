"""Crea el primer SUPER_ADMIN de la plataforma en un despliegue limpio,
sin cargar datos de demostración (a diferencia de seed.py).

Idempotente: si ya existe un SUPER_ADMIN, no hace nada.
Lee las credenciales del entorno (ver .env):
  BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD,
  BOOTSTRAP_ADMIN_FIRST_NAME, BOOTSTRAP_ADMIN_LAST_NAME

Uso (dentro del contenedor):
  docker compose exec app python scripts/create_superadmin.py
"""
import os
from app import create_app
from app.models.user import User


def main():
    # Inicializa la app (conexión a Mongo + bcrypt)
    create_app(os.environ.get("FLASK_ENV", "prod"))

    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    first = os.environ.get("BOOTSTRAP_ADMIN_FIRST_NAME", "Administrador").strip()
    last = os.environ.get("BOOTSTRAP_ADMIN_LAST_NAME", "Goventia").strip()

    if not email or not password:
        raise SystemExit(
            "Falta BOOTSTRAP_ADMIN_EMAIL o BOOTSTRAP_ADMIN_PASSWORD en el entorno."
        )

    existing = User.objects(role="SUPER_ADMIN").first()
    if existing:
        print(f"Ya existe un SUPER_ADMIN ({existing.email}); no se crea otro.")
        return

    if User.objects(email=email).first():
        print(f"Ya existe un usuario con el email {email}; no se crea.")
        return

    user = User(
        email=email,
        first_name=first,
        last_name=last,
        role="SUPER_ADMIN",
        is_active=True,
    )
    user.set_password(password)
    user.save()
    print(f"SUPER_ADMIN creado: {user.email}")
    print("Inicia sesión y cambia la contraseña desde tu perfil cuanto antes.")


if __name__ == "__main__":
    main()
