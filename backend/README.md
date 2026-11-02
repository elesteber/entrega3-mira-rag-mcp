# Backend del Asistente MIRA CU-3

Este directorio contendrá el backend del sistema, estructurado en arquitectura desacoplada para dar soporte al **Caso de Uso CU-3: Asistente de Incorporación de Organizaciones**.

> **Estado actual:** PREPARACIÓN DOCUMENTAL PREVIA A SPEC KIT.  
> La implementación de código fuente, inicialización de dependencias y migraciones de base de datos se encuentran **pendientes** hasta la definición formal de especificaciones y tareas con GitHub Spec Kit.

---

## 1. Responsabilidades del Directorio

- **`app/`**: API REST FastAPI encargada de la autenticación de usuarios de DPRIME (simulada o vía headers/tokens de sesión), orquestación de llamadas al LLM (Google Gemini Flash), validación de respuestas y exposición de endpoints para el frontend.
- **`rag/`**: Pipeline RAG desacoplado:
  - Script offline de indexación y chunking del corpus de incorporación (`GUI-INC`, `FIC-PLA`, `REQ-INT`, `POL-FOR`).
  - Servicio runtime de recuperación vectorial con ChromaDB y cálculo de similitud.
  - Formateador de fragmentos con metadatos estructurados (código, sección, versión, vigencia).
- **`mcp/`**: Servidor MCP (FastMCP) propio:
  - Definición y exposición de herramientas (`checklist_organizacion`, `listar_plantillas`, `marcar_tarea`).
  - Consultas SQL parametrizadas a la base de datos relacional.
  - Validación de reglas de negocio en el backend (permisos por rol, pertenencia de organización, estados válidos).
- **`data/`**: Almacén local de datos:
  - Base de datos SQLite inicializada a partir del Excel `CU-3_datos.xlsx`.
  - Directorio persistente de ChromaDB (`chroma_db/`, excluido en Git).

---

## 2. Tecnologías Planificadas

- **Lenguaje:** Python 3.12+ gestionado con `uv`.
- **Framework Web:** FastAPI + Uvicorn + Pydantic v2.
- **Servidor MCP:** FastMCP / Official Python MCP SDK.
- **Base de Datos:** SQLite con SQLAlchemy o aiosqlite (consultas parametrizadas).
- **RAG & Vector Store:** ChromaDB + SentenceTransformers (`paraphrase-multilingual-MiniLM-L12-v2`).
- **Integración LLM:** Google GenAI SDK (Gemini Flash).

---

## 3. Próximos Pasos

1. Formalizar especificaciones técnicas y contratos en Spec Kit.
2. Inicializar entorno virtual con `uv`.
3. Crear script de ingestión de Excel a SQLite en `data/`.
4. Implementar servidor MCP y suite RAG.
