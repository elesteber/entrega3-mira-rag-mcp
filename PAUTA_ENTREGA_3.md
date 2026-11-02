# Entregable 3
## Asistente con RAG y MCP: evidencia documental y acceso gobernado al sistema
### Caso MIRA

**Taller de Desarrollo de Software Conducido por Agentes de IA**  
**Escuela de Ingeniería Informática**  
**Universidad de Valparaíso**  
**Facultad de Ingeniería**  

**Entrega:** lunes 9 de noviembre de 2026

| Campo | Detalle |
|---|---|
| **Actividad** | Diseño, construcción y evaluación de un caso de uso de MIRA en que un asistente responde con evidencia recuperada de documentos (RAG) y consulta o actúa sobre datos del sistema mediante un servidor MCP propio, con frontend y backend |
| **Caso de trabajo** | MIRA - Plataforma de inteligencia multimodal para decisiones empresariales, DPRIME SpA |
| **Fecha de entrega** | Lunes 9 de noviembre de 2026, 14:00 |
| **Integrantes por equipo** | 3 o 4 (mismo equipo de las entregas anteriores) |
| **Tiempo de presentación** | 15 minutos, con demostración en vivo incluida |
| **Tiempo de preguntas** | 5 minutos |
| **Entregables** | Informe escrito (PDF), repositorio con código, presentación oral |
| **Ponderación** | Informe y repositorio 50 % - Presentación oral y demostración 50 % |
| **Modalidad de evaluación** | Grupal |

---

## 1. Objetivo

### 1.1 Objetivo general

Diseñar, construir y evaluar un caso de uso de MIRA en que un asistente responde con evidencia recuperada de documentos (RAG, Retrieval-Augmented Generation) y consulta o actúa sobre un backend propio con datos simulados a través de un servidor MCP (Model Context Protocol) propio, con interfaz de usuario y servicios de backend, y demostrar que el equipo distingue cuándo una necesidad se resuelve con conocimiento documental, cuándo con datos vivos del sistema y cuándo con una acción que requiere permiso.

El énfasis de la actividad está en la **evidencia y el control**. No interesa que el asistente converse bien, sino que cada afirmación sobre una regla tenga una fuente verificable, que cada dato sobre un caso provenga de una llamada registrada, que el asistente reconozca lo que no sabe y que ninguna acción con efecto ocurra sin que una persona la confirme. En MIRA eso no es un detalle de implementación: el documento de DPRIME exige que toda decisión pueda justificarse ante un tercero, y un asistente que inventa una regla con tono convincente es exactamente el riesgo que el producto promete evitar.

---

## 2. Material de trabajo

El equipo trabaja sobre cinco insumos:
- **Descripción del proyecto MIRA, versión 1.4**, incluidas las entrevistas del capítulo 7.
- **Kit de la Entrega 3**, con una carpeta por caso de uso. Cada carpeta trae los documentos del corpus en Markdown (`corpus/`) y un Excel con las tablas de la base de datos que consulta el servidor MCP (`datos/`). La hoja LEEME de cada Excel describe sus tablas.
- **Informes, bitácora de decisiones y repositorio de las Entregas 1 y 2**, como referencia.
- **Retroalimentación recibida en la corrección de la Entrega 2**.
- **Material de la clase de RAG y MCP.** Los conceptos de indexación y consulta, golden set, separación entre recuperación y generación, primitivas MCP, criterios de evaluación de herramientas y riesgos se usan con el mismo significado que en la clase.

---

## 3. Caso de uso

### 3.1 Menú de casos de uso

El equipo implementa un **caso de uso nuevo**, elegido desde el siguiente menú. Los cuatro casos se plantean sobre MIRA como producto: el asistente debe servir a cualquier organización que opere en la plataforma, sea una aseguradora, un banco o una clínica. Por eso los datos de prueba usan organizaciones ficticias de al menos dos industrias distintas.

Los casos son autocontenidos: no dependen de las funcionalidades construidas en la Entrega 2, y cada uno trae acotado su usuario, su corpus, sus herramientas y sus datos. Cada caso exige las dos componentes: una respuesta documental sin RAG o una consulta al sistema sin MCP no cumple.

| ID | Caso de uso | Quién lo usa | Necesidad que atiende |
|---|---|---|---|
| **CU-1** | Asistente del operador de revisión | Operador de una organización cliente que revisa los casos que MIRA no resolvió sola | Entender por qué un caso fue derivado y qué regla lo explica, sin abrir otros sistemas |
| **CU-2** | Asistente de soporte y operación de la plataforma | Equipo de soporte y operación de DPRIME | Diagnosticar un caso detenido o con error y reprocesarlo sin escalar a ingeniería |
| **CU-3** | Asistente de incorporación de organizaciones | Equipo de implementación de DPRIME | Saber qué le falta a una organización nueva para pasar a producción a partir de su plantilla |
| **CU-4** | Asistente de módulos y consumo | Área comercial y de administración de DPRIME | Explicar el consumo de una organización, su tramo de cobro y el efecto de activar un módulo |

**Ejemplos de preguntas que el asistente debe poder responder combinando ambas componentes:**
- **CU-1:** «¿Por qué se derivó el caso C-012 si su puntaje es 86? ¿Qué dice la política de decisión?»
- **CU-2:** «El caso C-031 quedó detenido con el error E-207. ¿Qué significa y puedo reprocesarlo?»
- **CU-3:** «¿Qué le falta a la organización ORG-07 para pasar a producción con la plantilla de admisión clínica?»
- **CU-4:** «¿En qué tramo de cobro va la organización ORG-03 este mes y qué cambiaría si activa prueba de vida?»

**Lo que trae el kit para cada caso y las herramientas sugeridas:**

| ID | Documentos del corpus (kit) | Tablas de la base de datos (Excel) | Tools de lectura sugeridas | Tool de escritura sugerida |
|---|---|---|---|---|
| **CU-1** | POL-DEC (v1 y v2), MAN-REV, CAT-SEN, PRO-ANT, FAQ-OPE | organizaciones, usuarios, casos, senales, evidencias, solicitudes_antecedentes, cambios_umbral | buscar_reglas, consultar_caso, listar_senales | solicitar_antecedentes |
| **CU-2** | MAN-INC, CAT-ERR (v1 y v2), POL-ACC, GUI-COL, PRO-MAN | organizaciones, usuarios, servicios, casos, registro_tecnico, reprocesos, autorizaciones_acceso, incidentes | buscar_reglas, estado_servicios, consultar_caso | reprocesar_caso |
| **CU-3** | GUI-INC (v1 y v2), FIC-PLA, REQ-INT, POL-FOR | organizaciones, usuarios, plantillas, tareas, integraciones, formularios_propios | buscar_reglas, checklist_organizacion, listar_plantillas | marcar_tarea |
| **CU-4** | FIC-MOD, ANX-TAR (v1 y v2), DEF-VAL, CON-COM | organizaciones, usuarios, modulos, modulos_activos, consumo_mensual, detalle_casos, solicitudes_activacion | buscar_reglas, modulos_activos, consumo_mes | solicitar_activacion |

### 3.2 Reglas de selección

- El caso de uso se construye sobre el corpus y la base de datos del kit. El equipo carga el Excel en la base de datos que elija y puede agregar registros, pero no eliminar ni modificar los entregados, porque varios son casos de prueba.
- Los nombres de las herramientas son sugerencias: el equipo puede renombrarlas, dividirlas o agregar otras, siempre que cumpla los mínimos del capítulo 5.
- El kit contiene, sin señalarlos, documentos derogados junto a su versión vigente, fuentes que se contradicen entre sí o con los datos, preguntas razonables que ninguna fuente responde y contenido que intenta manipular al asistente. Encontrarlos y tratarlos según los principios de la sección 3.3 es parte de la evaluación.

### 3.3 Principios no negociables del asistente

Aplican a cualquier caso de uso. Deben regir el comportamiento del agente.

| ID | Principio |
|---|---|
| **PR-1** | El asistente no decide sobre un caso. Explica, sugiere y prepara; la decisión la toma y la confirma una persona. |
| **PR-2** | Toda afirmación sobre reglas, políticas o contrato cita el fragmento que la respalda, con fuente, sección y versión. Sin cita, no se afirma. |
| **PR-3** | Si la respuesta no está en el corpus, el asistente lo dice. La ausencia de evidencia nunca se presenta como respuesta favorable. |
| **PR-4** | Si dos fuentes vigentes se contradicen, el asistente presenta ambas y no elige por su cuenta. |
| **PR-5** | Todo dato sobre un caso proviene de una llamada MCP registrada y visible en la interfaz; el modelo no completa datos de un caso con texto propio. |
| **PR-6** | Las acciones con efecto requieren confirmación explícita de la persona. Una consulta nunca produce efectos. |
| **PR-7** | El asistente solo accede a lo que el usuario conectado puede ver según su rol: los datos de su organización o, para el personal de DPRIME, las organizaciones que tiene asignadas o autorizadas. |

---

## 4. Componente RAG

### 4.1 Corpus

El corpus reúne los documentos que el asistente puede citar y se compone de:
- Los documentos del kit para el caso elegido, todos obligatorios.
- Opcionalmente, artefactos propios de las Entregas 1 y 2 o documentos adicionales redactados por el equipo. Si se agregan, se marcan como ficticios, se declaran en el inventario y no pueden resolver en silencio una contradicción del kit.
- Considere que los docs pueden tener inconsistencias y además estar derogados.

Cada documento del kit declara en su encabezado su código, versión, estado y vigencia. Esos datos se conservan como metadatos de cada fragmento. El informe incluye el inventario del corpus: identificador, título, origen (kit, Descripción o equipo), versión, vigencia y tamaño aproximado en tokens.

### 4.2 Tecnología y datos enviados al modelo

El stack es libre. Si usa Python puede usar chromaDB para la BD vectorial. Para el modelo LLM, se recomienda una opción sin costo que corre en la nube, pero ninguna herramienta es obligatoria.

---

## 5. Componente MCP

### 5.1 Servidor MCP

El asistente es un modelo de lenguaje conectado, como cliente MCP, a un servidor MCP propio del equipo. El servidor expone herramientas que consultan la base de datos cargada desde el Excel del kit. El recorrido de una pregunta es el siguiente: la persona pregunta en la interfaz; la API del asistente entrega la pregunta al modelo junto con la lista de herramientas; el modelo decide qué herramienta llamar y con qué argumentos; el servidor MCP ejecuta la consulta en la base de datos y devuelve el resultado; el modelo redacta la respuesta con ese resultado y con los fragmentos que recuperó del corpus.

Reglas del acceso a la base de datos:
- Cada herramienta ejecuta una consulta parametrizada escrita por el equipo. El modelo elige la herramienta y sus argumentos; nunca escribe SQL.
- Las reglas que el corpus define para las acciones, como estados válidos, límites o permisos, se validan en el servidor antes de escribir. Si una regla impide la acción, la herramienta devuelve un error explicativo. Por ejemplo:
  - El procedimiento PRO-ANT dice que un operador no puede registrar más de dos solicitudes de antecedentes sobre un mismo caso.
  - En el Excel, el caso C-016 ya tiene dos (SA-001 y SA-002).
  - Si el operador pide «solicita antecedentes para C-016», el modelo llama a `solicitar_antecedentes(C-016)`.
  - La herramienta, antes de insertar en `solicitudes_antecedentes`, cuenta en la base cuántas tiene ya ese caso.
  - Si son dos o más y el usuario no es supervisor, no escribe nada y devuelve un error que se entienda, por ejemplo: «C-016 ya tiene 2 solicitudes; una tercera debe registrarla un supervisor (PRO-ANT §4)».
  - El asistente le muestra ese mensaje al usuario.

---

## 6. Frontend, backend y datos de prueba

### 6.1 Frontend

La interfaz es una aplicación web en español. Puede ser nueva o un módulo agregado a la aplicación de la Entrega 2. Mínimos:
- Conversación con el asistente, con indicación visible de cuándo responde con evidencia, cuándo se abstiene y cuándo detecta un conflicto entre fuentes.
- Mensaje comprensible cuando el proveedor del modelo o un servicio no responde, sin respuesta inventada.

### 6.2 Backend

- API del asistente: recibe la pregunta, decide si recupera, si llama herramientas o ambas, arma el prompt y devuelve respuesta, citas y trazas.
- Servicio RAG con indexación y consulta separadas.
- Servidor MCP descrito en el capítulo 5.
- Base de datos cargada desde el Excel del kit, a la que solo accede el servidor MCP.

---

## 7. Evaluación del asistente

Lo que el equipo debe medir y cómo. La regla general es la de la clase: cuando una respuesta falla, primero se pregunta si falló la búsqueda o falló el modelo.

### 7.1 Golden set del RAG

Lista fija de al menos 20 preguntas escritas por el equipo, con la siguiente composición mínima:

| Tipo | Mínimo | Comportamiento esperado |
|---|---|---|
| **Con respuesta en el corpus** | 12 | Responde y cita el fragmento esperado. |
| **Sin respuesta en el corpus** | 4 | Se abstiene y dice qué información falta. |
| **Con conflicto entre fuentes vigentes** | 2 | Presenta ambas fuentes y no elige. |
| **Con respuesta distinta entre versiones** | 2 | Responde con la versión vigente y lo indica. |

Para cada pregunta se registra identificador, pregunta, fragmento esperado, respuesta esperada, si debe responder y tipo. Las respuestas esperadas las valida el representante del cliente. El golden set se versiona en un commit anterior a la primera ejecución completa del pipeline, para que no se ajuste a lo que el sistema ya responde.

### 7.2 Métricas del RAG

| Etapa | Métrica | Definición operativa |
|---|---|---|
| **Recuperación** | Recall@k | Proporción de preguntas con respuesta cuyo fragmento esperado aparece entre los k recuperados. Se reporta a nivel de fragmento, no solo de documento. |
| **Generación** | Precisión de cita | Proporción de citas emitidas que apuntan a un fragmento que efectivamente respalda la afirmación. |
| **Generación** | Fidelidad | Proporción de respuestas cuyas afirmaciones están todas respaldadas por la evidencia recibida. |
| **Comportamiento** | Abstención correcta | Proporción de preguntas sin respuesta en que el asistente se abstiene, y proporción de preguntas con respuesta en que se abstiene sin motivo. |
| **Comportamiento** | Manejo de conflicto y vigencia | Proporción de preguntas de conflicto y de versión resueltas según la tabla 7.1. |

Cada fallo se clasifica como fallo de recuperación o de generación. El juicio de fidelidad y de precisión de cita puede hacerse a mano, con un modelo evaluador o con ambos; si se usa un modelo evaluador, se revisa a mano una muestra y se informa la concordancia.

---

## 11. Entregables

El equipo entrega cuatro piezas: el informe escrito con la estructura de este capítulo, el repositorio con código, y la presentación en PPT. Si no hace la presentación del trabajo se descuenta el 50% de la nota. Esta presentación debe contener una demo en vivo.

| Sección | Extensión máxima |
|---|---|
| **11.1 Resumen ejecutivo** | 1/2 plana |
| **11.2 Caso de uso y especificación** | 1,5 planas |
| **11.3 Diseño e implementación del RAG** | 2 planas |
| **11.4 Diseño e implementación del servidor MCP** | 1,5 planas |
| **11.5 Arquitectura e implementación front y back** | 1,5 planas |
| **11.6 Evaluación** | 3 planas |
| **11.7 Riesgos y controles** | 1 plana |
| **11.8 Discusión y conclusiones** | 1 plana |

---

## 13. Evaluación

La entrega se evalúa en dos partes de igual peso. Cada criterio se califica con nota de 1,0 a 7,0 y pondera según la tabla. La nota final es la suma de cada nota multiplicada por su ponderación, con un decimal. El criterio P4 se califica de forma individual, por lo que la nota final puede diferir entre integrantes del mismo equipo.

| Parte | Criterio | Ponderación |
|---|---|---|
| **Informe y repositorio (50 %)** | C1. Resumen ejecutivo | 3 % |
| | C2. Caso de uso y especificación | 6 % |
| | C3. Diseño e implementación del RAG | 10 % |
| | C4. Diseño e implementación del servidor MCP | 10 % |
| | C5. Arquitectura e implementación front y back | 6 % |
| | C6. Evaluación | 10 % |
| | C7. Riesgos y controles | 3 % |
| | C8. Discusión y conclusiones | 2 % |
| **Presentación oral (50 %)** | P1. Exposición | 10 % |
| | P2. Demostración en vivo | 20 % |
| | P3. Defensa técnica de la evaluación | 10 % |
| | P4. Respuestas individuales | 10 % |
| **Total** | | **100 %** |

---

## 14. Rúbrica

Cada criterio se califica según los descriptores siguientes. Las notas intermedias se asignan cuando el trabajo cumple parcialmente el nivel superior. La calificación 4,0 corresponde al cumplimiento suficiente del criterio.

### 14.1 Informe y repositorio (50 %)

| Criterio | 7,0 | 5,0 a 6,0 | 3,0 a 4,0 | 1,0 a 2,0 |
|---|---|---|---|---|
| **C1. Resumen ejecutivo (3 %)** | Responde qué hace, para quién, qué tan bien funciona con cifras comprensibles, qué no hace y qué se recomienda, en media plana y sin jerga. | Responde todo, con algo de jerga o con cifras sin interpretar. | Omite el desempeño o los límites, o describe el proceso en vez del resultado. | Ausente o sin relación con el trabajo. |
| **C2. Caso de uso y especificación (6 %)** | Caso justificado según 3.2, con la contradicción entre fuentes identificada y citada. Flujos principal y alternativos completos; cada necesidad clasificada con argumento; requisitos con ID y fuente; principios 3.3 en la constitución o el PRD. | Elementos completos; clasificación correcta pero poco argumentada o trazabilidad parcial. | Caso sin contradicción en el corpus, o necesidades mal clasificadas, por ejemplo un dato vivo resuelto con RAG. | Ausente o genérico, aplicable a cualquier sistema. |
| **C3. RAG (10 %)** | Corpus que cumple con inventario y versiones. Indexación reproducible y separada de la consulta. Fragmentación escogida con un experimento comparativo. Búsqueda justificada. Citas con fuente, sección y versión. Abstención, conflicto y vigencia implementados. | Pipeline completo y reproducible; la fragmentación o la búsqueda se justifican con argumentos y no con datos, o falta una política. | Funciona solo en el camino feliz; corpus insuficiente, sin versiones o con citas imprecisas. | No hay recuperación real, por ejemplo todo el corpus en el prompt, o no funciona. |
| **C4. Servidor MCP (10 %)** | Primitivas mínimas con consultas parametrizadas sobre la base del kit, sin SQL escrito por el modelo. Contratos completos. Errores informados. | Primitivas y contratos completos; algún control débil, como confirmación solo en la interfaz o descripciones ambiguas. | Solo lecturas, herramientas que acceden directo a la base de datos o sin manejo de errores. | No hay servidor MCP o no se conecta. |
| **C5. Front y back (6 %)** | Arquitectura y secuencia diagramadas. Datos enviados al modelo declarados. Estado y aporte del agente honestos. | Funciona con defectos menores o falta algún elemento de la interfaz. | Front o back incompleto; citas o trazas no visibles; pasos no documentados. | No se puede levantar o no existe interfaz. |
| **C6. Evaluación (10 %)** | Estrategia de pruebas. Fallos clasificados entre recuperación y generación. | Completo; análisis de fallos descriptivo o ciclo de mejora débil. | Golden set insuficiente o sin preguntas trampa; solo cifras agregadas sin análisis. | Ausente o anecdótica. |
| **C7. Riesgos y controles (3 %)** | Guardrails y riesgos configurados (mínimo 3). | Controles y pruebas para la mayoría de los riesgos. | Se identifica solo 1 riesgo con su guardrails. | Ausente. |
| **C8. Discusión y conclusiones (2 %)** | Reflexión con ejemplos propios sobre qué resolvió cada componente y qué ninguno; aprendizajes transferibles y pendientes concretos. | Reflexión pertinente con algún ejemplo. | Mayormente resume o generaliza. | Ausente. |

### 14.2 Presentación oral (50 %)

| Criterio | 7,0 | 5,0 a 6,0 | 3,0 a 4,0 | 1,0 a 2,0 |
|---|---|---|---|---|
| **P1. Exposición (10 %)** | Respeta el tiempo, la estructura es clara, participa todo el equipo sin leer y las diapositivas son legibles y coherentes con el informe. | Buena exposición con alguna falla de tiempo, de ritmo o de legibilidad. | Excede el tiempo, lee diapositivas o la participación es desigual. | No se presenta o hay integrantes que no exponen. |
| **P2. Demostración (20 %)** | Recorre D1 a D8 en vivo sobre v3.0 y cada paso muestra lo que debe verse: cita abierta, abstención, conflicto, traza, efecto verificado, riesgo contenido, cliente externo y pregunta no prevista bien manejada. | Guion completo con fallos menores, o algún paso explicado en vez de mostrado. | Faltan dos o más pasos, se recurre al video sin causa externa o la versión no es la etiquetada. | No hay demostración o el sistema no funciona. |
| **P3. Defensa técnica (10 %)** | Presenta las métricas del informe, explica un fallo concreto y su corrección, y defiende fragmentación, búsqueda y reparto entre RAG y MCP frente a alternativas. | Métricas correctas; defensa razonable pero general. | Métricas sin análisis o que no coinciden con el informe. | No presenta evaluación. |
| **P4. Respuestas individuales (10 %)** | Responde con dominio sobre cualquier parte del trabajo, incluidos código, corpus y evaluación, y fundamenta en el propio análisis. | Responde correctamente con alguna imprecisión. | Respuestas vagas o limitadas a la parte que desarrolló. | No responde o atribuye la respuesta a otro integrante o al agente. |
