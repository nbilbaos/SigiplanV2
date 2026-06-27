# ROADMAP — SIGIPLAN

Estado del desarrollo por módulo. Actualizar este archivo cada vez que se complete o inicie una funcionalidad.

**Leyenda**: ✅ Implementado · 🔄 En progreso · ⬜ Pendiente · ❌ Descartado

---

## Infraestructura Base

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | Application Factory con blueprints |
| ✅ | Modelos MongoDB (Entity, User, Initiative, FundingSource) |
| ✅ | Autenticación con Flask-Login + Bcrypt |
| ✅ | Decorador `@role_required` para control de acceso |
| ✅ | Sistema de auditoría embebido en Initiative |
| ✅ | Diseño base ("Terra Design") con sidebar por rol |
| ✅ | Script de seed con datos de demostración |
| ✅ | Configuración multi-entorno (dev / test / prod) |
| ✅ | Documentación para agentes (CLAUDE.md + README.md) |
| ✅ | ROADMAP como fuente de verdad del estado del desarrollo |

---

## Módulo: Auth

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | Login con email y contraseña |
| ✅ | Logout |
| ✅ | Redirección post-login al dashboard |
| ✅ | Actualización de `last_login` |
| ⬜ | Recuperación de contraseña por email |
| ⬜ | Bloqueo de cuenta tras N intentos fallidos |

---

## Módulo: Super Admin (`/superadmin`)

> **Alcance**: Administrador de la plataforma SaaS. Opera sobre TODAS las entidades.
> Puede crear/editar/desactivar entidades, asignar planes de suscripción, gestionar cualquier
> usuario del sistema y consultar logs globales. Es el único rol sin entidad asignada.

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | **Dashboard Global** — métricas de plataforma (entidades activas, usuarios, iniciativas por estado) |
| ✅ | **Listar Entidades** — tabla con plan, usuarios, iniciativas y estado de cada entidad |
| ✅ | **Crear Entidad** — registrar nueva entidad gubernamental con RUT y plan inicial |
| ✅ | **Editar Entidad** — modificar nombre, RUT, dirección y plan de suscripción |
| ✅ | **Activar / Desactivar Entidad** — bloquear o rehabilitar acceso de toda una entidad |
| ✅ | **Cambio de Plan** — asignar Standard / Premium / Enterprise |
| ✅ | **Listar Usuarios Globales** — todos los usuarios de todas las entidades con filtros |
| ✅ | **Crear Usuario (cualquier rol)** — incluye el primer ENTITY_ADMIN de cada entidad |
| ✅ | **Editar Usuario** — cambiar datos, rol, entidad y estado activo |
| ✅ | **Activar / Desactivar Usuario** — desde el panel global |
| ✅ | **Logs de Auditoría Global** — todas las acciones sobre iniciativas, filtrable por entidad, acción y fecha |
| ✅ | **Detalle de Entidad** — vista con usuarios, iniciativas, fuentes y actividad reciente de una entidad específica |
| ✅ | **Estadísticas de Plataforma** — resumen ejecutivo: presupuesto formulado total, iniciativas aprobadas por entidad |
| ⬜ | **Configuración de Plataforma** — parámetros globales del sistema |

---

## Módulo: Entity Admin (`/admin`)

> **Alcance**: Administrador LOCAL de una sola entidad. Solo ve y opera sobre los datos
> de SU entidad. No puede crear entidades, cambiar planes ni ver datos de otras entidades.
> Puede crear usuarios con roles PLANNING_DIRECTOR, FORMULATION_LEADER y TECHNICAL_FORMULATOR
> (no puede crear SUPER_ADMIN ni otros ENTITY_ADMIN — eso es responsabilidad del Super Admin).

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | **Dashboard de Entidad** — métricas locales: usuarios activos, iniciativas por estado, fuentes de financiamiento disponibles |
| ✅ | **Listar Usuarios** — usuarios de SU entidad con rol y estado |
| ✅ | **Crear Usuario** — roles permitidos: PLANNING_DIRECTOR, FORMULATION_LEADER, TECHNICAL_FORMULATOR |
| ✅ | **Editar Usuario** — modificar nombre, rol (dentro del alcance), contraseña y estado |
| ✅ | **Desactivar / Reactivar Usuario** — solo usuarios de su entidad |
| ✅ | **Resetear Contraseña** — incluido en la edición de usuario (campo opcional) |
| ✅ | **Listar Fuentes de Financiamiento** — con presupuesto total, asignado, disponible y barra de uso |
| ✅ | **Crear Fuente de Financiamiento** — registrar nueva fuente con código único y presupuesto total |
| ✅ | **Editar Fuente de Financiamiento** — modificar nombre, código y presupuesto |
| ✅ | **Activar / Desactivar Fuente** — bloquear uso de una fuente sin eliminarla |
| ✅ | **Ver Perfil de Entidad** — nombre, RUT, plan activo (solo lectura — no puede editar nombre ni RUT) |
| ✅ | **Editar Dirección de Entidad** — único campo editable por el Entity Admin |
| ✅ | **Logs de Actividad de su Entidad** — vista filtrada por acción y fechas, solo sus iniciativas |
| ✅ | **Exportar Datos** — descarga CSV de las iniciativas de su entidad |

---

## Módulo: Planning (`/planning`)

> **Alcance**: PLANNING_DIRECTOR gestiona la cartera de iniciativas. FORMULATION_LEADER y
> TECHNICAL_FORMULATOR tienen acceso de lectura y formulación. Las fuentes de financiamiento
> son creadas por el ENTITY_ADMIN; el PLANNING_DIRECTOR solo las asigna a iniciativas.

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | **Dashboard de Planificación** — métricas de cartera por estado e iniciativas recientes (servido en "Inicio") |
| ✅ | **Listar Iniciativas** — tabla con chips de estado, búsqueda por código/título y conteos |
| ✅ | **Crear Iniciativa** — formulario completo: código, título, descripción, responsables, fuentes, costo estimado, plazo |
| ✅ | **Detalle de Iniciativa** — ficha completa con bitácora de auditoría en línea de tiempo |
| ✅ | **Editar Iniciativa** — modificar campos en estados DRAFT, IN_PROGRESS y REJECTED |
| ✅ | **Aprobar Iniciativa** — transición UNDER_REVIEW → APPROVED con comentario |
| ✅ | **Rechazar Iniciativa** — transición UNDER_REVIEW → REJECTED con observaciones obligatorias |
| ✅ | **Archivar Iniciativa** — transición APPROVED → ARCHIVED |
| ✅ | **Borrado Lógico** — papelera (is_deleted=True) con restauración |
| ✅ | **Asignar Responsables** — director, coordinador y formuladores desde el formulario de iniciativa |
| ✅ | **Ver y Asignar Fuentes de Financiamiento** — selección de fuentes existentes y vista de uso/disponibilidad |
| ✅ | **Organigrama** — visualización jerárquica de usuarios de la entidad |
| ✅ | **Exportar Cartera** — exportación CSV y reporte ejecutivo imprimible |

---

## Módulo: Formulation (`/formulation`)

> **Alcance**: FORMULATION_LEADER coordina el equipo técnico. TECHNICAL_FORMULATOR
> solo ve y trabaja en las iniciativas que tiene asignadas.

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | **Dashboard de Formulación** — "Mesa de Formulación": iniciativas agrupadas por estado con métricas |
| ✅ | **Ver Iniciativas** — FORMULATION_LEADER ve todas; TECHNICAL_FORMULATOR solo las asignadas |
| ✅ | **Carga de Documentos** — subir adjuntos (PDF, Office, imágenes, ZIP) hasta 16 MB |
| ✅ | **Gestión de Adjuntos** — listar, descargar y eliminar archivos cargados |
| ✅ | **Formulación Técnica** — editar título, descripción y costo en estados editables |
| ✅ | **Asignar Formuladores** — el Coordinador asigna TECHNICAL_FORMULATOR a la iniciativa |
| ✅ | **Enviar a Revisión** — transición IN_PROGRESS → UNDER_REVIEW con comentario obligatorio |
| ✅ | **Retomar tras Rechazo** — transición REJECTED → IN_PROGRESS para corregir y reenviar |
| ✅ | **Ver Observaciones de Rechazo** — panel con el motivo y autor cuando status = REJECTED |

---

## Módulo: Public / Perfil

> **Alcance**: Funcionalidades transversales disponibles para todos los roles autenticados.

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | Landing page pública |
| ✅ | Dashboard de inicio con métricas según rol |
| ✅ | **Página de Perfil** — ver datos, editar nombre y cambiar contraseña propia (con validaciones) |
| ⬜ | **Notificaciones** — alertas de cambios de estado en iniciativas asignadas |

---

## Módulo: API (`/api`)

> **Alcance**: Endpoints JSON de soporte para componentes frontend (gráficos, selectores dinámicos).

| Estado | Funcionalidad |
|--------|--------------|
| ✅ | `GET /api/org-data` — nodos y aristas reales de la jerarquía de usuarios de la entidad |
| ✅ | `GET /api/initiatives` — listado de iniciativas en JSON (scoped por rol, filtro por estado) |
| ✅ | `GET /api/funding-sources` — fuentes de la entidad con uso y disponibilidad |
| ✅ | `GET /api/dashboard-metrics` — métricas del dashboard según rol (incluye SUPER_ADMIN global) |
| ✅ | `GET /api/executive-metrics` — métricas ejecutivas de cartera, riesgo y presupuesto |

---

## Orden de implementación

1. ✅ **Super Admin** — Dashboard · Entidades · Usuarios · Logs de Auditoría
2. ✅ **Entity Admin** — Dashboard · Usuarios · Fuentes de Financiamiento · Perfil de Entidad · Logs locales
3. ✅ **Planning** — Cartera · Crear/Detalle/Editar Iniciativas · Flujo de Estados · Asignar Responsables · Financiamiento · Organigrama
4. ✅ **Formulation** — Mesa de Formulación · Ficha Técnica · Adjuntos · Asignar Formuladores · Enviar a Revisión · Observaciones de Rechazo
5. ✅ **Public** — Página de Perfil (datos personales + cambio de contraseña)
6. ✅ **API** — org-data · initiatives · funding-sources · dashboard-metrics
