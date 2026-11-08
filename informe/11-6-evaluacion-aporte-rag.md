# 11.6 Evaluación: aporte de RAG y golden set (borrador)

> Insumo de Ángel Salgado para la sección 11.6 (3 planas en total), 2026-11-07. Las cifras de **generación** quedan **PENDIENTES** hasta que `tests/evaluation/eval_goldenset.py` se ejecute contra el backend integrado. No se deben completar a mano.

## Estrategia de pruebas (capas)

| Capa | Qué verifica | Dónde | Necesita LLM |
|---|---|---|---|
| Integridad de datos de prueba | Golden set con la composición de la pauta y anclas literales únicas; corpus idéntico al ZIP del kit | `tests/unit/test_goldenset.py`, `backend/rag/verify_corpus.py` | No |
| Unitaria del RAG | Metadatos, fragmentación, BM25/RRF, vigencia y validador de citas | `tests/unit/test_rag_chunker.py`, `test_vigencia.py`, `test_citations.py` | No |
| Integración RAG/MCP | Indexación reproducible, contrato de `buscar_reglas`, conflictos y abstención en la recuperación, protocolo MCP real | `tests/integration/` | No |
| Recuperación | Recall@k a nivel de fragmento y MRR; experimento de fragmentación | `tests/evaluation/eval_recuperacion.py` | No |
| De punta a punta | Precisión de cita, abstención, conflicto y vigencia, clasificación de fallos | `tests/evaluation/eval_goldenset.py` | Sí |

## Golden set (v1.0, fijado antes de la primera corrida)

22 casos:
- 13 con respuesta;
- 4 sin respuesta, diseñados como trampas cercanas al corpus (por ejemplo, una plantilla inexistente);
- 2 conflictos entre documentos vigentes;
- 2 cambios de versión;
- 1 conflicto documento-datos que requiere MCP.

Las respuestas esperadas están **pendientes de validación del cliente**.

## Resultados de recuperación (configuración elegida)

| Métrica | Valor |
|---|---|
| Recall@1 / @3 / @4 (con respuesta, n = 13) | 0.69 / 0.92 / **1.00** |
| MRR | 0.81 |
| Recall@4 de fragmentos en conflicto (n = 4 fragmentos) | 0.75 |
| Recall@4 en cambio de versión (n = 2) | 1.00 |
| Versión derogada recuperada con `filtro_vigencia="todas"` | 2 / 2 |

Fuente: `tests/evaluation/resultados/recuperacion_20261107-025237.md`.

## Análisis de fallos (recuperación)

| Caso | Fallo | Clase | Causa | Acción |
|---|---|---|---|---|
| GS-03 (línea base densa) | No recupera la ficha PLA-CTA | Recuperación | El embedding no representa bien el código y el nombre de la plantilla | Búsqueda híbrida (corregido) |
| GS-10 (línea base densa) | Fila E3 en el puesto 9 | Recuperación | Contenido en tabla y término exacto «E3» | Búsqueda híbrida (corregido) |
| GS-18 | `FIC-PLA v1 §1` fuera del top-10 | Recuperación | La pregunta no comparte términos con «sin necesidad de ejemplos»; el stemming solo lo sube al puesto 9 | Pendiente; el asistente puede no detectar el conflicto C-1 |
| GS-14 a GS-17 | El umbral no los descarta (similitud 0.44 a 0.56) | Límite del diseño | Las trampas están cerca del dominio | La abstención la decide el orquestador; se mide en la corrida de punta a punta |

## Resultados de generación

**PENDIENTE.** Requiere `POST /api/chat` (T020 y T021). Comando:

```bash
uv run python -m tests.evaluation.eval_goldenset
```

El script produce el JSON de métricas y la planilla `*_revision_manual.csv` para juzgar a mano la fidelidad. Si se usa un modelo evaluador, se revisa a mano una muestra y se informa la concordancia (pauta §7.2).
