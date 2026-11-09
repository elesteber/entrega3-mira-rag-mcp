# Backend del Asistente MIRA CU-3 (Release v3.0)

Este directorio contiene el backend completo del sistema MIRA para el **Caso de Uso CU-3: Asistente de Incorporación de Organizaciones** (*DPRIME SpA*), estructurado bajo una arquitectura desacoplada orientada a **evidencia documental (RAG)** y **acceso gobernado a datos relacionales (FastMCP)**.

> **Estado de Implementación:** 100% implementado, integrado y verificado (350 pruebas aprobadas, 1 xfailed conocido en la suite completa de `pytest`).

---

## 1. Arquitectura y Módulos

```text
backend/
├── app/                  # API REST FastAPI y Orquestador Conversacional
│   ├── main.py           # Aplicación FastAPI, configuración de CORS y montaje de routers
│   ├── config.py         # Configuración centralizada vía Pydantic Settings
│   ├── security.py       # Firma HMAC (JWT HS256), emisión de tokens y control de sesiones
│   ├── orchestrator.py   # Orquestador del asistente, detección conservadora de intenciones, RAG y FastMCP
│   ├── routers/          # Endpoints REST (/api/session, /api/chat, /api/action)
│   └── schemas/          # Modelos de datos Pydantic v2 (ActionDraft, ActionProposal, etc.)
│
├── mcp/                  # Servidor FastMCP y Protocolo MCP Propio
│   ├── server.py         # Instancia FastMCP registrada con middleware de delegación stdio
│   ├── client.py         # Cliente MCP estándar con filtrado de herramientas y timeout (MiraMcpClient)
│   ├── transport_auth.py # Middleware de delegación firmado por solicitud (AUD-03, PR-7)
│   ├── access_control.py # Reglas de autorización en SQLite (roles, asignación y etapa E5)
│   └── tools/            # Herramientas modulares de consulta y mutación protegida
│       ├── sql_tools.py      # checklist_organizacion, listar_plantillas, consultar_integracion, consultar_formularios
│       ├── rag_tools.py      # buscar_reglas (búsqueda híbrida en ChromaDB)
│       └── mutation_tools.py # marcar_tarea (mutación atómica transaccional en BEGIN IMMEDIATE)
│
├── rag/                  # Pipeline de Recuperación Documental y Embeddings
│   ├── index_corpus.py   # CLI de indexación offline reproducible en ChromaDB
│   ├── indexer.py        # Segmentación por encabezados de sección y metadatos estructurados
│   ├── retriever.py      # Recuperador híbrido (denso MiniLM L12 + BM25 con Reciprocal Rank Fusion)
│   ├── lexico.py         # Motor léxico BM25 en memoria con tokenización en español
│   ├── citas.py          # Formateador y validador de citas canónicas (documento, sección, versión)
│   └── verify_corpus.py  # Verificador de integridad de los documentos Markdown del kit
│
└── data/                 # Almacenamiento Relacional y Vectorial Local
    ├── db.py             # Conexión SQLite y resolución de rutas
    ├── init_db.py        # CLI de hidratación de SQLite a partir del Excel CU-3_datos.xlsx
    ├── mira_cu3.db       # Base de datos SQLite original hidratada (inmutable)
    └── chroma_db/        # Directorio persistente de la colección vectorial ChromaDB
```

---

## 2. Variables de Entorno del Backend

El backend se configura mediante un archivo `.env` en la raíz del repositorio o variables del sistema (gestionadas por `backend/app/config.py`):

| Variable | Tipo / Valor por Defecto | Propósito y Requisitos |
|---|---|---|
| `SQLITE_DB_PATH` | `backend/data/mira_cu3.db` | Ruta a la base de datos SQLite relacional. En demostración se puede usar `backend/data/mira_cu3_demo.db`. |
| `CHROMADB_PATH` | `backend/data/chroma_db` | Ruta al directorio persistente de ChromaDB. |
| `CORPUS_DIR` | `archivos-base/.../corpus` | Directorio con los 5 documentos Markdown oficiales del CU-3. |
| `EXCEL_DATA_PATH` | `archivos-base/.../CU-3_datos.xlsx` | Ruta al archivo Excel inmutable del kit para hidratación. |
| `GEMINI_API_KEY` | *(requerida para LLM real)* | Clave de API de Google Gemini obtenida en Google AI Studio. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Modelo generativo Gemini Flash configurable. |
| `JWT_SECRET` | *(mínimo 32 bytes en prod)* | Clave secreta para la firma HMAC de sesiones y tokens de confirmación (5 min). |
| `MIRA_MCP_DELEGATION_SECRET` | *(mínimo 32 bytes)* | Clave independiente obligatoria para la delegación de identidad en FastMCP stdio (AUD-03, PR-7). |

---

## 3. Endpoints Principales de la API REST

- `GET /health`: Comprobación de salud del backend, versión y estado de servicios.
- `GET /api/session/users`: Lista los 4 usuarios simulados del kit (`U-I1` a `U-I4`), roles y organizaciones asignadas.
- `POST /api/session/switch`: Cambia la sesión activa y emite un token de sesión JWT HS256.
- `POST /api/chat`: Procesa la consulta del operador. Integra el RAG para citas normativas, el servidor MCP para datos vivos y detecta de manera conservadora solicitudes de cambio de estado emitiendo un borrador `ActionDraft` sin tokens colaterales.
- `POST /api/action/prepare`: Valida precondiciones operativas, permisos y emite una propuesta estructurada (`ActionProposal`) con un token de confirmación criptográfico efímero (validez estricta de 5 minutos).
- `POST /api/action/confirm`: Ejecuta la mutación de estado invocando `marcar_tarea` en FastMCP dentro de una transacción atómica `BEGIN IMMEDIATE`, verificando el hash anti-replay y la concurrencia optimista.

---

## 4. Comandos de Operación

### Inicializar la Base de Datos SQLite
```bash
uv run python -m backend.data.init_db
```
Para inicializar o reiniciar una base de demostración con eventos limpios:
```bash
uv run python -m backend.data.init_db --db backend/data/mira_cu3_demo.db --reset-events
```

### Indexar el Corpus Documental (RAG)
```bash
uv run python -m backend.rag.index_corpus
```

### Iniciar el Servidor FastAPI
```bash
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Ejecutar Pruebas Automatizadas
```bash
# Suite completa del backend (350 passed, 1 xfailed):
uv run --extra dev pytest tests/ -q -rs

# Pruebas específicas de integración Chat -> Propuesta -> Modal:
uv run --extra dev pytest tests/integration/test_chat_propuesta.py -v

# Pruebas de seguridad de transporte y delegación FastMCP (AUD-03):
uv run --extra dev pytest tests/integration/test_auth_stdio.py -v
```
