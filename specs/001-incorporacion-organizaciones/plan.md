# Implementation Plan: CU-3 Asistente de Incorporación de Organizaciones

**Branch**: `docs/cu3-plan` | **Date**: 2026-11-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-incorporacion-organizaciones/spec.md`, pauta académica `PAUTA_ENTREGA_3.md`, constitución `.specify/memory/constitution.md` y kit oficial de archivos base del CU-3.

---

## Summary

El sistema MIRA CU-3 es un asistente conversacional para el personal de operaciones e implementación de DPRIME SpA. Permite consultar el estado de avance de incorporación de organizaciones clientes, verificar requisitos normativos mediante recuperación documental fundamentada (RAG con `chunk_id` trazable) y consultar el estado operativo a través de herramientas registradas en el Model Context Protocol (MCP).

El enfoque técnico desacopla el conocimiento normativo (indexado en ChromaDB a partir de los 5 documentos Markdown oficiales del CU-3) de los datos estructurados del sistema (almacenados en SQLite e importados desde `CU-3_datos.xlsx`). Toda mutación de estado sobre tareas operativas se ejecuta bajo un estricto protocolo en dos pasos (preparación estructurada -> confirmación humana en interfaz -> ejecución atómica con token efímero), preservando la inmutabilidad de las tablas del kit mediante un almacén de eventos relacional (`tarea_eventos_cambio`) y una vista de estado efectivo (`v_tareas_estado_efectivo`). La herramienta de mutación `marcar_tarea` está estrictamente protegida y no se expone al modelo de lenguaje (Gemini), el cual solo dispone de herramientas de consulta. La identidad del operador se administra mediante una sesión de demostración firmada por el backend, cuyos permisos se validan exclusivamente en el servidor.

---

## Technical Context

- **Language/Version**: Python 3.12 (backend y orquestación), TypeScript / JavaScript ECMAScript 2022+ (frontend).
- **Primary Dependencies**:
  - Backend: `fastapi >= 0.115`, `uvicorn >= 0.30`, `fastmcp >= 0.4`, `google-genai >= 0.1` (o SDK oficial de Gemini), `chromadb >= 0.5`, `sentence-transformers` (`paraphrase-multilingual-MiniLM-L12-v2`), `pydantic >= 2.0`, `pyjwt` / `cryptography`.
  - Frontend: `react >= 18.3`, `vite >= 5.4`, `tailwindcss >= 3.4`, `lucide-react` (iconos).
  - Herramientas de desarrollo: `uv` (administrador ultrarrápido de paquetes y entornos virtuales en Python).
- **Modelos Generativos (LLM)**:
  - Familia candidata vigente: **Gemini Flash** (ej. `gemini-3.8-flash` o `gemini-3.5-flash`), sujeto a disponibilidad de API pública y cuota del proyecto.
  - Modelos anteriores descartados: `gemini-1.5-flash` y `gemini-2.0-flash`.
  - Diferenciación: Se aclara que los modelos de la API de Gemini no deben confundirse con los modelos del asistente de codificación Antigravity.
  - Configurabilidad: Variable `GEMINI_MODEL` configurable vía `.env`.
- **Storage**:
  - Relacional: SQLite 3 (`backend/data/mira_cu3.db`), hidratado automáticamente desde `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/datos/CU-3_datos.xlsx`.
  - Vectorial: ChromaDB (`backend/rag/chroma_db`), persistido localmente con metadatos de vigencia, documento, sección y `chunk_id` sobre los 5 documentos del kit.
- **Testing**:
  - `pytest` y `pytest-asyncio` para pruebas unitarias de contratos REST y herramientas MCP.
  - Script offline de evaluación del Golden Set (`tests/evaluation/eval_goldenset.py`) con verificación métrica de principios PR-1 a PR-7.
- **Target Platform**: Entorno POSIX / Linux local (probado en Arch Linux), ejecutable en desarrollo con hot-reload.
- **Project Type**: Web Application monorepo desacoplada (Frontend SPA en React/Vite + Orquestador API REST en FastAPI + Servidor FastMCP local interoperable).
- **Performance Goals**:
  - Consulta RAG (`buscar_reglas`): < 300 ms en CPU.
  - Herramientas MCP relacionales en SQLite: < 50 ms.
  - Interacción conversacional completa: Monitoreada en interfaz mediante traza diagnóstica visible (sin SLA contractual externo arbitrario).
- **Constraints**:
  - Cumplimiento irrestricto de principios PR-1 a PR-7.
  - Prohibición absoluta de SQL libre generado por LLM.
  - Prohibición de escritura directa sobre tablas base del kit.
  - Validación de roles e identidades exclusivamente en servidor mediante sesión firmada.
  - Aislamiento de observaciones de tareas como datos no confiables (mitigación de prompt injection en `T-008`).
  - No exposición de la herramienta `marcar_tarea` al LLM.
- **Scale/Scope**:
  - 4 usuarios reales del kit (`U-I1` Sofía Tapia, `U-I2` Diego Fuentes, `U-I3` Carolina Vera, `U-I4` Pablo Reyes).
  - 4 organizaciones (`ORG-05`, `ORG-06`, `ORG-07`, `ORG-08`).
  - 37 tareas operativas en 6 etapas (`E0` a `E5`), con estados `pendiente`, `en_curso`, `completada`.
  - 4 plantillas (`PLA-REM`, `PLA-SIN`, `PLA-CTA`, `PLA-ADM`).
  - 4 integraciones (`I-01` a `I-04`).
  - 3 formularios propios (`F-01` a `F-03`).
  - 5 documentos Markdown oficiales del CU-3.
  - 8 momentos obligatorios de demostración en vivo (D1 a D8 de la rúbrica oficial P2, incluyendo cliente MCP externo).

---

## Constitution Check

*Comprobación de puertas de control previas y posteriores al diseño técnico:*

| Principio Constitucional | Regla Operativa | Validación en el Diseño Técnico | Estado |
|---|---|---|:---:|
| **PR-1: Decisión humana** | El asistente no decide ni muta estado autónomamente. | Endpoint `/api/action/prepare` solo sugiere; la mutación requiere confirmación interactiva en modal de UI. Gemini no recibe herramientas de mutación. | **PASÓ** |
| **PR-2: Evidencia documental** | Toda afirmación sobre reglas debe citar fuente, sección y versión exacta. | Modelo RAG en ChromaDB y esquema `Citation` exigen `chunk_id`, documento, sección, versión y extracto literal verificado. | **PASÓ** |
| **PR-3: Abstención explícita** | Si la información falta en el corpus, se declara abiertamente. | Flujo de orquestación detecta score bajo o ausencia de fragmentos y activa respuesta estructurada de abstención (D2). | **PASÓ** |
| **PR-4: Conflicto entre fuentes** | Ante contradicciones vigentes, se exponen ambas posturas sin elegir. | Prompt y herramientas detectan discrepancia (`FIC-PLA §2` 85% vs `plantillas.db` 80%, `GUI-INC v1` vs `v2`) y fuerzan reporte dual (D3). | **PASÓ** |
| **PR-5: Datos mediante MCP** | Todo dato proviene de llamadas MCP registradas; no inventar ni extrapolar. | FastMCP con consultas SQL parametrizadas a SQLite. Trazas visibles en frontend y observaciones en cuarentena (D4, D6). | **PASÓ** |
| **PR-6: Confirmación en 2 pasos** | Acciones con mutación requieren flujo seguro de preparación y confirmación. | Token efímero HMAC (TTL 5 min), consumo único vía `token_hash` y transacción atómica SQLite con concurrencia optimista (D5). | **PASÓ** |
| **PR-7: Control de acceso por rol** | Validación de permisos en servidor según identidad confiable. | Sesión demo firmada por backend; validación en servidor de pertenencia de organizaciones (`U-I1` a `U-I4`), extensible a clientes MCP externos (D7). | **PASÓ** |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-incorporacion-organizaciones/
├── plan.md              # Este plan de implementación técnica detallado
├── research.md          # Fase 0: Decisiones arquitectónicas, mitigaciones y modelos LLM
├── data-model.md        # Fase 1: Esquema relacional, DDL de eventos y metadatos RAG
├── quickstart.md        # Fase 1: Guía de ejecución, protocolo D1 a D8 y cliente externo
├── contracts/           # Fase 1: Contratos formales de interfaces
│   ├── api-rest.yaml        # OpenAPI 3.0.3 para orquestador backend
│   ├── mcp-tools.json       # JSON Schema Draft 2020-12 de herramientas FastMCP
│   └── events-schema.json   # JSON Schema Draft 2020-12 de eventos y estado efectivo
└── checklists/
    └── requirements.md  # Checklist de calidad de requisitos (16/16 superado)
```

### Source Code Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # Punto de entrada FastAPI, middlewares y rutas
│   │   ├── config.py            # Carga de variables de entorno con Pydantic Settings
│   │   ├── security.py          # Validación de sesión demo, tokens efímeros HMAC y control PR-7
│   │   ├── orchestrator.py      # Orquestador: llamada a Gemini Flash, ejecución MCP y citas con chunk_id
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py          # Endpoint POST /api/chat
│   │   │   ├── actions.py       # Endpoints POST /api/action/prepare y confirm
│   │   │   └── session.py       # Endpoints GET /api/session/users y switch
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── chat.py          # Modelos Pydantic para chat y citas (con chunk_id)
│   │       ├── actions.py       # Modelos Pydantic para acciones y justificacion
│   │       └── session.py       # Modelos Pydantic para usuarios simulados
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py            # Servidor FastMCP interoperable y registro de herramientas
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── rag_tools.py     # Herramienta buscar_reglas (conexión con ChromaDB)
│   │   │   ├── sql_tools.py     # Herramientas checklist, plantillas, integraciones, formularios
│   │   │   └── mutation_tools.py # Herramienta marcar_tarea (protegida, no expuesta a LLM)
│   │   └── client.py            # Cliente MCP para invocar herramientas desde el orquestador
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── indexer.py           # Lógica de chunking semántico y embeddings con chunk_id
│   │   ├── retriever.py         # Búsqueda semántica con filtros de vigencia
│   │   └── index_corpus.py      # Script CLI para indexación offline inicial
│   └── data/
│       ├── __init__.py
│       ├── init_db.py           # Script CLI para hidratar SQLite desde Excel
│       ├── db.py                # Conexión SQLite con thread-safety y SQL parametrizado
│       └── models.py            # Modelos y consultas SQL sobre tablas base y eventos
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx              # Contenedor principal con layout de 2 columnas
│       ├── components/
│       │   ├── SessionSelector.tsx  # Barra superior con selector de U-I1 a U-I4
│       │   ├── ChatInterface.tsx    # Mensajería, entrada de texto y streaming/respuesta
│       │   ├── CitationCard.tsx     # Tarjeta interactiva de cita con chunk_id, fuente, sección y versión
│       │   ├── McpTracePanel.tsx    # Panel lateral de trazabilidad de llamadas MCP y tiempos (sanitizado)
│       │   ├── ConfirmationModal.tsx # Modal de confirmación en dos pasos (PR-1, PR-6)
│       │   └── EvidenceBadge.tsx    # Indicador de estado de evidencia (Completa/Parcial/Conflicto)
│       ├── services/
│       │   └── api.ts           # Cliente HTTP para backend FastAPI
│       └── types/
│           └── index.ts         # Tipos TypeScript derivados de contratos OpenAPI
├── tests/
│   ├── unit/
│   │   ├── test_security.py     # Pruebas de validación de roles y HMAC tokens
│   │   ├── test_sql_tools.py    # Pruebas de consultas SQL parametrizadas
│   │   └── test_rag_chunker.py  # Pruebas de segmentación documental y chunk_id
│   ├── integration/
│   │   ├── test_mcp_server.py   # Pruebas de invocación de herramientas FastMCP
│   │   ├── test_chat_flow.py    # Pruebas del endpoint /api/chat completo
│   │   └── test_action_flow.py  # Pruebas del flujo prepare -> confirm
│   ├── clients/
│   │   └── test_external_mcp_client.py # Cliente MCP externo para demostración D7
│   └── evaluation/
│       ├── eval_goldenset.py    # Suite de regresión del Golden Set (D1 a D8)
│       └── goldenset_cases.json # Casos de prueba formales con aserciones
├── docs/                        # Documentación metodológica y auditorías previas
└── pyproject.toml               # Configuración del proyecto Python para uv
```

**Structure Decision**: Monorepo desacoplado con separación estricta de responsabilidades:
1. `backend/app`: Orquestador FastAPI que administra la sesión demo, recibe solicitudes del frontend, coordina la llamada al modelo Gemini Flash exponiendo solo herramientas de lectura, y gestiona el flujo de confirmación.
2. `backend/mcp`: Servidor FastMCP estándar que aísla el acceso a datos. Expone `buscar_reglas` (RAG) y consultas SQL parametrizadas a SQLite, además de la herramienta protegida `marcar_tarea` para ejecución interna post-confirmación.
3. `backend/rag`: Motor de indexación y recuperación documental offline/online sobre ChromaDB con metadatos unificados y `chunk_id`.
4. `frontend`: Aplicación web moderna en React + Vite que visualiza explícitamente las citas documentales, las trazas MCP sanitizadas y el modal de confirmación en dos pasos.

---

## Complexity Tracking

| Componente de Complejidad | Justificación Técnica | Alternativa Simple Rechazada y Motivo |
|---|---|---|
| **Almacén de eventos (`tarea_eventos_cambio`)** | Garantiza la inmutabilidad física y jurídica de los datos originales del kit (`CU-3_datos.xlsx`), registrando quién, cuándo y por qué mutó una tarea con control anti-replay vía `token_hash`. | *Modificar SQLite directamente*: Rechazada porque destruiría los datos base del kit y violaría el principio de auditoría e inmutabilidad evaluativa. |
| **Token efímero HMAC (`token_confirmacion`)** | Asegura que la confirmación humana (Paso 2) corresponda exactamente a la propuesta validada (Paso 1) sin permitir mutaciones arbitrarias. | *Confirmar enviando ID y nuevo estado directamente*: Rechazada porque permitiría saltarse el Paso 1 o alterar parámetros entre propuesta y confirmación (vulnerabilidad PR-6). |
| **Sesión demo firmada (`session_token`)** | Proporciona autenticación verificable en el backend para la demostración académica sin depender de un header abierto manipulable. | *Confiar en parámetro libre del LLM o header plano*: Rechazada porque violaría taxativamente el control de acceso del servidor (PR-7). |
| **Herramienta RAG expuesta como MCP (`buscar_reglas`)** | Permite que el modelo decida dinámicamente si necesita consultar normas, o bien que el orquestador evalúe la recuperación de forma aislada. | *Inyectar siempre todo el corpus en el prompt*: Rechazada porque sobrecarga la ventana de contexto, degrada la precisión y encarece la inferencia. |

---

## Team Responsibilities & Parallel Work Streams

La arquitectura y los contratos definidos permiten la ejecución en paralelo por parte de los 4 integrantes del equipo:

1. **Rodrigo Guerrero (Backend de Datos, FastMCP y Control de Acceso)**:
   - Hidratación de SQLite (`init_db.py`, `models.py`), almacén de eventos y vista efectiva.
   - Implementación de herramientas FastMCP relacionales y de mutación protegida (`sql_tools.py`, `mutation_tools.py`).
   - Implementación de `backend/app/security.py` (control de acceso por organización PR-7 y tokens HMAC PR-6 con hash anti-replay).
   - Pruebas unitarias en `tests/unit/test_security.py` y `test_sql_tools.py`.

2. **Jorge Álvarez (Frontend Web, Trazas y Citas Interactivas)**:
   - Configuración de React + Vite + TailwindCSS en `frontend/`.
   - Implementación de componentes: `SessionSelector`, `ChatInterface`, `CitationCard` (con `chunk_id`), `McpTracePanel` sanitizado, `ConfirmationModal` y `EvidenceBadge`.
   - Integración con la API REST mediante `frontend/src/services/api.ts` respetando `api-rest.yaml`.

3. **Lester González (Orquestador FastAPI, Gemini Flash y Cliente MCP)**:
   - Implementación de `backend/app/main.py`, `config.py` y los routers de chat, acciones y sesión.
   - Implementación de `backend/app/orchestrator.py` con llamadas a Gemini Flash (restringiendo herramientas al subconjunto de consulta) y parseo de citas con `chunk_id`.
   - Implementación de `backend/mcp/client.py` para la invocación asíncrona de herramientas.
   - Pruebas de integración en `tests/integration/test_chat_flow.py` y `test_action_flow.py`.

4. **Ángel Salgado (RAG, ChromaDB, Evaluación y Golden Set)**:
   - Implementación de `backend/rag/indexer.py`, `retriever.py` e `index_corpus.py` (con `chunk_id` determinista).
   - Implementación de la herramienta FastMCP `buscar_reglas` conectando con ChromaDB.
   - Construcción del banco de pruebas `tests/evaluation/goldenset_cases.json` y el evaluador `eval_goldenset.py`.
   - Preparación y validación del cliente MCP externo independiente (`tests/clients/test_external_mcp_client.py`) para el paso D7.

---

## Plan Status & Next Actions

- **Plan Status**: Completado, revisado y con consistencia técnica 100% verificada contra la Constitución (PR-1 a PR-7), el kit oficial y la rúbrica de la cátedra.
- **Artefactos corregidos y consistentes**:
  - `specs/001-incorporacion-organizaciones/research.md` (Fase 0)
  - `specs/001-incorporacion-organizaciones/data-model.md` (Fase 1)
  - `specs/001-incorporacion-organizaciones/contracts/api-rest.yaml` (Fase 1)
  - `specs/001-incorporacion-organizaciones/contracts/mcp-tools.json` (Fase 1)
  - `specs/001-incorporacion-organizaciones/contracts/events-schema.json` (Fase 1)
  - `specs/001-incorporacion-organizaciones/quickstart.md` (Fase 1)
  - `specs/001-incorporacion-organizaciones/plan.md` (Fase 1)
- **Siguiente acción recomendada**:
  - Tras la aprobación del equipo, ejecutar `/speckit-tasks` para generar el desglose ordenado de tareas en `tasks.md`.
