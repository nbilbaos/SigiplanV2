# AGENTS.md — Guía para Agentes IA

Contexto operativo para agentes que trabajen en SIGIPLAN. Leer este archivo antes de modificar código.

> Antes de implementar funcionalidades, revisar `ROADMAP.md`. Si se completa una funcionalidad marcada como pendiente, actualizar su estado.

---

## Descripción del proyecto

SIGIPLAN es una plataforma web fullstack para la gestión de iniciativas de inversión pública de entidades gubernamentales chilenas.

- Dominio: inversión pública, planificación municipal, formulación técnica de proyectos.
- Usuarios objetivo: funcionarios de entidades gubernamentales con distintos niveles de responsabilidad.
- Stack: Python/Flask + MongoDB + Jinja2 templates.
- Estilo visual: “Fiscal Modern”, sobrio, institucional y data-forward.

---

## Comandos esenciales

```bash
pip install -r requirements.txt
python seed.py
python run.py
```

Para crear datos demo en un despliegue existente sin borrar información:

```bash
DEMO_PASSWORD='<contraseña-temporal>' python scripts/ensure_demo_data.py
```

`seed.py` limpia la base de datos y debe usarse solo en desarrollo. En producción/staging usar `scripts/ensure_demo_data.py`.

Variables principales:

```bash
FLASK_ENV=dev | test | prod
MONGODB_DB=sigiplan
MONGODB_HOST=mongodb://localhost:27018/sigiplan
SECRET_KEY=<obligatoria en producción>
SECURE_COOKIES=true
```

Credenciales demo de desarrollo, todas con `password123`:

| Email | Rol |
|---|---|
| superadmin@sigiplan.cl | SUPER_ADMIN |
| admin@santiago.cl | ENTITY_ADMIN |
| director@santiago.cl | PLANNING_DIRECTOR |
| coordinador@santiago.cl | FORMULATION_LEADER |
| formulador@santiago.cl | TECHNICAL_FORMULATOR |

---

## Arquitectura

Flask con Application Factory en `app/__init__.py` y blueprints por módulo. Patrón MVC simple: modelos MongoEngine, vistas Jinja2 y controladores en `routes.py`.

| Blueprint | Prefijo URL | Alcance |
|---|---|---|
| `public` | `/` | landing, dashboard y perfil |
| `auth` | `/auth` | login/logout |
| `admin` | `/admin` | administración de entidad |
| `planning` | `/planning` | cartera, revisión, reportes y financiamiento |
| `formulation` | `/formulation` | mesa técnica y adjuntos |
| `superadmin` | `/superadmin` | operación SaaS global |
| `api` | `/api` | endpoints JSON |

Estructura relevante:

```text
app/
├── __init__.py
├── models/
├── blueprints/
├── templates/
├── static/css/style.css
└── utils/
```

---

## Modelos principales

- `Entity`: tenant gubernamental principal.
- `User`: usuario autenticado; `SUPER_ADMIN` no tiene entidad, todos los demás roles sí.
- `Initiative`: documento central de cartera, con responsables, fuentes, estado, adjuntos, bitácora y borrado lógico.
- `FundingSource`: fuente de financiamiento con presupuesto total/asignado/disponible.

Reglas importantes:

- Nunca borrar físicamente una iniciativa; usar `is_deleted=True`.
- Registrar transiciones relevantes con `initiative.log_action(...)`.
- Usar `user.set_password(raw)`; nunca asignar `password_hash` directamente.
- Fechas en UTC con `datetime.utcnow()`.
- En queries multi-tenant, filtrar por `entity=current_user.entity` salvo `SUPER_ADMIN`.

---

## Roles y permisos

```text
SUPER_ADMIN
  └── ENTITY_ADMIN
        ├── PLANNING_DIRECTOR
        │     └── FORMULATION_LEADER
        │           └── TECHNICAL_FORMULATOR
```

Usar siempre:

```python
@blueprint.route('/ruta')
@login_required
@role_required('ROL_PERMITIDO')
def vista():
    ...
```

`@role_required` vive en `app/utils/decorators.py`.

---

## Workflow de iniciativas

```text
DRAFT → IN_PROGRESS → UNDER_REVIEW → APPROVED → ARCHIVED
                                ↘ REJECTED → IN_PROGRESS
```

Acciones de auditoría válidas:

```text
CREATE, UPDATE, SUBMIT_FOR_REVIEW, APPROVE, REJECT, SOFT_DELETE, RESTORE
```

---

## Seguridad y formularios

- La app usa `Flask-WTF` y CSRF global.
- Todo `<form method="POST">` debe incluir:

```jinja2
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
```

- El login valida redirecciones `next` para evitar open redirect.
- En producción, `SECRET_KEY` es obligatoria.
- Cookies de sesión: `Secure`, `HttpOnly`, `SameSite=Lax`.

---

## Adjuntos y archivos

- Los adjuntos se guardan fuera de `app/static`, en `UPLOAD_FOLDER`.
- En Docker producción el volumen monta en `/app/uploads`.
- Los archivos solo deben descargarse por rutas autenticadas.
- Usar `secure_filename()` y lista blanca de extensiones.

---

## Diseño visual

Todos los estilos deben vivir en `app/static/css/style.css`.

Mantener nombres de variables semánticas:

- `--color-primary`
- `--color-bg-base`
- `--color-bg-card`
- `--color-text-muted`
- `--color-border`
- `--color-tertiary`
- `--sidebar-bg`
- `--sidebar-accent`

El sistema UI actual incluye componentes reutilizables:

- `metric-card`
- `status-pill`
- `data-table`
- `timeline`
- `action-panel`
- `empty-state`
- `section-header`
- `risk-banner`
- `kanban-board`

Evitar crear estilos inline nuevos si una clase reutilizable puede resolverlo.

`base.html` contiene un bloque pequeño de CSS crítico inline para evitar FOUC
(destello de HTML sin estilos) antes de que cargue `style.css`. No eliminarlo
sin reemplazarlo por otra estrategia equivalente. El CSS local se carga con
query string de versión (`style.css?v=...`); si cambias `style.css` y el
navegador debe refrescar inmediatamente, actualizar esa versión.

---

## Infraestructura

- Producción usa Docker Compose con app + MongoDB.
- Reverse proxy independiente recomendado: Caddy con HTTPS automático.
- MongoDB no debe exponerse a internet.
- Uploads y Mongo viven en volúmenes Docker.
- `Claves*.txt`, `.env*`, llaves y credenciales no deben entrar al repo ni a la imagen.

---

## Convenciones para nuevas funcionalidades

1. Revisar `ROADMAP.md`.
2. Agregar rutas en el blueprint existente cuando sea posible.
3. Crear templates bajo `app/templates/<modulo>/`.
4. Reutilizar helpers de `app/utils/` antes de duplicar lógica.
5. Agregar navegación en `base.html` si la pantalla debe ser accesible desde sidebar.
6. Actualizar `ROADMAP.md` si una funcionalidad pendiente queda implementada.
