"""
Herramientas FastMCP relacionales de consulta sobre SQLite (PR-2, PR-5, PR-7).
MIRA CU-3 - Asistente de Incorporación de Organizaciones.

Catálogo expuesto al modelo de lenguaje (Gemini Flash):
- checklist_organizacion: Consulta el listado vivo de tareas y progreso efectivo (v_tareas_estado_efectivo).
- listar_plantillas: Consulta el catálogo de plantillas preconfiguradas y umbrales.
- consultar_integracion: Obtiene configuración técnica y telemetría de integración con detección de límites.
- consultar_formularios: Consulta formularios propios y estado de muestras recibidas.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from backend.data.db import get_db_connection
from backend.mcp.access_control import (
    McpSecurityError,
    get_current_user_id,
    validate_user_access_to_org,
)

ORG_ID_REGEX = re.compile(r"^ORG-[0-9]{2}$")


def checklist_organizacion(
    org_id: str,
    etapa: Literal["E0", "E1", "E2", "E3", "E4", "E5"] | None = None,
    usuario_id: str | None = None,
) -> dict[str, Any]:
    """
    Consulta el listado de tareas y progreso de incorporación para una organización específica autorizada,
    resolviendo el estado efectivo sobre la vista v_tareas_estado_efectivo en SQLite.
    Requiere contexto de identidad validado en el servidor (PR-5, PR-7).

    Las observaciones de campo se etiquetan explícitamente como datos no confiables de solo lectura
    para contención de inyección de prompts (PR-5, Regla 5 de AGENTS.md).
    """
    if not ORG_ID_REGEX.match(org_id):
        raise ValueError(f"Formato de org_id inválido: '{org_id}'. Debe coincidir con '^ORG-[0-9]{{2}}$'.")

    valid_etapas = {"E0", "E1", "E2", "E3", "E4", "E5", None}
    if etapa not in valid_etapas:
        raise ValueError(f"Etapa inválida: '{etapa}'. Opciones válidas: E0, E1, E2, E3, E4, E5.")

    with get_db_connection() as conn:
        # Validación de control de acceso por rol y pertenencia organizacional (PR-7)
        validate_user_access_to_org(org_id, usuario_id=usuario_id, conn=conn)

        cursor = conn.cursor()

        # Datos de la organización
        cursor.execute(
            "SELECT nombre, estado_incorporacion FROM organizaciones WHERE org_id = ?",
            (org_id,),
        )
        org_row = cursor.fetchone()
        if not org_row:
            raise McpSecurityError(
                message=f"Organización '{org_id}' no encontrada.",
                code="ORGANIZATION_NOT_FOUND",
            )
        org_nombre = org_row["nombre"]
        estado_inc = org_row["estado_incorporacion"]

        # Resumen global de progreso sobre todas las tareas de la organización
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_tareas,
                SUM(CASE WHEN estado = 'completada' THEN 1 ELSE 0 END) AS completadas,
                SUM(CASE WHEN estado = 'en_curso' THEN 1 ELSE 0 END) AS en_curso,
                SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) AS pendientes
            FROM v_tareas_estado_efectivo
            WHERE org_id = ?
            """,
            (org_id,),
        )
        sum_row = cursor.fetchone()
        total_tareas = sum_row["total_tareas"] or 0
        completadas = sum_row["completadas"] or 0
        en_curso = sum_row["en_curso"] or 0
        pendientes = sum_row["pendientes"] or 0
        porcentaje_avance = (
            round((completadas / total_tareas) * 100.0, 1) if total_tareas > 0 else 0.0
        )

        resumen_progreso = {
            "total_tareas": total_tareas,
            "completadas": completadas,
            "en_curso": en_curso,
            "pendientes": pendientes,
            "porcentaje_avance": porcentaje_avance,
        }

        # Consulta de tareas con filtro opcional de etapa
        if etapa:
            cursor.execute(
                """
                SELECT
                    tarea_id, etapa, descripcion, obligatoria, estado,
                    responsable, fecha_limite, observacion,
                    actualizado_por, fecha_ultima_actualizacion
                FROM v_tareas_estado_efectivo
                WHERE org_id = ? AND etapa = ?
                ORDER BY tarea_id ASC
                """,
                (org_id, etapa),
            )
        else:
            cursor.execute(
                """
                SELECT
                    tarea_id, etapa, descripcion, obligatoria, estado,
                    responsable, fecha_limite, observacion,
                    actualizado_por, fecha_ultima_actualizacion
                FROM v_tareas_estado_efectivo
                WHERE org_id = ?
                ORDER BY etapa ASC, tarea_id ASC
                """,
                (org_id,),
            )

        tareas_list = []
        for r in cursor.fetchall():
            obs = r["observacion"]
            # Etiquetado preventivo de datos no confiables (T057)
            task_dict = {
                "tarea_id": r["tarea_id"],
                "etapa": r["etapa"],
                "descripcion": r["descripcion"],
                "obligatoria": r["obligatoria"],
                "estado": r["estado"],
                "responsable": r["responsable"],
                "fecha_limite": str(r["fecha_limite"]),
                "observacion": obs,
                "actualizado_por": r["actualizado_por"],
                "fecha_ultima_actualizacion": (
                    str(r["fecha_ultima_actualizacion"])
                    if r["fecha_ultima_actualizacion"]
                    else None
                ),
                "es_dato_confiable": False if obs else True,
            }
            tareas_list.append(task_dict)

        return {
            "org_id": org_id,
            "organizacion_nombre": org_nombre,
            "estado_incorporacion": estado_inc,
            "resumen_progreso": resumen_progreso,
            "tareas": tareas_list,
        }


def listar_plantillas(
    plantilla_id: Literal["PLA-REM", "PLA-SIN", "PLA-CTA", "PLA-ADM"] | None = None,
) -> dict[str, Any]:
    """
    Consulta las plantillas de módulos preconfigurados del sistema MIRA (tabla plantillas en SQLite),
    detallando módulos incluidos, umbrales de aprobación sugeridos y requisitos biométricos.
    Catálogo público accesible a todos los roles autorizados (incluyendo rol comercial U-I4).
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if plantilla_id:
            cursor.execute(
                """
                SELECT
                    plantilla_id, nombre, industria, modulos,
                    umbral_aprobacion_sugerido, umbral_revision_sugerido,
                    dias_adaptacion_estimados, requiere_autorizacion_biometrica
                FROM plantillas
                WHERE plantilla_id = ?
                """,
                (plantilla_id,),
            )
        else:
            cursor.execute(
                """
                SELECT
                    plantilla_id, nombre, industria, modulos,
                    umbral_aprobacion_sugerido, umbral_revision_sugerido,
                    dias_adaptacion_estimados, requiere_autorizacion_biometrica
                FROM plantillas
                ORDER BY plantilla_id ASC
                """
            )

        plantillas_list = []
        for r in cursor.fetchall():
            plantillas_list.append(
                {
                    "plantilla_id": r["plantilla_id"],
                    "nombre": r["nombre"],
                    "industria": r["industria"],
                    "modulos": r["modulos"],
                    "umbral_aprobacion_sugerido": int(r["umbral_aprobacion_sugerido"]),
                    "umbral_revision_sugerido": int(r["umbral_revision_sugerido"]),
                    "dias_adaptacion_estimados": int(r["dias_adaptacion_estimados"]),
                    "requiere_autorizacion_biometrica": r["requiere_autorizacion_biometrica"],
                }
            )

        return {"plantillas": plantillas_list}


def consultar_integracion(
    org_id: str,
    usuario_id: str | None = None,
) -> dict[str, Any]:
    """
    Obtiene la configuración técnica y métricas de integración para una organización autorizada
    (tabla integraciones en SQLite), incluyendo modo de conexión, entorno y telemetría de pruebas.
    Detecta automáticamente excesos de tasa sobre el límite contractual (100 req/min según REQ-INT §5).
    """
    if not ORG_ID_REGEX.match(org_id):
        raise ValueError(f"Formato de org_id inválido: '{org_id}'.")

    with get_db_connection() as conn:
        validate_user_access_to_org(org_id, usuario_id=usuario_id, conn=conn)

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                integracion_id, org_id, modo, ambiente, estado,
                casos_ejemplo_enviados, llamadas_vuelta_exitosas,
                max_llamadas_por_minuto_observado
            FROM integraciones
            WHERE org_id = ?
            """,
            (org_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise McpSecurityError(
                message=f"No se encontró registro de integración para la organización '{org_id}'.",
                code="INTEGRATION_NOT_FOUND",
            )

        max_rate = int(row["max_llamadas_por_minuto_observado"])
        casos = int(row["casos_ejemplo_enviados"])
        callbacks = int(row["llamadas_vuelta_exitosas"])

        # Generar alerta técnica normativa (REQ-INT §5: máx 100 req/min, min 20 callbacks)
        alertas = []
        if max_rate > 100:
            alertas.append(
                f"Supera límite normativo contractual de 100 req/min (observado: {max_rate} req/min según REQ-INT §5)."
            )
        if casos > 0 and callbacks < casos:
            alertas.append(
                f"Registra fallos de callback: solo {callbacks} de {casos} llamadas de vuelta fueron exitosas."
            )
        elif casos == 0:
            alertas.append("No se han enviado casos de ejemplo para pruebas de integración.")

        alerta_tecnica = " ".join(alertas) if alertas else None

        return {
            "integracion_id": row["integracion_id"],
            "org_id": row["org_id"],
            "modo": row["modo"],
            "ambiente": row["ambiente"],
            "estado": row["estado"],
            "casos_ejemplo_enviados": casos,
            "llamadas_vuelta_exitosas": callbacks,
            "max_llamadas_por_minuto_observado": max_rate,
            "alerta_tecnica": alerta_tecnica,
        }


def consultar_formularios(
    org_id: str,
    usuario_id: str | None = None,
) -> dict[str, Any]:
    """
    Consulta los formularios propios definidos por una organización autorizada
    (tabla formularios_propios en SQLite), indicando conteo de muestras y estado de revisión.
    """
    if not ORG_ID_REGEX.match(org_id):
        raise ValueError(f"Formato de org_id inválido: '{org_id}'.")

    with get_db_connection() as conn:
        validate_user_access_to_org(org_id, usuario_id=usuario_id, conn=conn)

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT formulario_id, org_id, nombre, ejemplos_recibidos, fecha_ejemplos_completos, estado
            FROM formularios_propios
            WHERE org_id = ?
            ORDER BY formulario_id ASC
            """,
            (org_id,),
        )

        formularios_list = []
        for r in cursor.fetchall():
            formularios_list.append(
                {
                    "formulario_id": r["formulario_id"],
                    "org_id": r["org_id"],
                    "nombre": r["nombre"],
                    "ejemplos_recibidos": int(r["ejemplos_recibidos"]),
                    "fecha_ejemplos_completos": (
                        str(r["fecha_ejemplos_completos"])
                        if r["fecha_ejemplos_completos"]
                        else None
                    ),
                    "estado": r["estado"],
                }
            )

        return {
            "org_id": org_id,
            "formularios": formularios_list,
        }

