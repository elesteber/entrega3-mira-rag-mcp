# Suite de Pruebas y Evaluación MIRA CU-3

Este directorio alojará la batería de pruebas automatizadas y el framework de evaluación cuantitativa del asistente RAG + MCP.

> **Estado actual:** PREPARACIÓN DOCUMENTAL PREVIA A SPEC KIT.  
> Los casos de prueba automatizados y scripts de evaluación se implementarán una vez definidos los contratos y especificaciones.

---

## 1. Componentes Planificados

- **`evaluation/goldenset_cases.json`:** Conjunto fijo de al menos 20 preguntas redactadas para evaluar el CU-3:
  - 12 preguntas con respuesta en el corpus (con fragmento esperado y cita exacta).
  - 4 preguntas sin respuesta en el corpus (evaluación de abstención correcta).
  - 2 preguntas con conflicto entre fuentes vigentes (evaluación de presentación imparcial).
  - 2 preguntas con respuestas distintas entre versiones (v1 derogada vs v2 vigente).
  - *Nota obligatoria:* El golden set definitivo debe versionarse en Git **antes** de la primera corrida completa del pipeline para evitar sesgos de sobreajuste.
- **Pruebas de Recuperación y Generación (RAG Evaluation):**
  - Cálculo de `Recall@k` a nivel de fragmento/chunk.
  - Cálculo de `Precisión de Cita` (citas válidas que sustentan la afirmación).
  - Cálculo de `Fidelidad / Groundedness` (ausencia de afirmaciones no sustentadas).
  - Matriz de clasificación de fallos: diferenciar formalmente fallos de recuperación vs fallos de generación.
- **Pruebas Unitarias e Integración MCP:**
  - Validación de consultas parametrizadas.
  - Validación de reglas de negocio en servidor (ej: rechazo si no se es supervisor/jefe, límites de tareas, estados inválidos).
  - Verificación de que ninguna consulta de lectura modifica la base de datos.
- **Pruebas de Guardrails y Seguridad:**
  - Pruebas contra inyección de instrucciones (ej: nota de la tarea T-008 en `tareas`).
  - Pruebas de control de acceso por rol y organización asignada (PR-7).

---

## 2. Próximos Pasos

1. Consensuar con el equipo las 20 preguntas del Golden Set en `docs/plan-evaluacion.md`.
2. Implementar los scripts de benchmarking con `pytest`.
