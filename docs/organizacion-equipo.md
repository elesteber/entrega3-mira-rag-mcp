# Organización del Equipo y Distribución de Responsabilidades

Este documento define la estructura de trabajo colaborativo para el equipo de cuatro estudiantes durante el ciclo de desarrollo de la **Entrega 3 (Caso MIRA CU-3)**.

---

## 1. Distribución de Roles y Responsabilidades Principales

| Integrante | Rol Principal | Componentes a Cargo | Responsabilidades Técnicas Específicas |
|---|---|---|---|
| **Integrante 1** | **Especialista RAG y Corpus** | `backend/rag/`, `docs/corpus-cu3.md` | • Preparación y preprocesamiento de documentos Markdown.<br>• Extracción y catalogación de metadatos (`doc_code`, `version`, `section`, `status`).<br>• Script de indexación y persistencia en ChromaDB.<br>• Implementación y comparación experimental de estrategias de chunking.<br>• Lógica de filtrado por vigencia y formato de citas obligatorias (PR-2). |
| **Integrante 2** | **Especialista MCP y Datos** | `backend/mcp/`, `backend/data/`, `docs/datos-cu3.md` | • Script de migración e ingestión del Excel `CU-3_datos.xlsx` a SQLite.<br>• Creación del servidor MCP (FastMCP) y consultas parametrizadas.<br>• Implementación de herramientas de lectura (`checklist_organizacion`, `listar_plantillas`).<br>• Implementación de herramienta de escritura (`marcar_tarea`) con validación de roles en servidor (PR-6, PR-7). |
| **Integrante 3** | **Arquitecto Backend e Integración** | `backend/app/`, `docs/arquitectura-propuesta.md` | • Configuración de la API REST FastAPI y ruteadores.<br>• Conexión del cliente MCP con el servidor FastMCP.<br>• Integración con Google Gemini Flash API mediante SDK oficial.<br>• Orquestación de llamadas, inyección de contexto de usuario autenticado y ensamblado de prompt.<br>• Manejo centralizado de errores, trazas y caídas de servicios. |
| **Integrante 4** | **Ingeniero Frontend y Evaluación** | `frontend/`, `tests/`, `docs/plan-evaluacion.md` | • Desarrollo de la aplicación web en React + Vite en español.<br>• Componentes visuales de chat, badges de citas clicables y visor de trazas MCP.<br>• Modal interactivo de confirmación humana para mutaciones (PR-6).<br>• Consolidación del Golden Set (20 preguntas) y suite de evaluación automatizada (`pytest`).<br>• Preparación y ensayo de los 8 pasos de la demostración en vivo (D1 a D8). |

---

## 2. Matriz RACI Preliminar

- **R (Responsible):** Encargado de construir.
- **A (Accountable):** Responsable de que cumpla los criterios de la pauta.
- **C (Consulted):** Apoya en el diseño e integración.
- **I (Informed):** Recibe el artefacto y lo utiliza.

| Entregable / Hito | Int. 1 (RAG) | Int. 2 (MCP) | Int. 3 (Back) | Int. 4 (Front/Eval) |
|---|:---:|:---:|:---:|:---:|
| Ingestión de datos a SQLite | I | **R / A** | C | I |
| Servidor FastMCP y contratos | I | **R / A** | C | I |
| Indexación y pipeline RAG | **R / A** | I | C | I |
| Orquestación FastAPI y Gemini | C | C | **R / A** | C |
| UI React (Chat, Citas, Modales) | I | I | C | **R / A** |
| Golden Set y benchmarking | C | C | C | **R / A** |
| Guion de Demo en Vivo (D1 a D8) | C | C | C | **R / A** |
| Redacción de Informe Escrito (12 planas) | **R** (Sec 11.3) | **R** (Sec 11.4) | **R** (Sec 11.5) | **R** (Sec 11.6) |

---

## 3. Protocolo de Flujo de Trabajo en Git

1. **Rama Principal (`main`):** Protegida. Siempre en estado desplegable y funcional.
2. **Ramas de Trabajo por Funcionalidad:**
   - Nomenclatura convencional:
     - `feat/rag-indexing`
     - `feat/mcp-server-tools`
     - `feat/backend-orchestration`
     - `feat/frontend-chat-ui`
     - `test/golden-set-evaluation`
3. **Commits Convencionales:**
   - Formato obligatorio: `tipo(alcance): descripción clara en presente` (ej: `feat(mcp): agregar validacion de rol para etapa E5`).
4. **Revisiones Cruzadas (Peer Reviews):**
   - Todo Pull Request debe contar con al menos una revisión y aprobación cruzada antes del merge:
     - RAG es revisado por Backend.
     - MCP es revisado por Backend.
     - Backend es revisado por Frontend.
     - Frontend y Pruebas son revisados por el equipo completo.
