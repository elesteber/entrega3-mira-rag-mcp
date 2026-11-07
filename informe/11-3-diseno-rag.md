# 11.3 Diseño e implementación del RAG (borrador)

> Borrador de Ángel Salgado, 2026-11-07, sujeto a revisión del equipo. Extensión objetivo: 2 planas. Todas las cifras provienen de `tests/evaluation/resultados/recuperacion_20261107-025237.md`.

## Corpus

El corpus está formado por los cinco documentos del kit del CU-3, todos obligatorios. No se agregaron documentos propios. De cada documento se toman del encabezado su código, versión, estado y vigencia, y esos datos se guardan como metadatos de cada fragmento.

| ID | Título | Origen | Versión | Estado | Vigencia | Tokens* | Fragmentos |
|---|---|---|---|---|---|---|---|
| GUI-INC | Guía de incorporación de organizaciones | kit | 2 | Vigente | Desde 01-09-2026 | 691 | 5 |
| GUI-INC | Guía de incorporación de organizaciones | kit | 1 | **Derogada** | 01-11-2025 al 31-08-2026 | 329 | 3 |
| FIC-PLA | Fichas de plantillas por caso de uso | kit | 1 | Vigente | Desde 01-09-2026 | 566 | 6 |
| REQ-INT | Requisitos técnicos de integración | kit | 2 | Vigente | Desde 01-09-2026 | 484 | 6 |
| POL-FOR | Política de formularios propios | kit | 1 | Vigente | Desde 01-09-2026 | 293 | 4 |

\*Tokens contados con el tokenizador del modelo de embeddings.

Al auditar el corpus se encontraron dos contradicciones entre fuentes vigentes:
- `FIC-PLA v1 §1` dice que las plantillas reconocen cualquier documento «sin necesidad de ejemplos», mientras que `POL-FOR v1 §2` exige entre 20 y 30 ejemplos por cada formulario propio.
- `GUI-INC v2 §1` fija la producción en diez días hábiles, pero el ajuste de un formulario propio toma entre 10 y 15 días (`POL-FOR v1 §2`) y el criterio 6 de `GUI-INC v2 §3` exige que todos los formularios estén operativos.

Aparte de esas dos, hay una discrepancia entre un documento y los datos: el umbral de PLA-ADM es 85 en la ficha y 80 en la base de datos.

## Pipeline: indexación y consulta separadas

- **Indexación offline** (`backend/rag/index_corpus.py`): lee, fragmenta, vectoriza con `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensiones, CPU) y persiste en ChromaDB con similitud coseno. Cada ejecución reconstruye la colección desde cero. Los `chunk_id` son deterministas (`GUI-INC-V2-SEC3-P1`) y se guarda una huella SHA-256 del corpus, así que dos ejecuciones producen el mismo índice (lo verifica una prueba automatizada).
- **Consulta** (`backend/rag/retriever.py`): la función `buscar_reglas(query, top_k=4, filtro_vigencia)` se expone como herramienta MCP. No invoca al LLM, por lo que la misma función se evalúa de forma aislada.

## Fragmentación y búsqueda elegidas por experimento

Se compararon 10 configuraciones con el golden set: fragmentación por encabezados frente a tamaño fijo (150/40 y 60/15 palabras), límite de 128 frente a 256 tokens, y búsqueda densa frente a híbrida. Recall@k se mide a nivel de fragmento: un acierto exige que el fragmento recuperado contenga la cita literal esperada.

| Configuración | Recall@1 | Recall@4 | MRR | Fragmentos truncados |
|---|---|---|---|---|
| Encabezados, 128, denso (línea base) | 0.77 | 0.85 | 0.82 | 11 / 24 |
| **Encabezados, 256, híbrido** | 0.69 | **1.00** | 0.81 | 0 / 24 |
| Fijo 150/40, 256, híbrido | 0.62 | 1.00 | 0.76 | 4 / 14 |
| Fijo 60/15, 128, denso | 0.54 | 0.69 | 0.64 | 1 / 36 |

**Decisión.** Se fragmenta por encabezados: una sección `##` por fragmento, y en `FIC-PLA §2` una plantilla por fragmento. Las razones:
- El modelo trunca a 128 tokens por defecto y eso dejaba incompletas 11 de las 24 secciones. Con 256 tokens no se trunca ninguna.
- Cada fragmento coincide con una sección, así que la cita es exacta. Los fragmentos de tamaño fijo cruzan secciones (`§2–§3`) y vuelven ambigua la cita.

**Búsqueda híbrida.** La búsqueda densa sola no encontraba la ficha de `PLA-CTA` ni la fila de la etapa `E3`, porque los embeddings pierden los códigos exactos. BM25 los recupera por coincidencia literal. Ambos rankings se combinan con *Reciprocal Rank Fusion* (k = 60, el valor estándar, sin ajustar).

## Citas, vigencia y conflictos

- **Citas.** Cada resultado trae `chunk_id`, `doc_code`, `section`, `version`, `status` y el texto literal. El orquestador cita con esos campos (PR-2) y la interfaz muestra el fragmento.
- **Vigencia.** Por defecto, `filtro_vigencia="vigente"` excluye `GUI-INC v1`. En las preguntas de cambio de versión se usa `"todas"` para mencionar la versión derogada como histórica. Recall@4 de versión: 1.00.
- **Conflictos.** La búsqueda devuelve fragmentos de varios documentos y el modelo debe presentar ambas posturas (PR-4). Recall@4 de los fragmentos de conflicto: 0.75. Falla `GS-18`, que no recupera `FIC-PLA v1 §1`.
- **Abstención.** Si ningún fragmento alcanza una similitud de 0.35, `buscar_reglas` devuelve una lista vacía. El experimento mostró que esta señal no basta para abstenerse: la mayor similitud de una pregunta sin respuesta fue 0.56, mientras que la de una pregunta con respuesta bajó a 0.45. Por eso la abstención la decide el orquestador, que comprueba si los fragmentos responden la pregunta (PR-3).

## Limitaciones

- La configuración se eligió con el mismo golden set con que se mide, porque no hay un conjunto separado.
- Las preguntas del golden set comparten vocabulario con el corpus, lo que favorece a BM25.
- Está pendiente decidir si se agregan capítulos de la Descripción de MIRA al corpus (opcional según la pauta §4.1).
