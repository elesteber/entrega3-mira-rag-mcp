# Inventario y Análisis del Corpus Documental (CU-3)

Este documento detalla el inventario completo, características y análisis semántico de los cinco documentos que componen el corpus obligatorio del **Caso de Uso CU-3: Asistente de Incorporación de Organizaciones**.

---

## 1. Inventario General del Corpus

| Código | Título | Versión | Estado | Vigencia | Origen | Palabras | Tokens Aprox. | Archivo en Repositorio |
|---|---|---|---|---|---|---|---|---|
| **GUI-INC** | Guía de incorporación de organizaciones (v1) | 1 | **Derogada** | 01/11/2025 al 31/08/2026 | Kit CU-3 (Equipo de Implementación) | 206 | ~278 | `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus/GUI-INC_v1_derogada.md` |
| **GUI-INC** | Guía de incorporación de organizaciones (v2) | 2 | **Vigente** | Desde 01/09/2026 | Kit CU-3 (Equipo de Implementación) | 471 | ~635 | `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus/GUI-INC_v2_vigente.md` |
| **FIC-PLA** | Fichas de plantillas por caso de uso | 1 | **Vigente** | Desde 01/09/2026 | Kit CU-3 (Dirección de Producto) | 333 | ~449 | `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus/FIC-PLA_fichas_plantillas.md` |
| **REQ-INT** | Requisitos técnicos de integración | 2 | **Vigente** | Desde 01/09/2026 | Kit CU-3 (Ingeniería de Plataforma) | 324 | ~437 | `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus/REQ-INT_requisitos_integracion.md` |
| **POL-FOR** | Política de formularios propios | 1 | **Vigente** | Desde 01/09/2026 | Kit CU-3 (Ingeniería de Modelos) | 202 | ~272 | `archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus/POL-FOR_formularios_propios.md` |
| **TOTAL** | **5 documentos** | — | — | — | — | **1.536** | **~2.071** | — |

---

## 2. Análisis Detallado por Documento

### 2.1 `GUI-INC_v1_derogada.md` (Versión Histórica Derogada)
- **Metadatos:** Código `GUI-INC`, Versión `1`, Estado `Derogada`, Vigencia `2025-11-01 a 2026-08-31`.
- **Estructura de Secciones:**
  - `§1. Etapas`: 5 etapas tradicionales (Creación de ambiente, Configuración de módulos, Armado de flujo a medida, Ajuste de formularios, Integración). Duración total: 6 a 8 semanas.
  - `§2. Salida a producción`: La salida la otorga el ingeniero a cargo cuando da su conformidad.
- **Rol en la Evaluación:** Permite evaluar si el asistente discrimina versiones obsoletas (ej. preguntas como «¿Cuánto dura la incorporación según GUI-INC?», donde debe responder con la v2 e indicar que la v1 duraba 6 a 8 semanas pero está derogada).

### 2.2 `GUI-INC_v2_vigente.md` (Norma Principal Vigente)
- **Metadatos:** Código `GUI-INC`, Versión `2`, Estado `Vigente`, Vigencia `Desde 2026-09-01`.
- **Estructura de Secciones:**
  - `§1. Meta`: Adaptación de plantilla con meta de 10 días hábiles desde firma.
  - `§2. Etapas`: 6 etapas estandarizadas:
    - `E0. Alta`: Día 0 (organización, ambiente integración, usuarios iniciales).
    - `E1. Plantilla`: Día 0 (asignación plantilla FIC-PLA y casos ejemplo).
    - `E2. Adaptación`: Días 1 a 5 (módulos, reglas, umbrales, formularios propios).
    - `E3. Integración`: Días 1 a 8 (conexión y prueba en integración).
    - `E4. Pruebas`: Días 6 a 9 (ejecución casos punta a punta).
    - `E5. Salida a producción`: Día 10 (verificación y paso a producción).
  - `§3. Criterios de salida a producción`: 6 criterios obligatorios acumulativos:
    1. Tareas obligatorias E0 a E4 completadas.
    2. Integración probada con éxito en ambiente de integración.
    3. Umbrales de decisión aprobados por dos supervisores de la organización.
    4. Firma de transferencia internacional si proveedor de modelos procesa fuera del país.
    5. Firma de tratamiento de datos biométricos si plantilla incluye módulos biométricos.
    6. Todos los formularios propios en estado «operativo».
    *Regla taxativa:* Ninguna organización pasa a producción con tareas obligatorias pendientes, aunque se cumpla la fecha objetivo.
  - `§4. Permisos`:
    - Cada ejecutivo ve y modifica solo las organizaciones asignadas.
    - Ejecutivo puede marcar completadas tareas E0 a E4 de sus organizaciones.
    - La tarea de salida a producción (E5) solo la marca el **jefe de implementación**.

### 2.3 `FIC-PLA_fichas_plantillas.md` (Catálogo de Plantillas)
- **Metadatos:** Código `FIC-PLA`, Versión `1`, Estado `Vigente`, Vigencia `Desde 2026-09-01`.
- **Estructura de Secciones:**
  - `§1. Qué es una plantilla`: Flujo preconfigurado con módulos, reglas y umbrales.
  - `§2. Plantillas disponibles`:
    - `PLA-REM` (Reembolso gastos médicos): Seguros, módulos OCR/QR/FIR, umbrales 85/60, 4 días adaptación, no requiere biometría.
    - `PLA-SIN` (Siniestro automotriz): Seguros, módulos OCR/IMG/VDO, umbrales 85/60, 5 días adaptación, no requiere biometría.
    - `PLA-CTA` (Apertura de cuenta): Banca, módulos OCR/ROS/VID/QR, umbrales 90/65, 3 días adaptación, **requiere autorización biométrica**.
    - `PLA-ADM` (Admisión clínica): Salud, módulos OCR/ROS/QR, umbrales sugeridos **85/60**, 4 días adaptación, **requiere autorización biométrica**.
- **Punto de Conflicto Detectado:**
  - En `FIC-PLA §2` los umbrales de `PLA-ADM` son **85 aprobación / 60 revisión**.
  - En la base de datos (`plantillas`), `PLA-ADM` figura con **80 aprobación / 60 revisión**.

### 2.4 `REQ-INT_requisitos_integracion.md` (Norma Técnica de Conexión)
- **Metadatos:** Código `REQ-INT`, Versión `2`, Estado `Vigente`, Vigencia `Desde 2026-09-01`.
- **Estructura de Secciones:**
  - `§1. Modos de integración`:
    - Interfaz asincrónica: Modo por defecto (acuse <1s, llamada de vuelta / webhook posterior).
    - Interfaz sincrónica: Solo para documentos livianos con respuesta inmediata.
    - Intercambio de archivos: Carpetas compartidas con ciclos de 30 minutos.
  - `§2. Autenticación`: Credenciales MIRA o federación con directorio corporativo. Credenciales cifradas por ambiente.
  - `§3. Límites de llamadas`: 1.000 llamadas por minuto por organización general. Excesos se encolan.
  - `§4. Ambientes`: Integración (con datos de ejemplo DPRIME) y Producción (datos reales solo aquí).
  - `§5. Prueba de integración`: Exige enviar al menos 20 casos de ejemplo y recibir llamada de vuelta de todos sin error. Carga máxima en prueba: **100 llamadas por minuto**.

### 2.5 `POL-FOR_formularios_propios.md` (Políticas de Modelos)
- **Metadatos:** Código `POL-FOR`, Versión `1`, Estado `Vigente`, Vigencia `Desde 2026-09-01`.
- **Estructura de Secciones:**
  - `§1. Qué es un formulario propio`: Documento con formato particular de la organización cliente.
  - `§2. Requisitos para dejarlo operativo`:
    - Entrega de entre 20 y 30 ejemplos con datos personales enmascarados.
    - Ajuste de modelos: 10 a 15 días hábiles desde recepción de ejemplos completos.
    - Ciclo de estados: `recibido` -> `en_ajuste` -> `operativo`.
  - `§3. Operación mientras no está operativo`: Los casos se derivan a revisión asistida con razón *«formulario propio en ajuste»*.

---

## 3. Metadatos Requeridos para Indexación en ChromaDB

Cada chunk o fragmento almacenado en la base vectorial debe contener la siguiente estructura de metadatos para permitir citas exactas (PR-2) y filtros de vigencia:

```json
{
  "doc_code": "GUI-INC",
  "doc_title": "Guía de incorporación de organizaciones",
  "version": 2,
  "status": "vigente",
  "effective_date": "2026-09-01",
  "section": "§3. Criterios de salida a producción",
  "origin": "kit_cu3",
  "chunk_id": "GUI-INC-v2-sec3-c1"
}
```
