# Entrega 3 · Asistente con RAG y MCP (Caso MIRA)
**Taller de Desarrollo de Software Conducido por Agentes de IA**  
**Escuela de Ingeniería Informática — Universidad de Valparaíso**  
**Fecha de Entrega:** Lunes 9 de noviembre de 2026, 14:00 hrs.  
**Modalidad:** Grupal (3 o 4 integrantes)  
**Evaluación:** 50% Informe escrito + Repositorio | 50% Presentación oral + Demostración en vivo (15 min presentación + 5 min preguntas)

---

## 1. Estado de Avance y Situación Actual

1. **Descompresión de Archivos Base:**  
   Se descomprimió exitosamente el archivo `Kit_Entrega_3_MIRA.zip` dentro del directorio `archivos-base/Kit_Entrega_3_MIRA/`.
2. **Archivos Base Disponibles:**
   - `archivos-base/Entrega_3_MIRA_RAG_MCP.pdf`: Documento oficial de especificaciones, requisitos y rúbrica de evaluación.
   - `archivos-base/Kit_Entrega_3_MIRA/`: Contiene los 4 casos de uso disponibles (`CU-1`, `CU-2`, `CU-3`, `CU-4`), cada uno con su corpus documental (`corpus/`) y su base de datos relacional simulada en Excel (`datos/`).

---

## 2. Resumen de los Archivos Entregados (`archivos-base`)

El kit proporciona cuatro casos de uso autocontenidos sobre la plataforma ficticia **MIRA** (*DPRIME SpA*). Cada equipo debe elegir **un solo caso de uso** para implementar.

### Comparativa de Casos de Uso Disponibles

| Caso de Uso | Usuario Objetivo | Necesidad Principal | Corpus Documental (`corpus/`) | Tablas Base de Datos (`datos/*.xlsx`) | Tools MCP Sugeridas |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CU-1: Asistente del operador de revisión** | Operador de una organización cliente que revisa casos no resueltos por MIRA | Entender por qué un caso fue derivado y qué regla lo explica, sin abrir otros sistemas | • `POL-DEC_v1_derogada.md`<br>• `POL-DEC_v2_vigente.md`<br>• `PRO-ANT_solicitud_antecedentes.md`<br>• `CAT-SEN_catalogo_senales.md`<br>• `MAN-REV_manual_revision_asistida.md`<br>• `FAQ-OPE_preguntas_frecuentes_operadores.md` | • `LEEME`<br>• `organizaciones`<br>• `usuarios`<br>• `casos`<br>• `senales`<br>• `evidencias`<br>• `solicitudes_antecedentes`<br>• `cambios_umbral` | **Lectura:**<br>`buscar_reglas`<br>`consultar_caso`<br>`listar_senales`<br><br>**Escritura:**<br>`solicitar_antecedentes` |
| **CU-2: Asistente de soporte y operación** | Equipo de soporte y operación de DPRIME | Diagnosticar un caso detenido o con error y reprocesarlo sin escalar a ingeniería | • `CAT-ERR_v1_derogado.md`<br>• `CAT-ERR_v2_vigente.md`<br>• `GUI-COL_colas_servicios_externos.md`<br>• `PRO-MAN_mantencion.md`<br>• `POL-ACC_acceso_evidencia.md`<br>• `MAN-INC_manual_incidentes.md` | • `LEEME`<br>• `organizaciones`<br>• `usuarios`<br>• `servicios`<br>• `casos`<br>• `registro_tecnico`<br>• `reprocesos`<br>• `autorizaciones_acceso`<br>• `incidentes` | **Lectura:**<br>`buscar_reglas`<br>`estado_servicios`<br>`consultar_caso`<br><br>**Escritura:**<br>`reprocesar_caso` |
| **CU-3: Asistente de incorporación** | Equipo de implementación de DPRIME | Saber qué le falta a una organización nueva para pasar a producción a partir de su plantilla | • `GUI-INC_v1_derogada.md`<br>• `GUI-INC_v2_vigente.md`<br>• `FIC-PLA_fichas_plantillas.md`<br>• `REQ-INT_requisitos_integracion.md`<br>• `POL-FOR_formularios_propios.md` | • `LEEME`<br>• `organizaciones`<br>• `usuarios`<br>• `plantillas`<br>• `tareas`<br>• `integraciones`<br>• `formularios_propios` | **Lectura:**<br>`buscar_reglas`<br>`checklist_organizacion`<br>`listar_plantillas`<br><br>**Escritura:**<br>`marcar_tarea` |
| **CU-4: Asistente de módulos y consumo** | Área comercial y de administración de DPRIME | Explicar el consumo de una organización, su tramo de cobro y el efecto de activar un módulo | • `ANX-TAR_v1_derogado.md`<br>• `ANX-TAR_v2_vigente.md`<br>• `CON-COM_condiciones_comerciales.md`<br>• `FIC-MOD_fichas_modulos.md`<br>• `DEF-VAL_definicion_validacion.md` | • `LEEME`<br>• `organizaciones`<br>• `usuarios`<br>• `modulos`<br>• `modulos_activos`<br>• `consumo_mensual`<br>• `detalle_casos`<br>• `solicitudes_activacion` | **Lectura:**<br>`buscar_reglas`<br>`modulos_activos`<br>`consumo_mes`<br><br>**Escritura:**<br>`solicitar_activacion` |

> **Advertencia crítica sobre el corpus entregado:**  
> El material reproduce condiciones empresariales complejas intencionales: incluye documentos derogados coexistiendo con vigentes, contradicciones entre documentos y con los datos de la base de datos, preguntas sin respuesta en las fuentes y contenido con posibles manipulaciones/inyecciones. El asistente debe saber identificar y resolver estas condiciones según los principios del proyecto.

---

## 3. Requisitos Clave del Entregable (PDF)

### 3.1 Objetivo y Filosofía Central: Evidencia y Control
El asistente no se evalúa por qué tan bien conversa, sino por su **fidelidad a la evidencia y control estricto**:
- Cada afirmación sobre reglas debe tener una fuente verificable (RAG).
- Cada dato específico sobre una entidad o caso debe provenir de una llamada MCP trazable y registrada.
- El asistente debe reconocer y admitir explícitamente cuando algo no está en su conocimiento.
- **Ninguna acción con efecto (escritura/mutación) puede ocurrir sin confirmación explícita de un humano (Human-in-the-Loop).**

### 3.2 Principios No Negociables del Asistente (PR-1 al PR-7)
1. **PR-1 (Decisión humana):** El asistente no decide sobre un caso. Explica, sugiere y prepara; la decisión final la confirma una persona.
2. **PR-2 (Citas obligatorias):** Toda afirmación sobre reglas, políticas o contratos cita el fragmento que la respalda (fuente, sección y versión). Sin cita, no se afirma.
3. **PR-3 (Abstención):** Si la respuesta no está en el corpus, el asistente lo dice explícitamente. La ausencia de evidencia jamás se presenta como respuesta favorable.
4. **PR-4 (Conflicto entre fuentes vigentes):** Si dos fuentes vigentes se contradicen, el asistente expone ambas posturas y no toma partido por su cuenta.
5. **PR-5 (Datos vivos vía MCP):** Todo dato sobre un caso debe provenir de una herramienta MCP visible en la interfaz; el LLM jamás inventa ni extrapola datos.
6. **PR-6 (Acciones con confirmación):** Las acciones que modifiquen el estado del sistema requieren confirmación explícita del usuario. Las consultas nunca deben producir efectos secundarios.
7. **PR-7 (Control de acceso por rol):** El asistente solo permite acceder a los datos que el usuario conectado tiene permitido ver según su rol y organización.

---

## 4. Arquitectura y Componentes a Implementar

### 4.1 Componente RAG
- **Corpus:** Indexar los documentos Markdown del caso elegido conservando metadatos estructurados en cada chunk: `código`, `versión`, `estado`, `vigencia` y `sección`.
- **Pipeline Desacoplado:** Separación estricta entre proceso de indexación (offline/batch) y proceso de consulta (runtime).
- **Experimentación:** Justificación empírica/comparativa de la estrategia de fragmentación (tamaño de chunk, solapamiento) y de la búsqueda vectorial/híbrida.
- **Manejo de Versiones:** Diferenciar documentos vigentes de derogados, priorizando la norma vigente e indicando el cambio si corresponde.

### 4.2 Componente Servidor MCP (Model Context Protocol)
- **Servidor MCP propio:** Expone tools de lectura y escritura conectadas a la base de datos (cargada a partir del Excel del caso).
- **Consultas parametrizadas:** Todo acceso a la base de datos es mediante queries parametrizadas programadas en el servidor. El LLM nunca genera código SQL libre.
- **Validación de reglas en el servidor:** Las restricciones de negocio (permisos, roles, límites como máximo de solicitudes) se validan en el backend antes de escribir. Si se incumple una regla, el servidor retorna un error explicativo entendible para el usuario.

### 4.3 Frontend y Backend
- **Frontend Web (en español):**
  - Chat conversacional con el asistente.
  - Indicadores visuales claros de:
    - Cuándo responde con evidencia documental.
    - Cuándo se abstiene por falta de información.
    - Cuándo detecta un conflicto entre fuentes vigentes.
  - Despliegue de citas (fuente, sección, versión) y trazas de las llamadas MCP ejecutadas.
  - Interfaz de confirmación explícita para acciones con efecto colateral.
  - Mensajes de error claros ante caídas de servicios sin alucinaciones.
- **Backend:**
  - API orquestadora que decide si requiere RAG, MCP o ambos.
  - Integración del cliente MCP y del motor RAG.

---

## 5. Evaluación y Golden Set

### 5.1 Golden Set del RAG (Mínimo 20 preguntas)
Debe crearse y **versionarse en git antes de la primera corrida completa** para evitar sobreajuste:
- **12 preguntas** con respuesta en el corpus (debe responder y citar el fragmento exacto).
- **4 preguntas** sin respuesta en el corpus (debe abstenerse e indicar qué falta).
- **2 preguntas** con conflicto entre fuentes vigentes (debe presentar ambas fuentes sin elegir).
- **2 preguntas** con respuesta distinta entre versiones (debe responder con la versión vigente e indicar la diferencia).

### 5.2 Métricas de Rendimiento a Reportar
- **Recuperación:** `Recall@k` (a nivel de fragmento/chunk).
- **Generación:** 
  - `Precisión de cita`: proporción de citas que realmente respaldan lo dicho.
  - `Fidelidad (Groundedness)`: proporción de afirmaciones respaldadas por la evidencia recuperada.
- **Comportamiento:**
  - `Abstención correcta`: precisión en detectar ausencia de información sin abstenerse indebidamente.
  - `Manejo de conflicto y vigencia`: tasa de éxito resolviendo contradicciones y versiones.
- **Clasificación de fallos:** Distinguir formalmente si cada error fue **fallo de recuperación** o **fallo de generación**.

### 5.3 Riesgos y Guardrails
- Configurar y probar un mínimo de **3 riesgos con sus respectivos guardrails** (por ejemplo: inyección de instrucciones en documentos o preguntas, intentos de saltarse confirmaciones de escritura, fuga de datos entre organizaciones).

---

## 6. Estructura del Informe Escrito (Máximo 12 planas)

| Sección | Extensión Máxima | Contenido Clave |
| :--- | :--- | :--- |
| **11.1 Resumen ejecutivo** | 1/2 plana | Qué hace, para quién, desempeño con métricas claras, limitaciones y recomendaciones (sin jerga técnica excesiva). |
| **11.2 Caso de uso y especificación** | 1,5 planas | Justificación del caso, contradicción del corpus identificada, flujos principal/alternativos, clasificación RAG vs MCP, trazabilidad con IDs. |
| **11.3 Diseño e implementación del RAG** | 2 planas | Inventario del corpus, chunking comparado experimentalmente, pipeline reproducible, indexación separada, formato de citas, vigencia y conflictos. |
| **11.4 Diseño e implementación del servidor MCP** | 1,5 planas | Primitivas de lectura y escritura, validaciones de reglas de negocio en servidor, contratos de tools, errores informados. |
| **11.5 Arquitectura e implementación Front y Back** | 1,5 planas | Diagramas de arquitectura y secuencia, datos enviados al modelo, trazabilidad en UI, honestidad del agente ante fallos. |
| **11.6 Evaluación** | 3 planas | Golden set, métricas (Recall@k, Fidelidad, Precisión de citas, Abstención), matriz de fallos recuperación vs generación, ciclo de mejora. |
| **11.7 Riesgos y controles** | 1 plana | Identificación de mínimo 3 riesgos de seguridad/operación y configuración de guardrails/controles con pruebas. |
| **11.8 Discusión y conclusiones** | 1 plana | Reflexión crítica de qué resolvió cada componente, qué quedó fuera, aprendizajes transferibles y trabajo futuro. |

---

## 7. Rúbrica y Demostración en Vivo

### Ponderaciones Oficiales
- **Informe y Repositorio (50%):**
  - C1: Resumen ejecutivo (3%)
  - C2: Caso de uso y especificación (6%)
  - C3: RAG (10%)
  - C4: Servidor MCP (10%)
  - C5: Frontend y Backend (6%)
  - C6: Evaluación (10%)
  - C7: Riesgos y controles (3%)
  - C8: Discusión y conclusiones (2%)
- **Presentación Oral (50%):**
  - P1: Exposición (10%)
  - P2: Demostración en vivo (20%) — *Debe recorrer los 8 momentos clave: cita abierta, abstención, conflicto de fuentes, traza de tool, efecto verificado en DB, riesgo contenido por guardrail, cliente externo y pregunta no prevista.*
  - P3: Defensa técnica de la evaluación (10%)
  - P4: Respuestas individuales (10%)

---

## 8. Siguientes Pasos Sugeridos

1. **Definir el Caso de Uso a implementar:** Elegir entre `CU-1`, `CU-2`, `CU-3` o `CU-4`.
2. **Definir el Stack Tecnológico:**
   - Base de datos (ej. SQLite / PostgreSQL) para migrar las tablas del Excel seleccionado.
   - Vector Store (ej. ChromaDB / FAISS / Qdrant) y modelo de embeddings.
   - Framework para el Servidor MCP (ej. MCP SDK oficial en Python o TypeScript / FastMCP).
   - Backend / Orquestador (FastAPI, Python).
   - Frontend (React + Vite o similar con soporte para trazas, Markdown y citas).
3. **Armar el Golden Set inicial (20 preguntas) y versionarlo en Git.**
