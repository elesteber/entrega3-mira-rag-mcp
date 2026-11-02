# Plan de Evaluación del Asistente y Diseño del Golden Set (CU-3)

Este documento detalla la metodología de evaluación cuantitativa y cualitativa del sistema RAG + MCP para el **Caso de Uso CU-3**, en cumplimiento del capítulo 7 y la rúbrica de la Entrega 3.

---

## 1. Metodología del Golden Set del RAG

### 1.1 Composición Obligatoria (Mínimo 20 Preguntas)
La pauta exige una lista fija de al menos 20 preguntas redactadas por el equipo con la siguiente estructura:

| Tipo de Pregunta | Mínimo | Comportamiento Esperado del Sistema |
|---|---|---|
| **Con respuesta en el corpus** | 12 | Responde correctamente y cita el fragmento exacto con fuente, sección y versión. |
| **Sin respuesta en el corpus** | 4 | Se abstiene explícitamente y explica qué información falta (PR-3). |
| **Con conflicto entre fuentes vigentes** | 2 | Expone ambas posturas o discrepancias vigentes sin elegir arbitrariamente (PR-4). |
| **Con respuesta distinta entre versiones** | 2 | Responde con la versión vigente (`v2`) e indica la derogación de la previa (`v1`). |

### 1.2 Regla de Oro de Versionado
> **REQUISITO FORMAL:** El archivo definitivo del Golden Set (`tests/golden_set.json`) debe quedar **versionado en un commit de Git ANTERIOR a la primera ejecución completa del pipeline de evaluación**, asegurando que los casos no se sobreajusten artificialmente a las respuestas del modelo.

---

## 2. Propuesta Inicial de Candidatos para el Golden Set (CU-3)

A continuación se presentan 20 preguntas candidatas preliminares derivadas del análisis documental y del modelo de datos:

### 2.1 Con respuesta en el corpus (12 candidatas)
1. *¿Cuáles son los seis criterios que debe cumplir una organización para salir a producción?*  
   - Esperado: Cita `GUI-INC v2 §3`.
2. *¿Quién es el único autorizado para marcar la tarea de salida a producción (E5)?*  
   - Esperado: Cita `GUI-INC v2 §4` (Jefe de implementación).
3. *¿Qué módulos y qué industria contempla la plantilla PLA-CTA?*  
   - Esperado: Cita `FIC-PLA v1 §2` (Banca; OCR, ROS, VID, QR).
4. *¿Por qué la plantilla PLA-ADM requiere autorización de tratamiento de datos biométricos?*  
   - Esperado: Cita `FIC-PLA v1 §2` (contempla comparación de rostros MOD-ROS).
5. *¿Cuáles son los tres modos de integración técnica soportados y cuál es el modo por defecto?*  
   - Esperado: Cita `REQ-INT v2 §1` (API asincrónica por defecto, API sincrónica y archivos).
6. *¿Qué condiciones deben cumplirse para que una prueba de integración se considere exitosa?*  
   - Esperado: Cita `REQ-INT v2 §5` (al menos 20 casos exitosos con callback y máx 100 llamadas/min).
7. *¿Cuál es el límite general de llamadas por minuto por organización en MIRA?*  
   - Esperado: Cita `REQ-INT v2 §3` (1.000 llamadas/minuto).
8. *¿Cuántos ejemplos de un formulario propio debe entregar la organización y cuánto toma su ajuste?*  
   - Esperado: Cita `POL-FOR v1 §2` (20 a 30 ejemplos; 10 a 15 días hábiles).
9. *¿Qué ocurre con los casos que incluyen un formulario propio mientras este se encuentra en ajuste?*  
   - Esperado: Cita `POL-FOR v1 §3` (derivación a revisión asistida).
10. *¿En qué etapa de la incorporación se debe realizar la prueba de integración y en qué días?*  
    - Esperado: Cita `GUI-INC v2 §2` (Etapa E3, días 1 a 8 desde la firma).
11. *¿Cuántos días hábiles de adaptación se estiman para la plantilla PLA-SIN?*  
    - Esperado: Cita `FIC-PLA v1 §2` (5 días hábiles).
12. *¿Bajo qué condiciones se pueden usar datos reales de la organización fuera de producción?*  
    - Esperado: Cita `REQ-INT v2 §4` (solo con autorización expresa y datos enmascarados).

### 2.2 Sin respuesta en el corpus / Abstención (4 candidatas)
13. *¿Cuál es la tarifa por llamada excedente en el ambiente de integración?*  
    - Esperado: Abstención. El corpus técnico de CU-3 no define tarifas (PR-3).
14. *¿Cuál es el procedimiento técnico para migrar una base de datos On-Premise a MIRA Cloud?*  
    - Esperado: Abstención. No existe en el corpus de incorporación.
15. *¿Qué sanciones legales aplican si se vulnera la privacidad de datos biométricos en Perú?*  
    - Esperado: Abstención. El corpus no describe legislación penal extranjera.
16. *¿Qué modelo específico de red neuronal convolucional utiliza el módulo MOD-ROS?*  
    - Esperado: Abstención. La arquitectura interna del modelo no figura en las fichas.

### 2.3 Con conflicto / discrepancia entre fuentes vigentes (2 candidatas)
17. *¿Cuál es el umbral de aprobación sugerido para la plantilla de admisión clínica PLA-ADM?*  
    - Esperado: El asistente expone la discrepancia: la ficha documental `FIC-PLA §2` declara **85**, mientras que el registro de la base de datos de plantillas tiene **80** (PR-4).
18. *¿Se puede considerar aprobada una integración que procesó 20 casos pero alcanzó 240 llamadas por minuto?*  
    - Esperado: El asistente expone que cumple con los 20 casos pero viola el criterio de carga de `REQ-INT §5` (máximo 100 llamadas/min).

### 2.4 Con respuesta distinta entre versiones (2 candidatas)
19. *¿Cuánto tiempo toma la incorporación completa de una organización a MIRA según la guía?*  
    - Esperado: Responde con la versión vigente `GUI-INC v2 §1` (meta de 10 días hábiles) e indica que la versión 1 (derogada) estipulaba de 6 a 8 semanas.
20. *¿Quién autoriza la salida a producción de una organización?*  
    - Esperado: Responde con la versión vigente `GUI-INC v2 §4` (exclusivo del jefe de implementación) e indica que en la versión 1 derogada bastaba la conformidad del ingeniero a cargo.

---

## 3. Métricas de Evaluación Operativa

| Etapa | Métrica | Definición Operativa | Meta Propuesta |
|---|---|---|---|
| **Recuperación** | `Recall@k` | Proporción de preguntas con respuesta cuyo fragmento esperado aparece entre los $k$ chunks recuperados (a nivel de chunk). | $\ge 90\%$ ($k=4$) |
| **Generación** | `Precisión de Cita` | Proporción de citas emitidas que apuntan a un fragmento que efectivamente respalda la afirmación. | $\ge 95\%$ |
| **Generación** | `Fidelidad (Groundedness)` | Proporción de respuestas cuyas afirmaciones están respaldadas en la evidencia recuperada sin alucinaciones. | $\ge 95\%$ |
| **Comportamiento** | `Abstención Correcta` | Tasa de preguntas sin respuesta en las que el sistema se abstiene debidamente, sin abstenerse de preguntas respondibles. | $100\%$ |
| **Comportamiento** | `Manejo de Conflicto/Vigencia`| Proporción de preguntas de versiones y conflictos resueltas exponiendo ambas posturas y priorizando normas vigentes. | $100\%$ |

---

## 4. Estrategia de Experimentación de Chunking

Para cumplir con el criterio **C3 de la rúbrica**, se compararán experimentalmente dos estrategias de fragmentación sobre el Golden Set:
- **Estrategia A (Semántica por Encabezados Markdown):** Fragmentación por secciones lógicas (`#`, `##`, `###`), conservando títulos jerárquicos como prefijo de contexto.
- **Estrategia B (Tamaño Fijo con Overlap):** Fragmentos de 200 tokens con 50 tokens de solapamiento.
- Se medirá el impacto directo en `Recall@k` y `Precisión de Cita` para justificar empíricamente la elección en el informe final.

---

## 5. Preparación de la Demostración en Vivo (Pasos D1 a D8)

Para alcanzar el puntaje máximo en el criterio **P2 (Demostración en vivo 20%)**, el guion de presentación cubrirá los 8 momentos clave:
1. **D1 (Cita abierta):** Respuesta con cita detallada (documento, versión, sección).
2. **D2 (Abstención):** Demostración de reconocimiento de falta de evidencia.
3. **D3 (Conflicto):** Exposición de divergencia entre norma y dato (caso umbral PLA-ADM).
4. **D4 (Traza MCP visible):** Inspección de llamadas en la UI web.
5. **D5 (Efecto verificado en DB):** Ejecución de mutación confirmada por humano y reflejada en SQLite.
6. **D6 (Riesgo contenido):** Bloqueo de la prompt injection presente en `T-008` o rechazo de mutación no autorizada.
7. **D7 (Cliente externo / Roles):** Demostración del aislamiento entre ejecutivos (PR-7).
8. **D8 (Pregunta no prevista):** Respuesta honesta y fundamentada ante una pregunta del público/evaluador.
