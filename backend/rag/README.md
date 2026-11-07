# RAG del CU-3 (`backend/rag/`)

Responsable: Ángel Salgado. Indexación y consulta están separadas (pauta §6.2).

| Archivo | Fase | Qué hace |
|---|---|---|
| `indexer.py` | Indexación | Lee los 5 `.md` del kit, extrae metadatos del encabezado, fragmenta, vectoriza y persiste en ChromaDB. |
| `index_corpus.py` | Indexación | CLI que reconstruye el índice desde cero (reproducible). |
| `retriever.py` | Consulta | `Recuperador` y `buscar_reglas(query, top_k=4, filtro_vigencia="vigente")` según `contracts/mcp-tools.json`. |
| `lexico.py` | Consulta | BM25 y fusión RRF para la búsqueda híbrida. |

## Uso

```bash
uv sync                                       # instala dependencias (torch solo CPU)
uv run python -m backend.rag.index_corpus     # indexa en backend/data/chroma_db (ignorado por git)
uv run pytest                                 # pruebas unitarias + integración
uv run pytest -m "not modelo"                 # sin cargar el modelo de embeddings
uv run python -m tests.evaluation.eval_recuperacion   # experimento Recall@k
```

La primera ejecución descarga `paraphrase-multilingual-MiniLM-L12-v2` (~470 MB) a la caché de Hugging Face.
Si se reindexa con el servidor MCP corriendo, hay que reiniciar el servidor.

## Configuración elegida (ADR-10)

- **Fragmentación por encabezados**: un fragmento por sección `##`; FIC-PLA §2 se divide por plantilla (`###`). 24 fragmentos.
  `chunk_id` determinista: `GUI-INC-V2-SEC3-P1`. La sección del fragmento es la unidad de cita (PR-2).
- **`EMBEDDING_MAX_SEQ_LENGTH=256`**: con el valor por defecto del modelo (128) se truncaban 11 de 24 fragmentos.
- **Búsqueda híbrida** (`RAG_MODO_BUSQUEDA=hibrido`): ranking denso + BM25 fusionados con RRF (k=60).
- **Umbral por consulta** (`RAG_SCORE_THRESHOLD=0.35`): si ningún fragmento alcanza esa similitud, `results` viene vacío.
  El umbral **no** detecta las preguntas sin respuesta del golden set (la mayor similitud de una de ellas fue 0.56, mientras que la de una pregunta con respuesta bajó a 0.45). Por eso el orquestador debe abstenerse cuando los fragmentos no responden la pregunta, aunque `results` no venga vacío.

## Para integrar (MCP / orquestador)

```python
from backend.rag.retriever import buscar_reglas
buscar_reglas("¿Cuáles son los criterios de salida a producción?")
# {"total_found": 4, "results": [{"chunk_id": "GUI-INC-V2-SEC3-P1", "doc_code": "GUI-INC",
#   "doc_title": "...", "section": "§3", "version": "v2.0", "status": "vigente", "text": "...",
#   "similarity_score": 0.62}, ...]}
```

- Rodrigo: `backend/mcp/tools/rag_tools.py` solo debe registrar esta función como herramienta FastMCP.
- Lester: para preguntas de versión usar `filtro_vigencia="todas"` y citar la derogada como histórica; las citas deben usar `chunk_id`, `doc_code`, `section` y `version` del resultado.
