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
- [ADR-09: Almacén de Eventos Relacional y Vista de Estado Efectivo (PR-1, PR-6, FR-012)](#adr-09-almacén-de-eventos-relacional-y-vista-de-estado-efectivo-pr-1-pr-6-fr-012)
- [ADR-10: Golden Set con Anclas Literales y Conflictos Vigentes del Corpus](#adr-10-golden-set-con-anclas-literales-y-conflictos-vigentes-del-corpus)
- [ADR-11: Fragmentación por Encabezados, 256 Tokens y Búsqueda Híbrida](#adr-11-fragmentación-por-encabezados-256-tokens-y-búsqueda-híbrida)
- [ADR-12: Delegación firmada por solicitud MCP stdio (AUD-03)](#adr-12-delegación-firmada-por-solicitud-mcp-stdio-aud-03)

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
- **Estado:** **Aceptada**
- **Contexto:** Se requiere un servidor MCP propio que exponga herramientas de lectura y escritura para el caso de uso.
- **Decisión:** Construir el servidor MCP utilizando la librería `FastMCP` de Python.
- **Justificación:** FastMCP permite definir herramientas mediante tipado Pydantic estándar y decoradores, maneja esquemas JSON automáticamente, soporta ejecución local vía `stdio` o `SSE`, y se integra nativamente en el ecosistema Python del backend. Se ratifica e implementa operativamente con registro modular de herramientas y aislamiento de herramientas protegidas.
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

---

### ADR-09: Almacén de Eventos Relacional y Vista de Estado Efectivo (PR-1, PR-6, FR-012)
- **Fecha:** 2026-11-07
- **Estado:** **Aceptada**
- **Contexto:** La cátedra y la constitución del proyecto exigen que los datos originales del archivo Excel `CU-3_datos.xlsx` permanezcan estrictamente inalterados en la base de datos (snapshot de solo lectura), mientras que el asistente debe reflejar mutaciones confirmadas de tareas de incorporación.
- **Decisión:** Implementar la tabla `tarea_eventos_cambio` (almacén inmutable de mutaciones con `token_hash` SHA-256) y la vista consolidada `v_tareas_estado_efectivo` con resolución en tiempo real mediante `COALESCE(ult_ev.nuevo_estado, t.estado)` y transacción atómica SQLite (`BEGIN IMMEDIATE`).
- **Justificación:**
  1. Conserva el 100% de los datos originales del kit oficial en la tabla `tareas` sin sobreescrituras destructivas.
  2. Garantiza control criptográfico anti-replay mediante restricción `UNIQUE` en `token_hash` sin almacenar secretos en texto plano.
  3. Desacopla la importación administrativa offline del acceso operativo en tiempo de ejecución.
  4. Permite auditoría completa de fecha, usuario y justificación para cada transición.
- **Alternativas consideradas:** Sobreescritura directa de la tabla `tareas` (descartada por vulnerar la inmutabilidad exigida por la cátedra); almacenamiento de eventos en archivos JSON planos (descartado por falta de transaccionalidad ACID y soporte relacional).

---

### ADR-10: Golden Set con Anclas Literales y Conflictos Vigentes del Corpus
- **Fecha:** 2026-11-07
- **Estado:** **Propuesta** (pendiente de revisión por pares y validación del cliente)
- **Contexto:** La pauta (§7.1) exige 2 preguntas con conflicto entre fuentes *vigentes* y medir Recall@k a nivel de fragmento. `research.md §7.2` dejó pendiente identificar esos conflictos, y el caso PLA-ADM (85 vs 80) es un conflicto documento-datos.
- **Decisión:** (1) Usar como conflictos vigentes `FIC-PLA v1 §1` vs `POL-FOR v1 §2` y `GUI-INC v2 §1` vs `POL-FOR v1 §2`; conservar PLA-ADM como caso adicional `conflicto_documento_datos`. (2) Identificar cada fragmento esperado con `doc_code`, `version`, `section` y una cita literal ("ancla") única en el corpus; un fragmento recuperado acierta si es del mismo documento y versión y contiene el ancla.
- **Justificación:** Las anclas hacen la métrica independiente de la estrategia de chunking (necesario para el experimento comparativo del criterio C3) y verificables automáticamente (`tests/unit/test_goldenset.py`).
- **Alternativas consideradas:** Identificar fragmentos por `chunk_id` (se acopla a una estrategia de chunking concreta); usar PLA-ADM como conflicto vigente (no cumple la definición de la pauta).

---

### ADR-11: Fragmentación por Encabezados, 256 Tokens y Búsqueda Híbrida
- **Fecha:** 2026-11-07
- **Estado:** **Propuesta** (pendiente de revisión por pares)
- **Contexto:** El criterio C3 exige elegir la fragmentación con un experimento comparativo y justificar la búsqueda. El modelo `paraphrase-multilingual-MiniLM-L12-v2` trunca a 128 tokens por defecto.
- **Experimento:** `tests/evaluation/eval_recuperacion.py` sobre el golden set v1.0 (21 casos sin MCP), 10 configuraciones = {encabezados, fijo 150/40 palabras, fijo 60/15 palabras} × {128, 256 tokens} × {denso, híbrido}. Resultados en `tests/evaluation/resultados/recuperacion_20261107-025237.md`.

  | Configuración | Recall@1 | Recall@4 | MRR | Conflicto@4 | Truncados |
  |---|---|---|---|---|---|
  | Encabezados, 128, denso (línea base) | 0.77 | 0.85 | 0.82 | 0.50 | 11/24 |
  | **Encabezados, 256, híbrido (elegida)** | 0.69 | **1.00** | 0.81 | 0.75 | 0/24 |
  | Fijo 150/40, 256, híbrido | 0.62 | 1.00 | 0.76 | 0.75 | 4/14 |
  | Fijo 60/15, 128, híbrido | 0.62 | 0.85 | 0.71 | 1.00 | 1/36 |

- **Decisión:** Fragmentar por encabezados Markdown (subsección `###` en FIC-PLA §2), vectorizar con `max_seq_length=256` y buscar en modo híbrido (denso + BM25, fusión RRF con k=60, sin ajustar). El umbral de similitud se aplica por consulta, no por fragmento.
- **Justificación:**
  1. Encabezados + híbrido alcanza Recall@4 = 1.00 en las 13 preguntas con respuesta y no trunca ningún fragmento.
  2. Cada fragmento corresponde a una sección, por lo que la cita (documento, sección, versión) es exacta. Los fragmentos fijos cruzan secciones (`§2–§3`), lo que vuelve imprecisa la cita (PR-2).
  3. La búsqueda densa sola pierde términos exactos (código `PLA-CTA`, etapa `E3`); BM25 los recupera (GS-03 y GS-10 pasan de fallar a acertar).
  4. El umbral por fragmento eliminaba evidencia correcta (ficha PLA-CTA, similitud 0.32, en el puesto 4 del ranking híbrido).
- **Limitaciones y hallazgos:**
  - La configuración se eligió con el mismo golden set con que se mide (no hay conjunto separado); se informa como limitación.
  - El umbral de similitud **no** sirve para la abstención: la mayor similitud de una pregunta sin respuesta fue 0.56, mientras que la de una pregunta con respuesta bajó a 0.45. La abstención (PR-3) debe decidirla el orquestador al juzgar si los fragmentos responden la pregunta.
  - Fallo de recuperación pendiente: GS-18 (conflicto) no recupera `FIC-PLA v1 §1` en el top-10, así que el asistente podría no detectar ese conflicto.
  - **Ciclo de mejora 1 (2026-11-07), no adoptado:** se probó *stemming* por prefijo en BM25 (`RAG_BM25_PREFIJO`). Con prefijo 6, `FIC-PLA v1 §1` sube del puesto >10 al 9 en GS-18, pero sigue fuera del top-4; Recall@3 sube de 0.92 a 1.00 y MRR de 0.814 a 0.821. No se adopta porque la ganancia es de un caso, medida sobre el mismo golden set, y no corrige GS-18 (`tests/evaluation/resultados/recuperacion_20261107-125419.md`). La opción queda disponible y desactivada por defecto.
- **Alternativas consideradas:** Fragmentos de tamaño fijo (cita imprecisa, Recall@1 menor); solo denso (Recall@4 0.85); solo BM25 (Recall@4 1.00 en una prueba exploratoria, pero frágil ante paráfrasis, porque las preguntas del golden set comparten vocabulario con el corpus).

---

### ADR-12: Delegación firmada por solicitud MCP stdio (AUD-03)
- **Estado:** Aceptada para esta corrección.
- **Decisión:** Middleware FastMCP verifica JWT HS256 en metadata `mira_delegation`,
  con secreto independiente por entorno y contexto aislado restaurado al finalizar.
  SQLite sigue siendo la autoridad de permisos; `usuario_id` solo es una aserción.
- **Justificación:** Cierra la suplantación por argumentos y permite compartir un
  transporte entre usuarios sin identidad persistente de sesión MCP.
- **Alternativas:** Identidad declarada en argumentos (insegura); identidad fija por
  proceso (impide multiplexar usuarios); autenticación HTTP (no cubre stdio).
- **Contrato y plan:** `docs/aud-03-auth-stdio.md`. Integración PR #17 pendiente.
