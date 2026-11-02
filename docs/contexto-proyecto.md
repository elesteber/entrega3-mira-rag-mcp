# Contexto del Proyecto y Definición del Caso MIRA CU-3

## 1. Introducción y Contexto Empresarial

**MIRA** es una plataforma ficticia de inteligencia artificial multimodal desarrollada por la empresa **DPRIME SpA**, diseñada para apoyar decisiones empresariales críticas (tales como liquidación de siniestros, reembolsos médicos, admisión clínica y apertura de cuentas bancarias).

En el marco operativo de DPRIME SpA, la trazabilidad, la justificación ante terceros y el cumplimiento regulatorio son requisitos innegociables. El mayor riesgo empresarial radica en asistentes de lenguaje que produzcan respuestas de tono convincente pero basadas en normas obsoletas, alucinaciones o datos inexistentes. En consecuencia, la plataforma MIRA impone que **toda afirmación normativa esté respaldada por citas documentales verificables** y **todo dato sobre entidades vivas provenga de consultas registradas al sistema**.

---

## 2. Marco Académico de la Entrega 3

- **Asignatura:** Taller de Desarrollo de Software Conducido por Agentes de IA.
- **Institución:** Escuela de Ingeniería Informática, Facultad de Ingeniería, Universidad de Valparaíso.
- **Fecha y hora límite de entrega:** Lunes 9 de noviembre de 2026, a las 14:00 hrs.
- **Composición del equipo:** 4 integrantes.
- **Ponderación:** 50% Informe técnico y repositorio de código + 50% Presentación oral y demostración en vivo (15 minutos presentación/demo + 5 minutos de preguntas).
- **Independencia funcional:** La Entrega 3 es autocontenida; no depende del código desarrollado en las Entregas 1 y 2.

---

## 3. Definición y Propósito del Caso de Uso CU-3

### 3.1 Identificación
- **Identificador:** `CU-3`
- **Nombre:** Asistente de incorporación de organizaciones (*Onboarding Assistant*).
- **Usuario principal:** Equipo de Implementación de DPRIME SpA (ejecutivos de implementación y jefatura de implementación).

### 3.2 Necesidad que atiende
El proceso de incorporación de una organización cliente a MIRA contempla etapas críticas que van desde la creación del ambiente y asignación de plantilla, hasta la adaptación de umbrales, integración técnica y aprobación legal/biométrica.

El asistente de incorporación asiste al equipo de DPRIME para:
1. Determinar con exactitud **qué requisitos técnicos, tareas pendientes o autorizaciones faltan** para que una organización pase a producción a partir de la plantilla seleccionada.
2. Explicar el sustento documental vigente de cada criterio (normas de integración, vigencia de guías, requisitos de formularios propios y autorizaciones de datos).
3. Monitorear los checklists de avance y pruebas de carga observadas.
4. Preparar la actualización de estado de tareas, respetando de forma estricta los roles de los usuarios y solicitando confirmación humana obligatoria antes de cualquier mutación.

### 3.3 Pregunta de Referencia Oficial
> *«¿Qué le falta a la organización ORG-07 para pasar a producción con la plantilla de admisión clínica?»*

---

## 4. Actores del Sistema (CU-3)

A partir de los datos y corpus proporcionados, se identifican los siguientes actores y roles:

1. **Ejecutivo de Implementación (`ejecutivo_implementacion`):**
   - Profesional de DPRIME a cargo del acompañamiento técnico y operativo de organizaciones específicas.
   - *Permisos:* Consulta exclusiva sobre las organizaciones que tiene formalmente asignadas; puede marcar como completadas tareas correspondientes a las etapas E0 a E4 de sus organizaciones asignadas. No puede marcar la tarea de salida a producción (E5).
   - *Ejemplos en datos de prueba:* `U-I1` (Sofía Tapia), `U-I2` (Diego Fuentes).
2. **Jefe de Implementación (`jefe_implementacion`):**
   - Responsable de supervisar la totalidad del proceso de incorporación de todas las organizaciones en la plataforma.
   - *Permisos:* Consulta global y facultad exclusiva para autorizar y marcar la tarea de salida a producción (`E5. Salida a producción`).
   - *Ejemplo en datos de prueba:* `U-I3` (Carolina Vera).
3. **Área Comercial / Auditoría (`comercial`):**
   - Usuario con permisos de visualización general para seguimiento comercial, sin facultades para modificar tareas operativas de incorporación.
   - *Ejemplo en datos de prueba:* `U-I4` (Pablo Reyes).
4. **Organización Cliente (Entidad externa):**
   - Entidad en proceso de incorporación (ej. `ORG-05` Mutual de Seguros, `ORG-06` Banco Cumbres, `ORG-07` Red de Clínicas Valle Verde, `ORG-08` Aseguradora Ruta Segura).

---

## 5. Restricciones y Principios Operativos Innegociables

El sistema debe satisfacer sin excepciones los principios **PR-1 a PR-7**:
- **PR-1:** El asistente no decide la salida a producción ni aprueba por sí solo una tarea; explica, sugiere y prepara.
- **PR-2:** Toda regla o criterio citado debe incluir código de documento, sección y versión vigente.
- **PR-3:** Cuando no exista evidencia en el corpus sobre un requerimiento, el asistente debe abstenerse explícitamente.
- **PR-4:** Ante conflictos entre fuentes vigentes, el asistente debe exponer las alternativas sin elegir por su cuenta.
- **PR-5:** Todo dato de estado de avance, métricas de integración o nombres de tareas proviene exclusivamente de llamadas MCP trazables.
- **PR-6:** Cualquier acción de actualización en la base de datos exige confirmación humana previa.
- **PR-7:** Un ejecutivo no puede consultar ni alterar datos de organizaciones que no tenga asignadas.
