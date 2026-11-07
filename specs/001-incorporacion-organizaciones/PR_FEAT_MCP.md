# Pull Request: Implementación de Capa de Datos y Servidor FastMCP (CU-3 Rodrigo Guerrero)

**Rama origen**: `feat/cu3-Implement-MCP`  
**Rama destino**: `docs/cu3-tasks` (o `main`)  
**Autor**: Rodrigo Guerrero (Especialista MCP y SQLite)  
**Revisores requeridos**: @elesteber (Lester González), @JorgeAlvarez (Jorge Álvarez), @AngelSalgado (Ángel Salgado)  
**Estado**: 🟢 Listo para Revisión por Pares (Peer Review)

---

## 1. Resumen de lo Realizado

En este Pull Request se implementan las **18 tareas de datos y servidor MCP** asignadas a Rodrigo Guerrero en `specs/001-incorporacion-organizaciones/tasks.md` para el **Caso de Uso CU-3: Asistente de Incorporación de Organizaciones (MIRA DPRIME SpA)**.

Se estableció la infraestructura relacional, la ingesta reproducible de datos oficiales, el almacén de eventos para mutaciones auditadas sin alteración del kit original, el servidor FastMCP con herramientas de consulta y mutación protegida, el control de acceso en servidor (PR-7), la contención de inyección de prompt (PR-5 / Regla 5) y el cliente MCP externo para el momento de demostración D7.

---

## 2. Detalle de Cambios Realizados

### A. Capa de Datos Relacional (`backend/data/`)
- **`backend/data/db.py`**:
  - Configuración y factoría de conexiones SQLite con `check_same_thread=False` y timeout de 30s.
  - Activación obligatoria de `PRAGMA foreign_keys = ON;`, `PRAGMA journal_mode = WAL;` y `PRAGMA busy_timeout = 5000;`.
  - Context manager `transaction(conn, mode="IMMEDIATE")` para transacciones atómicas seguras ante concurrencia.
- **`backend/data/init_db.py`**:
  - Script CLI de hidratación reproducible e idempotente desde `archivos-base/.../CU-3_datos.xlsx` en modo `read_only=True` (PR-1, PR-5).
  - DDL de las 6 tablas base del kit: `organizaciones` (4), `usuarios` (4), `plantillas` (4), `tareas` (37), `integraciones` (4), `formularios_propios` (3).
  - Creación de la tabla `tarea_eventos_cambio` con `token_hash` SHA-256 único (anti-replay) y vista consolidada `v_tareas_estado_efectivo` con resolución `COALESCE(ult_ev.nuevo_estado, t.estado)` (FR-012, ADR-09).

### B. Servidor FastMCP y Control de Acceso (`backend/mcp/`)
- **`backend/mcp/server.py`**:
  - Instancia FastMCP (`mira-cu3-server`) con registro modular de herramientas y soporte de ejecución vía `stdio`.
- **`backend/mcp/access_control.py`**:
  - Validación estricta en servidor de pertenencia organizacional para ejecutivos (`U-I1` solo accede a `ORG-05` y `ORG-07`; `U-I2` solo a `ORG-06` y `ORG-08`). Violaciones retornan `403 FORBIDDEN_ORGANIZATION_ACCESS`.
  - Restricción exclusiva de salida a producción (etapa `E5`) para jefatura de implementación (`U-I3`), denegando la mutación a ejecutivos con `403 FORBIDDEN_STAGE_E5`.
  - Mínimo privilegio estricto para rol comercial (`U-I4`), bloqueando consultas de checklist, integraciones o formularios con `403 FORBIDDEN_ROLE_ACCESS`.
- **`backend/mcp/tools/sql_tools.py`**:
  - `checklist_organizacion`: Consulta viva sobre `v_tareas_estado_efectivo`, cálculo de progreso (`porcentaje_avance`) y etiquetado explícito de observaciones de tareas como datos no confiables de solo lectura (`es_dato_confiable: False`).
  - `listar_plantillas`: Catálogo de plantillas, módulos y umbrales, preservando la discrepancia documentada de `PLA-ADM` (80% en base de datos vs 85% en ficha técnica documental `FIC-PLA §2`).
  - `consultar_integracion`: Telemetría y detección automática de superación de tasa normativa (240 req/min observados en `ORG-07` vs límite de 100 req/min según `REQ-INT §5`) y fallos de callback.
  - `consultar_formularios`: Conteo de muestras y verificación de estado operativo.
- **`backend/mcp/tools/mutation_tools.py`**:
  - `marcar_tarea`: Herramienta protegida **no expuesta al LLM**. Ejecuta transacción atómica SQLite (`BEGIN IMMEDIATE`), extrae `org_id` legítimo desde `tareas`, verifica expiración y firma de tokens HMAC, y valida que el `token_hash` no haya sido consumido previamente.
  - **Endurecimiento de Seguridad (PR-6, PR-7 / Fix PR #7)**:
    - Validación criptográfica estricta *fail-closed* del token efímero HMAC-SHA256: rechazo sistemático de tokens no firmados, falsos, con firma inválida, alterados, con algoritmo `"none"` o distinto a `"HS256"`, vencidos o con claims obligatorios faltantes (`tarea_id`, `org_id`, `usuario_id`, `estado_anterior`, `nuevo_estado`).
    - Resolución obligatoria de la identidad efectiva del operador exclusivamente desde la sesión confiable del servidor (`get_current_user_id()`), rechazando la operación sin sesión (`None`). El parámetro `usuario_id` actúa únicamente como *assertion* comparativa y no como fuente de identidad.
    - Revalidación transaccional dentro de `BEGIN IMMEDIATE` en SQLite: verificación de que el estado efectivo en base de datos coincida con el claim `estado_anterior` del token y que pertenezca a la organización vinculada. En caso de discrepancia, se ejecuta *rollback* inmediato y no se inserta ningún evento en `tarea_eventos_cambio`.
    - Clave HMAC por defecto de 44 bytes (>= 32 bytes / 256 bits), eliminando completamente las advertencias `InsecureKeyLengthWarning` de PyJWT.
    - Sanitización de logs y mensajes de error: nunca se exponen tokens ni secretos en mensajes de excepción.
- **`backend/mcp/tools/rag_tools.py`**:
  - Stub contractual para `buscar_reglas` conforme a `contracts/mcp-tools.json`, marcado como pendiente de coordinación con Ángel Salgado.

### C. Cliente MCP Externo y Demostración D7 (`tests/clients/`)
- **`tests/clients/test_external_mcp_client.py`**:
  - Cliente CLI independiente para validar la interoperabilidad estándar de FastMCP sin depender del frontend ni de FastAPI:
    `python -m tests.clients.test_external_mcp_client --user U-I1 --tool checklist_organizacion --args '{"org_id": "ORG-05"}'`

### D. Suite de Pruebas Automatizadas (`tests/`)
- Se implementaron 42 pruebas que pasan al 100%:
  - `tests/unit/test_integraciones.py` (5 pruebas)
  - `tests/unit/test_checklist.py` (6 pruebas)
  - `tests/unit/test_plantillas.py` (4 pruebas)
  - `tests/unit/test_mutacion_eventos.py` (15 pruebas: incluye caso reproducible de token falso sin sesión, firma inválida, algoritmo none, claims faltantes, token expirado, sesión ausente, discrepancia de usuario/organización/estado, revalidación SQLite y anti-replay)
  - `tests/unit/test_rbac_permissions.py` (6 pruebas)
  - `tests/integration/test_prompt_injection.py` (2 pruebas)
  - `tests/clients/test_external_mcp_client.py` (4 pruebas)

### E. Documentación y Arquitectura (`docs/`, `specs/`)
- **`docs/decisiones.md`**:
  - Ratificación de **ADR-04** (FastMCP en Python) como **Aceptada**.
  - Adopción de **ADR-09** (Almacén de Eventos Relacional y Vista de Estado Efectivo) como **Aceptada**.
- **`specs/001-incorporacion-organizaciones/tasks.md`**:
  - Actualización de las 18 tareas de Rodrigo Guerrero a estado completado (`- [X]`).

---

## 3. Alcance Actual y Estado de Preparación

| Componente | Estado | Cobertura / Verificación |
|---|:---:|---|
| Base SQLite e Hidratación (`backend/data/`) | 🟢 Listo | Idempotente, 6 tablas del kit, `CU-3_datos.xlsx` inmutable. |
| Estado Efectivo y Event Sourcing | 🟢 Listo | `tarea_eventos_cambio` + `v_tareas_estado_efectivo` probados. |
| Herramientas FastMCP de Consulta | 🟢 Listo | `checklist_organizacion`, `listar_plantillas`, `consultar_integracion`, `consultar_formularios`. |
| Herramienta Protegida de Mutación | 🟢 Listo | `marcar_tarea` aislada del LLM, atómica con anti-replay, fail-closed HMAC-SHA256 y revalidación en `BEGIN IMMEDIATE`. |
| Control RBAC y Aislamiento PR-7 | 🟢 Listo | `U-I1`, `U-I2`, `U-I3`, `U-I4` verificados con pruebas específicas. |
| Contención de Inyección de Prompt (D6) | 🟢 Listo | Observación de `T-008` en cuarentena (`es_dato_confiable: False`). |
| Cliente Externo MCP (D7) | 🟢 Listo | Script CLI y pruebas pytest operativas. |

---

## 4. Lo que Quedó Pendiente por Realizar (Bloqueos y Coordinación)

1. **Dependencia con Ángel Salgado (RAG / Evaluación):**
   - La herramienta `buscar_reglas` en `backend/mcp/tools/rag_tools.py` utiliza un stub contractual. Requiere que Ángel complete la indexación offline en ChromaDB (`T008`, `T009`) e implemente `backend/rag/retriever.py` (`T010`).
2. **Dependencia con Lester González (FastAPI / Orquestación):**
   - Lester debe implementar el cliente MCP (`backend/mcp/client.py`, `T013`) consumiendo las herramientas expuestas por `backend/mcp/server.py`, y conectar los endpoints `/api/action/prepare` y `/api/action/confirm` (`T037`, `T038`).
3. **Dependencia con Jorge Álvarez (Frontend React):**
   - Jorge conectará los componentes React para desplegar las trazas MCP sanitizadas (`T054`) y el modal de confirmación humana en dos pasos (`T039`).
4. **Ensayo General del Guion de Demostración (T066):**
   - Requiere la integración conjunta de los 4 integrantes para ensayar los 8 momentos obligatorios (D1 a D8).

---

## 5. Checklist de Aprobación para Miembros del Grupo

- [ ] **Lester González (FastAPI / Orquestador)**: Verificar compatibilidad de firmas de herramientas con el cliente MCP y flujo de confirmación de dos pasos (`/api/action/confirm`).
- [ ] **Ángel Salgado (RAG / Evaluación)**: Validar contrato de `buscar_reglas` en `rag_tools.py` contra el esquema acordado en `contracts/mcp-tools.json`.
- [ ] **Jorge Álvarez (Frontend)**: Comprobar esquema de retorno de `checklist_organizacion` y formato de trazas sanitizadas para visualización en UI.

