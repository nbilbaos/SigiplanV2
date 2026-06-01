# CLAUDE.md — Guía para Agentes IA

Este archivo proporciona contexto completo del proyecto SIGIPLAN para agentes de IA (Claude Code y similares). Léelo antes de realizar cualquier cambio.

> **IMPORTANTE PARA AGENTES**: Antes de implementar cualquier funcionalidad, leer [`ROADMAP.md`](ROADMAP.md) para conocer el estado actual del desarrollo (qué está hecho, qué está en progreso, qué sigue). Al completar una funcionalidad, actualizar su estado en ROADMAP.md de `⬜ Pendiente` a `✅ Implementado`.

---

## Descripción del Proyecto

**SIGIPLAN** es una plataforma web fullstack para la **gestión de iniciativas de inversión pública** de entidades gubernamentales chilenas (municipalidades, ministerios, servicios públicos).

- **Dominio**: Inversión pública, planificación municipal, formulación técnica de proyectos
- **Usuarios objetivo**: Funcionarios de entidades gubernamentales con distintos niveles de responsabilidad
- **Stack**: Python/Flask + MongoDB + Jinja2 templates
- **Estado**: MVP funcional, en expansión activa de funcionalidades

---

## Comandos Esenciales

```bash
# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos con datos de demostración
python seed.py

# Iniciar servidor de desarrollo (puerto 5000)
python run.py

# Variables de entorno requeridas (ver .env.example)
# FLASK_ENV=dev | test | prod
# MONGODB_DB=sigiplan
# MONGODB_HOST=mongodb://localhost:27018/sigiplan
```

**Credenciales de demo** (todas con `password123`):
| Email | Rol |
|---|---|
| superadmin@sigiplan.cl | SUPER_ADMIN |
| admin@santiago.cl | ENTITY_ADMIN |
| director@santiago.cl | PLANNING_DIRECTOR |
| coordinador@santiago.cl | FORMULATION_LEADER |
| formulador@santiago.cl | TECHNICAL_FORMULATOR |

---

## Arquitectura

### Patrón General
Flask con **Application Factory** (`app/__init__.py`) y **Blueprints** por módulo funcional. Patrón MVC: modelos MongoEngine, vistas Jinja2, controladores en `routes.py`.

### Blueprints y sus URLs

| Blueprint | Prefijo URL | Roles con acceso |
|---|---|---|
| `public` | `/` | Todos (autenticados) |
| `auth` | `/auth` | Público |
| `admin` | `/admin` | ENTITY_ADMIN |
| `planning` | `/planning` | PLANNING_DIRECTOR, FORMULATION_LEADER, TECHNICAL_FORMULATOR |
| `formulation` | `/formulation` | FORMULATION_LEADER, TECHNICAL_FORMULATOR |
| `superadmin` | `/superadmin` | SUPER_ADMIN |
| `api` | `/api` | Varía por endpoint |

### Estructura de archivos
```
app/
├── __init__.py              # create_app() factory + extensiones globales (login_manager, bcrypt)
├── models/                  # Documentos MongoEngine
│   ├── entity.py            # Entity, PaymentRecord
│   ├── user.py              # User (con UserMixin para Flask-Login)
│   ├── initiative.py        # Initiative, FileAttachment, AuditTrailEntry
│   └── funding.py           # FundingSource
├── blueprints/
│   ├── <nombre>/
│   │   ├── __init__.py      # Define el Blueprint object
│   │   └── routes.py        # Vistas y lógica del módulo
├── templates/               # Jinja2 — base.html + subdirectorios por blueprint
├── static/
│   ├── css/style.css        # Único archivo CSS ("Fiscal Modern" design system)
│   └── uploads/             # Archivos subidos (creado automáticamente)
└── utils/
    └── decorators.py        # @role_required(*roles)
config.py                    # DevelopmentConfig, TestingConfig, ProductionConfig
run.py                       # Entrypoint
seed.py                      # Script de inicialización con datos demo
```

---

## Modelos de Datos

### Entity (`entities`)
Entidad gubernamental. Es el tenant principal del sistema.
```python
name: str (único)           # "Ilustre Municipalidad de Santiago"
tax_id: str (único)         # RUT: "69.070.300-K"
address: str
is_active: bool
subscription_plan: str      # "Standard" | "Premium" | "Enterprise"
payment_history: [PaymentRecord]
```

### User (`users`)
```python
email: str (único)
password_hash: str          # bcrypt — usar user.set_password() y user.check_password()
first_name / last_name: str
role: str                   # Ver jerarquía de roles abajo
entity: → Entity            # None solo para SUPER_ADMIN
is_active: bool
last_login: datetime
```
Propiedades útiles: `user.full_name`, `user.get_role_display()`

### Initiative (`initiatives`)
Documento central del sistema.
```python
entity: → Entity
code: str (único por entity)    # "INIT-CESFAM-01"
title / description: str
planning_director: → User
formulation_leader: → User
assigned_formulators: [→ User]
funding_sources: [→ FundingSource]
estimated_cost: float
status: str                     # Ver workflow de estados abajo
deadline: datetime
attachments: [FileAttachment]
audit_trail: [AuditTrailEntry]
is_deleted: bool                # Borrado lógico — NUNCA borrar físicamente
```
Métodos útiles: `initiative.log_action(user, action, details)`, `get_status_display()`, `get_status_color()`

### FundingSource (`funding_sources`)
```python
entity: → Entity
name / code: str
total_budget / allocated_budget: float
is_active: bool
# Propiedad calculada:
remaining_budget = total_budget - allocated_budget
```

---

## Jerarquía de Roles

```
SUPER_ADMIN           — Administrador global de la plataforma (sin entity)
  └── ENTITY_ADMIN    — Administrador local de una entidad
        ├── PLANNING_DIRECTOR    — Crea y supervisa iniciativas
        │     └── FORMULATION_LEADER    — Coordina la formulación técnica
        │               └── TECHNICAL_FORMULATOR    — Formula y carga documentos
```

**Regla importante**: `SUPER_ADMIN` no tiene `entity`. Todos los demás roles sí tienen `entity` asignada. Siempre verificar `current_user.role` antes de operar sobre `current_user.entity`.

---

## Workflow de Iniciativas

```
DRAFT → IN_PROGRESS → UNDER_REVIEW → APPROVED
                                   ↘ REJECTED → (vuelve a IN_PROGRESS)
APPROVED → ARCHIVED
```

Cada transición de estado debe registrarse en `audit_trail` con `initiative.log_action(user, "ACCION", "detalle")`.

Acciones de auditoría válidas: `CREATE`, `UPDATE`, `SUBMIT_FOR_REVIEW`, `APPROVE`, `REJECT`, `SOFT_DELETE`, `RESTORE`

---

## Control de Acceso

Siempre combinar `@login_required` con `@role_required(...)` en este orden:
```python
@blueprint.route('/ruta')
@login_required
@role_required('PLANNING_DIRECTOR', 'ENTITY_ADMIN')
def vista():
    ...
```

`@role_required` está en `app/utils/decorators.py`. Si el rol no tiene acceso, redirige a `public.dashboard` con un flash de advertencia.

---

## Extensiones Globales

Las extensiones `login_manager` y `bcrypt` se instancian en `app/__init__.py` a nivel de módulo. Para usarlas dentro de modelos o vistas, importar así:
```python
from app import bcrypt
```
No usar `current_app.extensions` — importar directamente.

---

## Convenciones de Código

- **Templates**: Heredar siempre de `base.html` con `{% extends 'base.html' %}`. El sidebar se genera dinámicamente según `current_user.role`.
- **CSS**: Todas las modificaciones de estilo van en `app/static/css/style.css`. Usar las variables CSS definidas en `:root` (`--color-primary`, `--color-bg-base`, `--color-bg-card`, `--color-text-muted`, `--color-tertiary`, etc.).
- **Rutas de API**: Devolver `jsonify()`. Autenticar con `@login_required` + `@role_required`.
- **Borrado de Iniciativas**: Solo borrado lógico (`is_deleted=True`). Nunca `initiative.delete()`.
- **Contraseñas**: Siempre `user.set_password(raw)` — nunca asignar `password_hash` directamente.
- **Fechas**: Usar `datetime.utcnow()` consistentemente. Los modelos usan UTC.
- **Queries de Entidad**: Siempre filtrar por `entity=current_user.entity` para aislar datos entre tenants.

---

## Añadir una Nueva Funcionalidad

1. Si es una página nueva en un blueprint existente: agregar la ruta en `app/blueprints/<nombre>/routes.py`.
2. Si es un módulo completamente nuevo: crear `app/blueprints/<nombre>/__init__.py` y `routes.py`, luego registrar en `app/__init__.py`.
3. Crear el template en `app/templates/<nombre>/`.
4. Si necesita modelo de datos nuevo: crear en `app/models/` e importar en `seed.py` si requiere datos demo.
5. Agregar la entrada de menú en `app/templates/base.html` dentro de la sección de navegación del sidebar.

---

## Diseño Visual ("Fiscal Modern")

Panel de control institucional, sobrio y data-forward para inversión pública: **riel de comando oscuro** (sidebar) + **lienzo papel claro** con tarjetas blancas.

- **Paleta**: Primario pino-teal (`--color-primary: #0E6E5B`), lienzo papel (`--color-bg-base: #EEF1EE`), tarjetas blancas (`--color-bg-card: #fff`), riel oscuro (`--sidebar-bg: #112019`) con acento teal brillante (`--sidebar-accent: #34D9AC`), oro refinado (`--color-tertiary: #9A6B12`).
- **Tipografía**: **Fraunces** (serif óptica, `--font-headlines`) para titulares y marca; **Hanken Grotesk** (`--font-body`) para UI/datos, con cifras tabulares (`font-feature-settings: 'tnum'`) para los montos.
- **Símbolo de marca**: 🌱 (semilla)
- **Todos los estilos** están en un único archivo: `app/static/css/style.css`. Las plantillas usan los **nombres de variables CSS semánticas** en estilos inline (`var(--color-primary)`, `var(--color-bg-base)`, `var(--color-text-muted)`, `var(--color-border)`, etc.), por lo que el sistema se reestiliza redefiniendo `:root` — **conservar los nombres de variables** al cambiar el tema.

---

## Notas de Infraestructura

- MongoDB corre localmente en el **puerto 27018** (no el estándar 27017) en el entorno de desarrollo.
- `MAX_CONTENT_LENGTH = 16 MB` para uploads.
- Los archivos subidos se guardan en `app/static/uploads/` (creado automáticamente al iniciar la app).
- En producción, `SECRET_KEY` debe venir obligatoriamente de variable de entorno.
