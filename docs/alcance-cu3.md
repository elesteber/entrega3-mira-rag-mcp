# Alcance Funcional del Caso CU-3 (Asistente de Incorporación)

## 1. Declaración de Alcance General

El alcance de este proyecto abarca el diseño, implementación y evaluación de un asistente conversacional inteligente para el **Equipo de Implementación de DPRIME SpA**, enfocado en la gestión y auditoría del proceso de incorporación (*onboarding*) de organizaciones clientes en la plataforma MIRA.

El asistente integra:
1. **Recuperación Documental Aumentada (RAG):** Acceso al corpus normativo de incorporación con citas exactas, resolución de vigencias y detección de abstenciones.
2. **Acceso Gobernado mediante MCP:** Consulta parametrizada sobre la base de datos de organizaciones, plantillas, tareas, integraciones y formularios propios.
3. **Flujo de Mutación Controlada (Human-in-the-Loop):** Preparación y validación de cambios de estado de tareas, sujeta a confirmación humana y validación de reglas de negocio en el servidor.
4. **Seguridad y Control de Acceso (PR-7):** Restricción de visibilidad y acción según el rol y organizaciones asignadas al usuario conectado.

---

## 2. Requisitos Funcionales Iniciales (Propuesta con IDs)

| ID | Nombre | Descripción | Componente | Principio Asociado |
|---|---|---|---|---|
| **REQ-F-01** | Consulta de Estado de Incorporación | El usuario puede consultar el estado general de una organización y sus fechas límite. | MCP (Lectura) | PR-5, PR-7 |
| **REQ-F-02** | Auditoría de Criterios de Salida a Producción | El sistema evalúa los 6 criterios de salida de `GUI-INC_v2` contrastando los datos vivos de la organización con las normas. | RAG + MCP | PR-2, PR-5 |
| **REQ-F-03** | Consulta de Checklist y Tareas | El usuario puede listar las tareas pendientes, en curso y completadas por etapa (`E0` a `E5`). | MCP (Lectura) | PR-5, PR-7 |
| **REQ-F-04** | Explicación Normativa de Requisitos | El asistente explica las reglas de formularios propios, pruebas de integración o transferencias internacionales con citas a fragmentos. | RAG | PR-2, PR-4 |
| **REQ-F-05** | Preparación de Actualización de Tarea | El asistente prepara una solicitud de cambio de estado para una tarea específica, verificando si el usuario tiene rol autorizado. | MCP (Escritura) | PR-1, PR-6, PR-7 |
| **REQ-F-06** | Confirmación Explícita de Escritura | Antes de ejecutar cualquier actualización en la base de datos, el frontend solicita confirmación humana explícita mostrando los detalles del cambio. | Frontend + Backend | PR-6 |
| **REQ-F-07** | Validación de Reglas en Servidor | El servidor MCP valida condiciones de negocio antes de modificar una tarea (ej: no completar E5 si no se es jefe; no completar integración si fallaron pruebas). | Servidor MCP | PR-6, PR-7 |
| **REQ-F-08** | Detección de Abstención | Si se consulta sobre un procedimiento no cubierto en el corpus, el asistente se abstiene explícitamente e indica la falta de información. | RAG + Backend | PR-3 |
| **REQ-F-09** | Manejo de Discrepancias y Conflictos | Si existen discrepancias entre normas o entre norma y datos (ej. umbral PLA-ADM), el asistente expone ambas realidades. | RAG + Backend | PR-4 |
| **REQ-F-10** | Trazabilidad y Visualización de Evidencias | La interfaz muestra claramente los fragmentos citados y el registro de llamadas a herramientas MCP realizadas. | Frontend | PR-2, PR-5 |

---

## 3. Propuestas de Historias de Usuario (Formato BDD)

### HU-01: Diagnóstico de salida a producción de una organización
- **Como:** Ejecutivo de implementación asignado (`U-I1`).
- **Quiero:** Preguntar qué le falta a `ORG-07` para pasar a producción.
- **Para:** Conocer exactamente las tareas, autorizaciones y pruebas pendientes sin revisar múltiples planillas.
- **Criterio de Aceptación (Escenario):**
  - *Dado que* el usuario autenticado es Sofía Tapia (`U-I1`), ejecutiva asignada a `ORG-07`.
  - *Cuando* solicita «¿Qué le falta a la organización ORG-07 para pasar a producción con la plantilla de admisión clínica?».
  - *Entonces* el asistente consulta las herramientas MCP correspondientes (`checklist_organizacion`, `consultar_integracion`, `consultar_formularios`).
  - *Y* recupera del corpus los 6 criterios de `GUI-INC_v2 §3` y los requisitos de `FIC-PLA` y `POL-FOR`.
  - *Y* responde detallando que faltan:
    1. Aprobación de segundo supervisor para umbrales (`T-023`).
    2. Firma de autorización biométrica (`T-025`, requerida por `PLA-ADM`).
    3. Pruebas de integración exitosas (`T-027`: solo van 14/20 exitosas y tasa observada de 240 supera límite de 100 de `REQ-INT §5`).
    4. Formulario propio `F-01` en estado operativo (actualmente recibido, con solo 12 ejemplos según `POL-FOR §2`).
    5. Firma de transferencia internacional (`T-029`, requerida por proveedor fuera del país).
    6. Tarea E5 de salida a producción (`T-030`).
  - *Y* cada criterio cita el documento, sección y versión correspondiente.

### HU-02: Control de acceso entre ejecutivos (PR-7)
- **Como:** Ejecutivo de implementación (`U-I2`).
- **Quiero:** Consultar información sobre `ORG-07`.
- **Para:** Intentar revisar un caso fuera de mis asignaciones.
- **Criterio de Aceptación:**
  - *Dado que* el usuario autenticado es Diego Fuentes (`U-I2`) y `ORG-07` está asignada a Sofía Tapia (`U-I1`).
  - *Cuando* el usuario solicita información o tareas de `ORG-07`.
  - *Entonces* el servidor MCP rechaza la consulta por falta de permisos o el backend filtra los datos.
  - *Y* el asistente responde informando de manera clara que el usuario no tiene asignada dicha organización.

### HU-03: Actualización controlada de una tarea (PR-6 / Human-in-the-Loop)
- **Como:** Ejecutiva de implementación (`U-I1`).
- **Quiero:** Marcar como completada la tarea `T-025` de `ORG-07`.
- **Para:** Reflejar que la autorización de datos biométricos fue firmada.
- **Criterio de Aceptación:**
  - *Dado que* el usuario solicita «Marca como completada la tarea T-025 de ORG-07».
  - *Cuando* el modelo procesa la petición, NO ejecuta la escritura de inmediato.
  - *Entonces* el sistema presenta un modal de confirmación con los datos de la acción (`tarea_id`, `org_id`, nuevo estado).
  - *Y* tras la confirmación explícita del usuario, el servidor MCP valida que el usuario sea el ejecutivo asignado y ejecuta la actualización.
  - *Y* el frontend muestra la traza de la llamada y el resultado actualizado en la base de datos.

### HU-04: Rechazo de salida a producción no autorizada
- **Como:** Ejecutiva de implementación (`U-I1`).
- **Quiero:** Marcar como completada la tarea `T-030` (Salida a producción E5).
- **Para:** Finalizar la incorporación.
- **Criterio de Aceptación:**
  - *Dado que* el usuario tiene rol `ejecutivo_implementacion`.
  - *Cuando* solicita marcar la tarea `T-030` de etapa `E5`.
  - *Entonces* el servidor MCP rechaza la acción retornando un error explicativo: *«La tarea de salida a producción (E5) solo puede ser marcada por el jefe de implementación (GUI-INC v2 §4)»*.
  - *Y* no se modifica ningún dato en la base de datos.

---

## 4. Exclusiones Explícitas (Fuera de Alcance)

1. **Otros Casos de Uso:** Quedan totalmente excluidos CU-1 (Operador de revisión), CU-2 (Soporte y operación) y CU-4 (Módulos y consumo).
2. **Generación Libre de SQL:** El modelo de lenguaje bajo ninguna circunstancia generará ni ejecutará sentencias SQL directas contra SQLite.
3. **Módulos Reales de IA Biométrica:** No se procesan imágenes reales, firmas digitales ni biometría; el sistema gestiona la trazabilidad documental y los registros de estado.
4. **Sistemas Externos Reales:** Las APIs asincrónicas, webhooks y carpetas compartidas son simuladas mediante los registros de la base de datos entregada.

---

## 5. Elementos que Requieren Validación Humana Posterior

- Validación con el equipo de la lista definitiva de herramientas MCP (si `buscar_reglas` se implementa como MCP tool o servicio RAG interno del backend).
- Definición de si el rol `comercial` puede consultar checklists de todas las organizaciones o si tiene alguna restricción adicional.
