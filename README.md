# SIGIPLAN 🌱

**Sistema de Gestión de Iniciativas de Inversión Pública**

Plataforma web para que entidades gubernamentales chilenas (municipalidades, ministerios, servicios públicos) gestionen su cartera de proyectos de inversión pública: desde la formulación técnica hasta la aprobación y seguimiento.

---

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | Python 3 + Flask >= 3.0 |
| Base de datos | MongoDB (MongoEngine ODM) |
| Autenticación | Flask-Login + Flask-Bcrypt |
| Frontend | Jinja2 + HTML5/CSS3 |
| Íconos | FontAwesome 6.4 |
| Tipografía | Google Fonts (Literata + Nunito Sans) |

---

## Requisitos Previos

- Python 3.10+
- MongoDB corriendo en `localhost:27018`
- pip

---

## Instalación y Puesta en Marcha

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd Sigiplan

# 2. Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env si es necesario

# 5. Cargar datos de demostración
python seed.py

# 6. Iniciar el servidor
python run.py
```

La aplicación queda disponible en `http://localhost:5000`.

---

## Credenciales de Demostración

Todas las cuentas usan la contraseña `password123`.

| Email | Rol | Descripción |
|---|---|---|
| superadmin@sigiplan.cl | Super Admin | Administrador global de la plataforma |
| admin@santiago.cl | Admin Entidad | Administrador de la Municipalidad de Santiago |
| director@santiago.cl | Director Planificación | Crea y supervisa iniciativas |
| coordinador@santiago.cl | Coordinador Formulación | Coordina el equipo técnico |
| formulador@santiago.cl | Formulador Técnico | Formula y carga documentos |

---

## Estructura del Proyecto

```
Sigiplan/
├── app/
│   ├── __init__.py          # Application factory
│   ├── models/              # Documentos MongoDB
│   ├── blueprints/          # Módulos de la aplicación
│   │   ├── public/          # Landing y dashboard
│   │   ├── auth/            # Login / logout
│   │   ├── admin/           # Gestión de usuarios y backups
│   │   ├── planning/        # Iniciativas y financiamiento
│   │   ├── formulation/     # Formulación técnica
│   │   ├── superadmin/      # Panel de plataforma
│   │   └── api/             # Endpoints REST
│   ├── templates/           # Vistas Jinja2
│   ├── static/              # CSS y archivos estáticos
│   └── utils/               # Decoradores y helpers
├── config.py                # Configuraciones (dev, test, prod)
├── run.py                   # Entrypoint
├── seed.py                  # Datos de demostración
├── requirements.txt
└── .env.example
```

---

## Roles y Permisos

```
SUPER_ADMIN            → Gestión global de la plataforma
  ENTITY_ADMIN         → Gestión de usuarios y configuración de la entidad
    PLANNING_DIRECTOR  → Crea, asigna y aprueba iniciativas
      FORMULATION_LEADER      → Coordina la formulación técnica
        TECHNICAL_FORMULATOR  → Carga documentos y formula proyectos
```

---

## Workflow de Iniciativas

```
DRAFT → IN_PROGRESS → UNDER_REVIEW → APPROVED → ARCHIVED
                                   ↘ REJECTED
```

Cada transición queda registrada en la **bitácora de auditoría** inmutable de la iniciativa.

---

## Configuración

| Variable | Descripción | Default |
|---|---|---|
| `FLASK_ENV` | Entorno (`dev`, `test`, `prod`) | `dev` |
| `SECRET_KEY` | Clave de sesión Flask | Valor dev inseguro |
| `MONGODB_DB` | Nombre de la base de datos | `sigiplan` |
| `MONGODB_HOST` | URI de conexión MongoDB | `mongodb://localhost:27017/sigiplan` |

Para producción, usar MongoDB Atlas: `mongodb+srv://usuario:password@cluster.mongodb.net/sigiplan`

---

## Para Agentes IA

Ver [CLAUDE.md](CLAUDE.md) para guía detallada de arquitectura, convenciones y cómo extender el proyecto.
