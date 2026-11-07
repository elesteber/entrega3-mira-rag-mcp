# Evaluación del asistente CU-3 (`tests/evaluation/`)

Responsable: Ángel Salgado.

| Archivo | Qué mide | Necesita |
|---|---|---|
| `goldenset_cases.json` | Golden set v1.0 (22 casos), fijado antes de la primera corrida | — |
| `eval_recuperacion.py` | Recall@k a nivel de fragmento, MRR, experimento de fragmentación (C3) | Solo el RAG |
| `eval_goldenset.py` | Precisión de cita, abstención, conflicto/vigencia y clasificación de fallos (C6) | Backend con `POST /api/chat` |
| `resultados/` | Salidas reales de cada corrida (JSON + Markdown); nunca se editan a mano | — |

```bash
uv run python -m tests.evaluation.eval_recuperacion
uv run python -m tests.evaluation.eval_goldenset --api http://localhost:8000/api   # con el backend levantado
```

---

## Auditoría de contradicciones del corpus (T061)

> **Estado: PENDIENTE DE VALIDACIÓN DOCENTE.** El equipo identificó las contradicciones de abajo leyendo el corpus del kit. Falta que el representante del cliente o el docente confirme que son las contradicciones que el kit contiene «sin señalarlas» (pauta §3.2).

La pauta (§7.1) pide 2 preguntas con **conflicto entre fuentes vigentes**. Se distinguen tres tipos de inconsistencia.

### A. Conflictos entre dos documentos vigentes del corpus (usados en el golden set)

| ID | Fuente 1 (vigente) | Fuente 2 (vigente) | Por qué se contradicen | Caso |
|---|---|---|---|---|
| C-1 | `FIC-PLA v1 §1`: «Todas las plantillas reconocen desde el primer día cualquier documento del proceso, sin necesidad de ejemplos de la organización.» | `POL-FOR v1 §2`: «La organización entrega entre 20 y 30 ejemplos del formulario…» | Un formulario propio es un documento del proceso, y POL-FOR exige ejemplos para leerlo. FIC-PLA afirma que no hacen falta. | GS-18 |
| C-2 | `GUI-INC v2 §1`: producción «dentro de diez días hábiles desde la firma». | `POL-FOR v1 §2`: «El ajuste de lectura toma entre 10 y 15 días hábiles desde que se reciben los ejemplos completos.» | Además, `GUI-INC v2 §3` (criterio 6) exige que todos los formularios propios estén «operativos». Una organización con un formulario propio no puede cumplir la meta de 10 días. | GS-19 |

Comportamiento esperado (PR-4): presentar ambas fuentes con su cita y no elegir; la resuelve una persona.

### B. Conflicto entre documento vigente y datos (no cuenta como «entre fuentes vigentes»)

| ID | Documento | Dato (MCP) | Caso |
|---|---|---|---|
| D-1 | `FIC-PLA v1 §2 (PLA-ADM)`: aprobación 85, revisión 60 | Tabla `plantillas`, `PLA-ADM`: `umbral_aprobacion_sugerido = 80` | GS-22 (`conflicto_documento_datos`, requiere MCP) |

Se mantiene separado porque la pauta habla de fuentes del corpus. El asistente debe exponer ambas cifras sin modificar el dato (FR-011).

### C. Cambios entre versiones (vigente vs derogada; no son conflictos)

| Tema | `GUI-INC v1` (derogada hasta 31-08-2026) | `GUI-INC v2` (vigente desde 01-09-2026) | Caso |
|---|---|---|---|
| Duración | Seis a ocho semanas (§1) | Diez días hábiles (§1) | GS-20 |
| Quién autoriza producción | El ingeniero a cargo (§2) | Solo el jefe de implementación marca E5 (§4) | GS-21 |

Comportamiento esperado: responder con la versión vigente e indicar que la anterior está derogada.

### Descartadas tras revisión

- `REQ-INT §3` (1.000 llamadas/minuto) vs `REQ-INT §5` (≤ 100 llamadas/minuto en la prueba): no se contradicen; son límites para contextos distintos, el general y el de la carga de prueba.
- `GUI-INC v2 §2` (E2 registra formularios propios en los días 1 a 5) vs `POL-FOR §2`: es parte de C-2, no un conflicto aparte.

---

## Resultados vigentes de recuperación

Última corrida: `resultados/recuperacion_20261107-025237.md`. La configuración elegida (encabezados, 256 tokens, híbrida) obtiene Recall@4 = 1.00 con respuesta, 0.75 en conflictos y 1.00 en versión. Fallo conocido: GS-18 no recupera C-1 / `FIC-PLA §1` (ver ADR-11).
