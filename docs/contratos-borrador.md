# Contratos Preliminares de API y Herramientas MCP (CU-3)

> **Aviso de Estado:** Este documento contiene **especificaciones borrador y propuestas técnicas preliminares**. Ninguno de estos contratos se considera definitivo hasta su formalización en el ciclo de especificación con GitHub Spec Kit.

---

## 1. Contratos de Herramientas del Servidor MCP

El servidor MCP expone herramientas parametrizadas que interactúan con la base de datos `SQLite` (`mira_cu3.db`).

### 1.1 Herramienta `checklist_organizacion` (Lectura)
- **Propósito:** Obtener el detalle de tareas de incorporación de una organización, su estado actual y observaciones técnicas.
- **Entrada (JSON Schema propuesto):**
```json
{
  "type": "object",
  "properties": {
    "org_id": {
      "type": "string",
      "description": "Identificador único de la organización (ej: 'ORG-07')"
    },
    "etapa": {
      "type": "string",
      "enum": ["todas", "E0", "E1", "E2", "E3", "E4", "E5"],
      "default": "todas",
      "description": "Filtro opcional por etapa de incorporación"
    }
  },
  "required": ["org_id"]
}
```
- **Contexto de Seguridad del Servidor (PR-7):** Valida que el usuario en sesión sea el ejecutivo asignado a `org_id` o tenga rol `jefe_implementacion` / `comercial`. Si no está autorizado, retorna error de permisos.
- **Salida:**
```json
{
  "org_id": "ORG-07",
  "nombre": "Red de Clínicas Valle Verde",
  "plantilla_id": "PLA-ADM",
  "ejecutivo_asignado": "U-I1",
  "total_tareas": 11,
  "completadas": 4,
  "en_curso": 2,
  "pendientes": 5,
  "tareas": [
    {
      "tarea_id": "T-023",
      "etapa": "E2",
      "descripcion": "Ajustar umbrales y obtener aprobación de dos supervisores",
      "obligatoria": "sí",
      "estado": "en_curso",
      "fecha_limite": "2026-10-21",
      "observacion": "Aprobado por un supervisor; falta el segundo"
    }
  ]
}
```

### 1.2 Herramienta `listar_plantillas` (Lectura)
- **Propósito:** Consultar las plantillas disponibles, sus módulos requeridos, umbrales y exigencias de biometría.
- **Entrada:**
```json
{
  "type": "object",
  "properties": {
    "plantilla_id": {
      "type": "string",
      "description": "Identificador opcional de la plantilla (ej: 'PLA-ADM')"
    }
  }
}
```
- **Salida:**
```json
{
  "plantillas": [
    {
      "plantilla_id": "PLA-ADM",
      "nombre": "Admisión clínica",
      "industria": "salud",
      "modulos": "MOD-OCR, MOD-ROS, MOD-QR",
      "umbral_aprobacion_sugerido": 80,
      "umbral_revision_sugerido": 60,
      "dias_adaptacion_estimados": 4,
      "requiere_autorizacion_biometrica": "sí"
    }
  ]
}
```

### 1.3 Herramienta `consultar_estado_integracion` (Lectura - Propuesta Adicional)
- **Propósito:** Consultar las métricas observadas en la prueba de integración de una organización (`casos_ejemplo_enviados`, `llamadas_vuelta_exitosas`, `max_llamadas_por_minuto_observado`).
- **Entrada:** `org_id` (string).
- **Salida:** Métricas de la tabla `integraciones` contrastadas con los límites de `REQ-INT §5`.

### 1.4 Herramienta `marcar_tarea` (Escritura - Requiere Confirmación Humana)
- **Propósito:** Actualizar el estado de una tarea específica de incorporación.
- **Entrada:**
```json
{
  "type": "object",
  "properties": {
    "tarea_id": {
      "type": "string",
      "description": "Código de la tarea (ej: 'T-025')"
    },
    "nuevo_estado": {
      "type": "string",
      "enum": ["pendiente", "en_curso", "completada"],
      "description": "Nuevo estado a registrar"
    },
    "token_confirmacion": {
      "type": "string",
      "description": "Token emitido tras la confirmación humana explícita (PR-6)"
    }
  },
  "required": ["tarea_id", "nuevo_estado", "token_confirmacion"]
}
```
- **Validaciones Críticas en Servidor:**
  1. Si `nuevo_estado == 'completada'` y la tarea corresponde a la etapa `E5` (ej. `T-010`, `T-019`, `T-030`), **solo se permite si el rol del usuario es `jefe_implementacion`** (`GUI-INC_v2 §4`). En caso contrario, retorna código `ERROR_ROL_NO_AUTORIZADO`.
  2. Si el usuario es `ejecutivo_implementacion`, la tarea debe pertenecer a una de sus organizaciones asignadas.
  3. No se puede marcar una tarea sin un `token_confirmacion` válido.

---

## 2. Contratos de la API REST (Backend FastAPI)

### 2.1 Endpoint: `POST /api/chat`
- **Payload de Solicitud:**
```json
{
  "mensaje": "¿Qué le falta a la organización ORG-07 para pasar a producción?",
  "usuario_id": "U-I1"
}
```
- **Respuesta:**
```json
{
  "respuesta": "A la organización ORG-07 (Red de Clínicas Valle Verde) le faltan los siguientes requisitos para pasar a producción...",
  "estado_evidencia": "con_evidencia",
  "citas": [
    {
      "doc_code": "GUI-INC",
      "version": 2,
      "section": "§3. Criterios de salida a producción",
      "fragmento": "Todas las tareas obligatorias de las etapas E0 a E4 están completadas... Ninguna organización pasa a producción con tareas obligatorias pendientes..."
    },
    {
      "doc_code": "FIC-PLA",
      "version": 1,
      "section": "§2. Plantillas disponibles - PLA-ADM",
      "fragmento": "Requiere autorización de tratamiento de datos biométricos."
    }
  ],
  "trazas_mcp": [
    {
      "herramienta": "checklist_organizacion",
      "parametros": { "org_id": "ORG-07" },
      "duracion_ms": 15,
      "resultado_resumen": "11 tareas encontradas, 5 pendientes"
    }
  ],
  "accion_propuesta": null
}
```

### 2.2 Endpoint: `POST /api/actions/prepare` y `POST /api/actions/execute`
- `prepare`: Recibe la intención de mutación, valida factibilidad y devuelve un resumen estructurado para el modal del frontend junto a un token efímero de confirmación.
- `execute`: Recibe el token firmado por el usuario y ejecuta la herramienta MCP de escritura.
