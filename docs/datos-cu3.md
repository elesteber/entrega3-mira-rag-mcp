# Modelo de Datos Estructurados y Análisis del Excel (CU-3)

Este documento detalla el esquema relacional, los tipos de datos, las relaciones y las reglas de integridad derivadas de la inspección técnica del archivo:
`archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/datos/CU-3_datos.xlsx`.

---

## 1. Convenciones y Hoja de Control (`LEEME`)

Según la hoja `LEEME` del kit:
- Cada hoja (salvo `LEEME`) representa una tabla de la base de datos relacional.
- La fila 1 contiene los nombres exactos de las columnas.
- La primera columna de cada tabla es la **clave primaria (PK)**, salvo en tablas de relación directa.
- Formatos: Fechas en `AAAA-MM-DD` (o `AAAA-MM-DD HH:MM`).
- Valores booleanos: cadenas en minúscula `sí` / `no`.
- Celdas vacías representan `NULL` (dato no informado).
- **Regla de integridad docente:** Los registros entregados son inmutables; no deben eliminarse ni modificarse ya que constituyen casos de prueba del evaluador.

---

## 2. Esquema Relacional Detallado por Tabla

### 2.1 Tabla `organizaciones` (4 registros)
Contiene las organizaciones clientes en proceso de incorporación o ya pasadas a producción.

| Columna | Tipo Inferido | Restricción | Descripción |
|---|---|---|---|
| `org_id` | TEXT | PRIMARY KEY | Identificador único de la organización (ej: `ORG-05`, `ORG-07`). |
| `nombre` | TEXT | NOT NULL | Razón social o nombre de fantasía. |
| `industria` | TEXT | NOT NULL | Sector económico (`seguros`, `banca`, `salud`). |
| `pais` | TEXT | NOT NULL | País de operación (`Chile`, `Perú`, `Colombia`). |
| `fecha_firma` | DATE | NOT NULL | Fecha de firma del contrato de incorporación (`AAAA-MM-DD`). |
| `estado_incorporacion` | TEXT | NOT NULL | Estado global (`en_adaptacion`, `en_pruebas`, `produccion`). |
| `plantilla_id` | TEXT | FK -> `plantillas.plantilla_id` | Plantilla MIRA asignada (`PLA-REM`, `PLA-CTA`, `PLA-ADM`, `PLA-SIN`). |
| `ejecutivo_id` | TEXT | FK -> `usuarios.usuario_id` | Ejecutivo de implementación asignado (`U-I1`, `U-I2`). |
| `proveedor_modelos_fuera_del_pais` | TEXT | CHECK in ('sí', 'no') | Si el modelo corre en el extranjero (activa criterio 4 de `GUI-INC_v2`). |
| `fecha_objetivo_produccion` | DATE | NOT NULL | Fecha meta calculada (10 días hábiles desde firma). |

### 2.2 Tabla `usuarios` (4 registros)
Catálogo del personal de DPRIME involucrado en la incorporación.

| Columna | Tipo Inferido | Restricción | Descripción |
|---|---|---|---|
| `usuario_id` | TEXT | PRIMARY KEY | Identificador de usuario (`U-I1` a `U-I4`). |
| `nombre` | TEXT | NOT NULL | Nombre y apellido del funcionario. |
| `rol` | TEXT | NOT NULL | Rol de permisos (`ejecutivo_implementacion`, `jefe_implementacion`, `comercial`). |

*Registros reales:*
- `U-I1`: Sofía Tapia (`ejecutivo_implementacion`) — Asignada a `ORG-05` y `ORG-07`.
- `U-I2`: Diego Fuentes (`ejecutivo_implementacion`) — Asignada a `ORG-06` y `ORG-08`.
- `U-I3`: Carolina Vera (`jefe_implementacion`) — Supervisión global y autorización exclusiva de etapa `E5`.
- `U-I4`: Pablo Reyes (`comercial`) — Seguimiento comercial.

### 2.3 Tabla `plantillas` (4 registros)
Especificación de plantillas estándar de MIRA.

| Columna | Tipo Inferido | Restricción | Descripción |
|---|---|---|---|
| `plantilla_id` | TEXT | PRIMARY KEY | Código de la plantilla (`PLA-REM`, `PLA-SIN`, `PLA-CTA`, `PLA-ADM`). |
| `nombre` | TEXT | NOT NULL | Nombre del flujo estándar. |
| `industria` | TEXT | NOT NULL | Industria aplicable (`seguros`, `banca`, `salud`). |
| `modulos` | TEXT | NOT NULL | Lista de códigos de módulos requeridos separados por coma. |
| `umbral_aprobacion_sugerido` | INTEGER | NOT NULL | Puntaje mínimo sugerido para aprobación automática. |
| `umbral_revision_sugerido` | INTEGER | NOT NULL | Puntaje mínimo sugerido para revisión asistida. |
| `dias_adaptacion_estimados` | INTEGER | NOT NULL | Días hábiles estimados para la etapa E2. |
| `requiere_autorizacion_biometrica` | TEXT | CHECK in ('sí', 'no') | Indica si exige firma de tratamiento de biometría. |

### 2.4 Tabla `tareas` (37 registros)
Checklist detallado de tareas por organización y etapa.

| Columna | Tipo Inferido | Restricción | Descripción |
|---|---|---|---|
| `tarea_id` | TEXT | PRIMARY KEY | Identificador único de tarea (`T-001` a `T-037`). |
| `org_id` | TEXT | FK -> `organizaciones.org_id` | Organización a la que pertenece la tarea. |
| `etapa` | TEXT | NOT NULL | Etapa del proceso (`E0`, `E1`, `E2`, `E3`, `E4`, `E5`). |
| `descripcion` | TEXT | NOT NULL | Detalle de la actividad requerida. |
| `obligatoria` | TEXT | CHECK in ('sí', 'no') | Si es condición obligatoria para salida a producción. |
| `estado` | TEXT | NOT NULL | Estado actual (`pendiente`, `en_curso`, `completada`). |
| `responsable` | TEXT | FK -> `usuarios.usuario_id` | Usuario responsable de ejecutar o verificar la tarea. |
| `fecha_limite` | DATE | NOT NULL | Fecha límite estimada (`AAAA-MM-DD`). |
| `observacion` | TEXT | NULLABLE | Notas de campo, justificaciones o intentos de inyección. |

### 2.5 Tabla `integraciones` (4 registros)
Estado de la conectividad técnica y resultados de las pruebas en integración.

| Columna | Tipo Inferido | Restricción | Descripción |
|---|---|---|---|
| `integracion_id` | TEXT | PRIMARY KEY | Identificador de la integración (`I-01` a `I-04`). |
| `org_id` | TEXT | FK -> `organizaciones.org_id` | Organización vinculada (relación 1:1 en los datos). |
| `modo` | TEXT | NOT NULL | Modo técnico (`api_asincronica`, `archivos`). |
| `ambiente` | TEXT | NOT NULL | Ambiente actual (`integracion`, `produccion`). |
| `estado` | TEXT | NOT NULL | Estado técnico (`en_configuracion`, `en_prueba`, `probada`, `operativa`). |
| `casos_ejemplo_enviados` | INTEGER | NOT NULL | Número de casos enviados en la prueba. |
| `llamadas_vuelta_exitosas` | INTEGER | NOT NULL | Número de webhooks recibidos exitosamente. |
| `max_llamadas_por_minuto_observado`| INTEGER | NOT NULL | Tasa máxima observada durante la prueba de carga. |

### 2.6 Tabla `formularios_propios` (3 registros)
Registro y ciclo de vida de formularios institucionales propios.

| Columna | Tipo Inferido | Restricción | Descripción |
|---|---|---|---|
| `formulario_id` | TEXT | PRIMARY KEY | Identificador del formulario (`F-01` a `F-03`). |
| `org_id` | TEXT | FK -> `organizaciones.org_id` | Organización propietaria del formulario. |
| `nombre` | TEXT | NOT NULL | Nombre del formulario. |
| `ejemplos_recibidos` | INTEGER | NOT NULL | Cantidad de muestras entregadas (debe ser >= 20 para avanzar). |
| `fecha_ejemplos_completos` | DATE | NULLABLE | Fecha en que se completó el lote de ejemplos. |
| `estado` | TEXT | NOT NULL | Estado (`recibido`, `en_ajuste`, `operativo`). |

---

## 3. Relaciones Inferidas y Grafo de Integridad

```text
[usuarios] (usuario_id)
    ▲            ▲
    │ (asigna)   │ (responsable)
[organizaciones] ┼──────────► [tareas] (org_id, responsable)
    ▲            │
    │ (usa)      ├──────────► [integraciones] (org_id)
[plantillas]     │
                 └──────────► [formularios_propios] (org_id)
```

---

## 4. Análisis de Casos de Prueba en los Datos

1. **`ORG-05` (Mutual de Seguros Puerto Claro - PLA-REM):**
   - Etapa: `en_adaptacion`. Asignada a `U-I1`.
   - Estado: Integración por archivos en configuración (`I-01`). Formulario propio `F-02` operativo.
   - **Caso de Prueba Trampa:** Tarea `T-008` contiene texto de prompt injection en `observacion`.
2. **`ORG-06` (Banco Cumbres del Pacífico - PLA-CTA):**
   - Etapa: `en_pruebas`. Asignada a `U-I2`.
   - Estado: Integración API probada exitosamente (`I-02`). Tarea `T-018` pendiente (legal revisando transferencia internacional). Formulario propio `F-03` aún `en_ajuste`.
3. **`ORG-07` (Red de Clínicas Valle Verde - PLA-ADM):**
   - Etapa: `en_adaptacion`. Asignada a `U-I1`.
   - **Caso Principal de Evaluación:**
     - Falta 2do supervisor para umbrales (`T-023`).
     - Falta firma de autorización biométrica (`T-025`).
     - Integración `I-03` falló: solo 14/20 llamadas exitosas y superó límite de tasa con 240 llamadas/min (`REQ-INT §5`).
     - Formulario propio `F-01` tiene solo 12 ejemplos (mínimo 20) y está en estado `recibido` (`POL-FOR §2`).
     - Falta firma de transferencia internacional (`T-029`).
     - Tarea de salida a producción `T-030` pendiente.
4. **`ORG-08` (Aseguradora Ruta Segura - PLA-SIN):**
   - Etapa: `produccion`. Asignada a `U-I2`.
   - Caso exitoso de referencia: Todas las tareas completadas y verificadas por `U-I3`.
