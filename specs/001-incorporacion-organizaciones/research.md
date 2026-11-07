# Research and Technical Decisions: MIRA CU-3 Onboarding Assistant

**Feature**: `001-incorporacion-organizaciones`
**Date**: 2026-11-07
**Status**: Completed & Consistency Verified

---

## 1. Decisiones de Arquitectura y Comunicación de Componentes

### Decisión 1.1: Flujo de Orquestación e Integración de Protocolos
- **Decisión:** El frontend (React + Vite) se comunica exclusivamente con la API Backend (FastAPI). FastAPI actúa como orquestador central: consume el Servidor MCP (`FastMCP`) como cliente MCP, gestiona las llamadas a la API de Google Gemini Flash y conecta con el almacén vectorial ChromaDB a través de la herramienta MCP `buscar_reglas`.
- **Catálogo de Herramientas Expuestas al LLM:**
  - Gemini Flash recibe **únicamente herramientas de consulta (lectura)**: `buscar_reglas`, `checklist_organizacion`, `listar_plantillas`, `consultar_integracion`, `consultar_formularios`.
  - La herramienta `marcar_tarea` es una **herramienta protegida de mutación**, que **NUNCA** se declara en la lista de tools expuestas a Gemini. El modelo jamás puede autoinvocar mutaciones de estado en la base de datos (PR-1, PR-6).
- **Flujo de Ejecución:**
  1. El usuario interactúa con la interfaz web en React enviando su consulta junto con el token de sesión demo en `Authorization: Bearer <session_token>`.
  2. FastAPI valida criptográficamente la sesión en el servidor y recupera la identidad del operador (`U-I1` Sofía Tapia, `U-I2` Diego Fuentes, `U-I3` Carolina Vera, `U-I4` Pablo Reyes) y sus permisos sobre organizaciones.
  3. FastAPI envía la consulta junto con las herramientas de lectura y el System Prompt a Gemini Flash.
  4. Si Gemini detecta intención de cambiar estado o el usuario solicita una mutación, el asistente sugiere y prepara la acción (`ActionProposal`) o el cliente invoca `/api/action/prepare`.
  5. Tras la confirmación interactiva humana en el frontend (Paso 2), el backend invoca internamente la ejecución de `marcar_tarea` en el servidor MCP enviando el `token_confirmacion` y el contexto autenticado.
  6. FastAPI entrega a React una respuesta estructurada con: texto final, citas documentales estructuradas con `chunk_id`, trazas MCP sanitizadas y estado de evidencia.

---

## 2. Persistencia Inmutable y Registro de Eventos (Event Sourcing Relacional)

### Decisión 2.1: Esquema de Actualizaciones sin Modificación del Kit Original
- **Problema:** La cátedra prohíbe taxativamente modificar o borrar los registros cargados desde el archivo original `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/datos/CU-3_datos.xlsx`.
- **Decisión:** Implementar un patrón de **Event Log Relacional** en SQLite (`backend/data/mira_cu3.db`):
  - Las tablas del Excel (`organizaciones`, `usuarios`, `plantillas`, `tareas`, `integraciones`, `formularios_propios`) se importan como tablas de solo lectura (`READ-ONLY SNAPSHOT`).
  - Se añade la tabla `tarea_eventos_cambio`:
    ```sql
    CREATE TABLE tarea_eventos_cambio (
        evento_id INTEGER PRIMARY KEY AUTOINCREMENT,
        tarea_id TEXT NOT NULL,
        org_id TEXT NOT NULL,
        estado_anterior TEXT NOT NULL CHECK (estado_anterior IN ('pendiente', 'en_curso', 'completada')),
        nuevo_estado TEXT NOT NULL CHECK (nuevo_estado IN ('pendiente', 'en_curso', 'completada')),
        usuario_id TEXT NOT NULL,
        rol_usuario TEXT NOT NULL CHECK (rol_usuario IN ('ejecutivo_implementacion', 'jefe_implementacion', 'comercial')),
        justificacion TEXT,
        token_hash TEXT NOT NULL UNIQUE,
        fecha_cambio DATETIME NOT NULL,
        FOREIGN KEY (tarea_id) REFERENCES tareas(tarea_id),
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
    );
    ```
  - Se define la vista SQL `v_tareas_estado_efectivo` que resuelve el estado actual mediante un `COALESCE` entre el último `nuevo_estado` de `tarea_eventos_cambio` y el `estado` original de la tabla `tareas`:
    ```sql
    CREATE VIEW v_tareas_estado_efectivo AS
    SELECT
        t.tarea_id,
        t.org_id,
        t.etapa,
        t.descripcion,
        t.obligatoria,
        COALESCE(ult_ev.nuevo_estado, t.estado) AS estado,
        t.responsable,
        t.fecha_limite,
        t.observacion,
        ult_ev.fecha_cambio AS fecha_ultima_actualizacion,
        ult_ev.usuario_id AS actualizado_por
    FROM tareas t
    LEFT JOIN (
        SELECT e1.tarea_id, e1.nuevo_estado, e1.fecha_cambio, e1.usuario_id
        FROM tarea_eventos_cambio e1
        INNER JOIN (
            SELECT tarea_id, MAX(evento_id) AS max_id
            FROM tarea_eventos_cambio
            GROUP BY tarea_id
        ) e2 ON e1.evento_id = e2.max_id
    ) ult_ev ON t.tarea_id = ult_ev.tarea_id;
    ```
- **Rationale:** Permite que las herramientas MCP de lectura consulten siempre `v_tareas_estado_efectivo` reflejando el estado en tiempo real, mientras la tabla `tareas` original permanece intacta para auditoría y evaluación académica.

---

## 3. Mecanismo de Sesión Simulada y Control de Acceso (PR-7)

### Decisión 3.1: Sesión de Demostración Firmada y Validación en Servidor
- **Problema:** Enviar únicamente un header abierto como `X-Simulated-User-ID` sin firma no constituye una autenticación confiable, y confiar en afirmaciones de identidad generadas por el LLM violaría PR-7.
- **Decisión:** Implementar una **Sesión de Demostración Administrada por el Backend**:
  - El frontend React incorpora un selector visual en su barra superior con los 4 usuarios reales del kit (`U-I1` Sofía Tapia, `U-I2` Diego Fuentes, `U-I3` Carolina Vera, `U-I4` Pablo Reyes).
  - Al cambiar de usuario, el frontend llama a `POST /api/session/switch`, y el backend emite un token firmado con HMAC-SHA256 (`session_token`) que codifica el `usuario_id`, rol y expiración.
  - El frontend envía dicho token en el header `Authorization: Bearer <session_token>` (o `X-MIRA-Demo-Session`).
  - FastAPI valida la firma criptográfica en el middleware o dependencia inyectable (`get_current_user_context`).
  - **Aviso explícito en documentación:** Se declara que este mecanismo es una **simulación de identidad para demostración y evaluación académica**, sin pretender ser un sistema de autenticación empresarial en producción (como SAML/OIDC).
  - **Inyección de contexto a FastMCP:** El servidor FastMCP recibe y valida el contexto del usuario directamente desde el servidor backend; las herramientas MCP nunca aceptan el ID del usuario desde los argumentos libres propuestos por el LLM.
  - **Matriz de Control de Acceso en Servidor:**
    - `ejecutivo_implementacion`: Solo puede consultar y mutar organizaciones donde `organizaciones.ejecutivo_id == usuario_id` (`U-I1` $\rightarrow$ `ORG-05`, `ORG-07`; `U-I2` $\rightarrow$ `ORG-06`, `ORG-08`). Acceso a otras organizaciones genera `403 FORBIDDEN_ORGANIZATION_ACCESS`.
    - `jefe_implementacion` (`U-I3`): Posee lectura global sobre todas las organizaciones y es la única autorizada para confirmar la salida a producción (etapa `E5`).
    - `comercial` (`U-I4`): Mínimo privilegio estricto; denegado el acceso a tareas y datos operativos de organizaciones. Solo puede consultar normativas generales y catálogo de plantillas.

---

## 4. Pipeline RAG, Metadatos Unificados y Trazabilidad

### Decisión 4.1: Indexación y Búsqueda Desacoplada con ChromaDB
- **Motor Vectorial:** ChromaDB en modo cliente local persistente (`backend/rag/chroma_db`).
- **Modelo de Embeddings:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ejecutado localmente en CPU (384 dimensiones).
- **Corpus Oficial:** Limitado exclusivamente a los 5 documentos del CU-3 en `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus/`:
  1. `GUI-INC_v1_derogada.md`
  2. `GUI-INC_v2_vigente.md`
  3. `POL-FOR_formularios_propios.md`
  4. `FIC-PLA_fichas_plantillas.md`
  5. `REQ-INT_requisitos_integracion.md`
- **Estructura de Metadatos Obligatoria (Unificada con ChromaDB, MCP y REST):**
  - `chunk_id`: Identificador determinista (ej. `GUI-INC-V2-SEC3-P1`).
  - `doc_code`: Código del documento (`GUI-INC`, `FIC-PLA`, `REQ-INT`, `POL-FOR`).
  - `doc_title`: Título formal.
  - `section`: Sección exacta (ej. `§3.2`).
  - `version`: Cadena de versión (`v1.0`, `v2.0`).
  - `status`: Cadena (`vigente` o `derogada`).
- **Herramienta FastMCP `buscar_reglas`:**
  - Entrada: `query` (cadena), `top_k` (entero, por defecto 4), `filtro_vigencia` (opcional: `vigente`, `todas`).
  - Retorna lista estructurada de fragmentos incluyendo obligatoriamente `chunk_id` para garantizar que toda cita en la API REST pueda ser validada contra el fragmento real devuelto (PR-2).

---

## 5. Protocolo de Escrituras y Mitigación de Concurrencia (PR-6)

### Decisión 5.1: Flujo en Dos Fases (Prepare-and-Confirm) con Transacción Atómica
- **Fase 1 (Preparación):**
  - Endpoint `POST /api/action/prepare`.
  - Recibe: `tarea_id`, `nuevo_estado`, `justificacion`.
  - Valida en SQLite: existencia de la tarea, que el usuario en sesión sea el responsable o ejecutivo asignado a la organización, que no sea etapa `E5` (reservada a jefe), y que la transición sea válida (`pendiente` o `en_curso` $\rightarrow$ `completada`).
  - Genera un `confirmation_token` efímero firmado con HMAC-SHA256 (TTL de 5 minutos), codificando: `tarea_id`, `org_id`, `nuevo_estado`, `usuario_id`, `rol_usuario`, `jti` y `exp`.
  - El backend calcula el hash SHA-256 del token (`token_hash`) para control de uso único.
  - Retorna payload estructurado para que el frontend despliegue el modal interactivo de confirmación humana (PR-1, PR-6).
- **Fase 2 (Ejecución):**
  - Endpoint `POST /api/action/confirm`.
  - Recibe: `confirmation_token`.
  - Verifica firma criptográfica, expiración y correspondencia con el usuario activo en sesión.
  - Ejecuta una **transacción atómica SQLite** (`BEGIN IMMEDIATE`):
    1. Verifica que `token_hash` no exista en `tarea_eventos_cambio` (garantía de uso único / anti-replay).
    2. Consulta la tabla `tareas` para obtener el `org_id` legítimo de la tarea:
       `SELECT t.org_id, v.estado, v.responsable FROM tareas t JOIN v_tareas_estado_efectivo v ON t.tarea_id = v.tarea_id WHERE t.tarea_id = :tarea_id`
    3. Re-verifica el estado efectivo actual (control de concurrencia optimista). Si cambió concurrentemente, aborta con `409 Conflict`.
    4. Inserta el evento en `tarea_eventos_cambio`, registrando `token_hash` (nunca el token ni secretos en texto plano).
    5. Realiza el `COMMIT`.

---

## 6. Integración del Modelo Generativo (Google Gemini Flash API)

### Decisión 6.1: Selección de Modelo y Configuración Flexible
- **Modelo Candidato Vigente:** Se adopta como candidato oficial la familia vigente **Gemini Flash** (ej. `gemini-3.8-flash` o `gemini-3.5-flash`), sujeto a la disponibilidad efectiva de la API pública y las cuotas del proyecto.
- **Modelos Obsoletos Eliminados:** Se descartan de plano las versiones anteriores `gemini-1.5-flash` y `gemini-2.0-flash`.
- **Distinción Crítica:** No se deben confundir los modelos utilizados por el entorno de desarrollo Antigravity con los modelos disponibles para consumo a través de la API externa de Google Gemini.
- **Configurabilidad Obligatoria:** La variable `GEMINI_MODEL` permanece completamente configurable a través del archivo de variables de entorno `.env`:
  ```env
  GEMINI_MODEL=gemini-3.8-flash
  ```

---

## 7. Interoperabilidad con Clientes MCP Externos y Evaluación RAG

### Decisión 7.1: Demostración con Cliente MCP Externo (Criterio P2 - D7)
- El servidor FastMCP es un servicio interoperable estándar que corre sobre el protocolo MCP.
- Para satisfacer el paso **D7 ("cliente externo")** del Criterio P2 de la rúbrica oficial, se documenta y habilita la conexión de un **cliente MCP independiente**:
  - Opción A: Conexión mediante el Inspector oficial de MCP (`npx @modelcontextprotocol/inspector uv run python -m backend.mcp.server`).
  - Opción B: Script cliente CLI independiente en Python (`tests/clients/test_external_mcp_client.py`) que ejecuta consultas sobre las herramientas expuestas (`checklist_organizacion`, `listar_plantillas`).
- Esta prueba demuestra que el servidor MCP opera conforme al estándar abierto sin depender exclusivamente del frontend React.

### Decisión 7.2: Evaluación RAG y Golden Set (Página 6 del PDF Oficial)
- El Golden Set consta de al menos 20 preguntas con la siguiente composición mínima obligatoria:
  - 12 preguntas con respuesta en el corpus.
  - 4 preguntas sin respuesta en el corpus (abstención explícita PR-3).
  - 2 preguntas con respuesta distinta entre versiones normativas (`GUI-INC v1` derogada vs `GUI-INC v2` vigente).
  - 2 preguntas con conflicto entre fuentes vigentes.
- **Pendiente de Validación en Auditoría del Corpus:**
  Se mantiene expresamente registrado como **pendiente** identificar las dos preguntas de contradicción interna entre documentos vigentes del corpus. El conflicto entre `FIC-PLA §2` (85%) y la tabla `plantillas` de SQLite (80%) corresponde a un **conflicto entre corpus documental y base de datos operativa**, no a una contradicción entre dos documentos normativos vigentes.
