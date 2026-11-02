# Registro de Decisiones de Arquitectura (ADR)

Este documento registra formalmente las decisiones de arquitectura (Architecture Decision Records) adoptadas o propuestas por el equipo para el proyecto **MIRA CU-3**.

---

## Índice de Decisiones

- [ADR-01: Selección del Caso de Uso CU-3](#adr-01-selección-del-caso-de-uso-cu-3)
- [ADR-02: Separación Arquitectónica entre Servicio RAG y Servidor MCP](#adr-02-separación-arquitectónica-entre-servicio-rag-y-servidor-mcp)
- [ADR-03: Elección de SQLite como Base de Datos Relacional Local](#adr-03-elección-de-sqlite-como-base-de-datos-relacional-local)
- [ADR-04: Implementación del Servidor MCP con FastMCP (Python)](#adr-04-implementación-del-servidor-mcp-con-fastmcp-python)
- [ADR-05: Almacenamiento Vectorial con ChromaDB y MiniLM Multilingüe](#adr-05-almacenamiento-vectorial-con-chromadb-y-minilm-multilingüe)
- [ADR-06: Selección del Modelo Generativo Gemini Flash](#adr-06-selección-del-modelo-generativo-gemini-flash)
- [ADR-07: Protocolo de Confirmación Humana en Dos Fases para Mutaciones](#adr-07-protocolo-de-confirmación-humana-en-dos-fases-para-mutaciones)
- [ADR-08: Uso de uv para Gestión de Entornos y Dependencias Python](#adr-08-uso-de-uv-para-gestión-de-entornos-y-dependencias-python)

---

### ADR-01: Selección del Caso de Uso CU-3
- **Fecha:** 2026-11-02
- **Estado:** **Aceptada**
- **Contexto:** La pauta ofrecía elegir entre cuatro casos de uso (CU-1 Operador, CU-2 Soporte, CU-3 Incorporación, CU-4 Consumo).
- **Decisión:** Desarrollar exclusivamente el **Caso de Uso CU-3: Asistente de incorporación de organizaciones**.
- **Justificación:** CU-3 cuenta con un balance óptimo entre complejidad documental (fichas de plantillas, normas de integración, versiones de guías) y datos estructurados relacionales (organizaciones, tareas, integraciones, formularios). Permite demostrar con gran claridad el cumplimiento de los principios PR-1 a PR-7, especialmente en cuanto a roles, etapas y criterios de salida a producción.
- **Alternativas consideradas:** CU-1 (muy centrado en señales de fraude), CU-2 (soporte a incidentes técnicos), CU-4 (cálculo de tramos tarifarios).

---

### ADR-02: Separación Arquitectónica entre Servicio RAG y Servidor MCP
- **Fecha:** 2026-11-02
- **Estado:** **Propuesta** (sujeta a ratificación en Spec Kit)
- **Contexto:** La pauta exige recuperación documental (RAG) y consulta de datos del sistema mediante un servidor MCP propio. Existían dos opciones: exponer el RAG como una herramienta MCP adicional (`buscar_reglas`) o mantener el RAG como un subsistema interno orquestado por FastAPI.
- **Decisión:** Mantener el RAG como servicio interno independiente y desacoplado, mientras que el Servidor MCP se especializa exclusivamente en el acceso gobernado a los datos estructurados del sistema.
- **Justificación:**
  1. Permite evaluar y medir el RAG (Recall@k, fragmentación, embeddings) de forma aislada sin sobrecargar el protocolo MCP.
  2. Evita latencias innecesarias de serialización MCP para búsquedas vectoriales densas.
  3. Mantiene una clara separación de responsabilidades: RAG = conocimiento normativo estático/versionado; MCP = datos vivos y mutaciones en base de datos.
- **Alternativas consideradas:** Exponer `buscar_reglas` como herramienta dentro de FastMCP. Si bien es viable, mezclaría la base vectorial con el motor relacional en el mismo proceso de servidor MCP.

---

### ADR-03: Elección de SQLite como Base de Datos Relacional Local
- **Fecha:** 2026-11-02
- **Estado:** **Aceptada**
- **Contexto:** Se requiere cargar el archivo Excel `CU-3_datos.xlsx` en una base de datos relacional para que el servidor MCP ejecute consultas SQL parametrizadas.
- **Decisión:** Utilizar **SQLite** como motor de base de datos relacional (`backend/data/mira_cu3.db`).
- **Justificación:** SQLite es autocontenido, no requiere levantar demonios externos (como PostgreSQL o MySQL), garantiza portabilidad absoluta entre los miembros del equipo y evaluadores, y es 100% compatible con Python estándar (`sqlite3`, SQLAlchemy).
- **Alternativas consideradas:** PostgreSQL en Docker (mayor complejidad operativa innecesaria para un dataset de 50 registros).

---

### ADR-04: Implementación del Servidor MCP con FastMCP (Python)
- **Fecha:** 2026-11-02
- **Estado:** **Propuesta**
- **Contexto:** Se requiere un servidor MCP propio que exponga herramientas de lectura y escritura para el caso de uso.
- **Decisión:** Construir el servidor MCP utilizando la librería `FastMCP` de Python.
- **Justificación:** FastMCP permite definir herramientas mediante tipado Pydantic estándar y decoradores, maneja esquemas JSON automáticamente, soporta ejecución local vía `stdio` o `SSE`, y se integra nativamente en el ecosistema Python del backend.
- **Alternativas consideradas:** Servidor MCP en TypeScript (aumentaría la fricción al requerir dos runtimes diferentes en el backend).

---

### ADR-05: Almacenamiento Vectorial con ChromaDB y MiniLM Multilingüe
- **Fecha:** 2026-11-02
- **Estado:** **Propuesta**
- **Contexto:** El RAG requiere una base vectorial ligera y reproducible para indexar los 5 documentos del corpus con metadatos.
- **Decisión:** Usar **ChromaDB** en modo embebido persistente local con el modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- **Justificación:**
  1. ChromaDB corre embebido en Python sin requerir servicios externos en la nube.
  2. El modelo de embeddings MiniLM L12 multilingüe tiene excelente rendimiento semántico en español y bajo consumo de cómputo en CPU.
- **Alternativas consideradas:** FAISS (menor soporte nativo de filtros por metadatos estructurados), Pinecone (dependencia de nube externa con costo/tokens).

---

### ADR-06: Selección del Modelo Generativo Gemini Flash
- **Fecha:** 2026-11-02
- **Estado:** **Propuesta**
- **Contexto:** La pauta recomienda un modelo sin costo que corra en la nube.
- **Decisión:** Utilizar **Google Gemini Flash** (versión actual disponible en Google AI Studio con tier gratuito).
- **Justificación:** Ofrece tiempos de respuesta inferiores a 1 segundo, amplia ventana de contexto, excelente soporte para seguimiento de instrucciones estrictas de formato y generación de citas.
- **Alternativas consideradas:** Modelos locales en Ollama (dependen del hardware del expositor durante la demo en vivo).

---

### ADR-07: Protocolo de Confirmación Humana en Dos Fases para Mutaciones
- **Fecha:** 2026-11-02
- **Estado:** **Aceptada**
- **Contexto:** El principio PR-6 impone que ninguna acción con efecto ocurra sin que una persona la confirme.
- **Decisión:** Implementar un flujo en dos fases:
  1. `Preparación`: El backend recibe la intención del usuario y devuelve un objeto de confirmación sin escribir en SQLite.
  2. `Confirmación y Ejecución`: El usuario revisa en un modal de la UI los datos exactos del cambio y presiona "Confirmar". El frontend envía la autorización firmada para que el servidor MCP ejecute la mutación.
- **Justificación:** Asegura que una simple consulta de lenguaje natural nunca pueda disparar una mutación no deseada en la base de datos.
- **Alternativas consideradas:** Preguntar directamente en texto de chat (muy susceptible a falsos positivos del LLM).

---

### ADR-08: Uso de uv para Gestión de Entornos y Dependencias Python
- **Fecha:** 2026-11-02
- **Estado:** **Propuesta**
- **Contexto:** Se requiere un gestor de dependencias rápido, determinista y moderno para Python 3.12.
- **Decisión:** Utilizar `uv` como gestor de paquetes y entornos virtuales.
- **Justificación:** Es un orden de magnitud más rápido que pip/poetry, genera archivos de bloqueo deterministas (`uv.lock`) y garantiza reproducibilidad entre sistemas operativos.
- **Alternativas consideradas:** Poetry / pip tradicional.
