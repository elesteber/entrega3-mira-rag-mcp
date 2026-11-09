"""
Control de acceso, resolución de identidad confiable en servidor y validación RBAC (PR-7).
MIRA CU-3 - Asistente de Incorporación de Organizaciones.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any

from backend.data.db import get_db_connection

# ContextVar para propagación de sesión autenticada en el hilo/corutina actual
_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


class McpSecurityError(Exception):
    """Excepción base para violaciones de seguridad y control de acceso (PR-7)."""

    def __init__(self, message: str, code: str, principle_violated: str = "PR-7", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.principle_violated = principle_violated
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": True,
            "code": self.code,
            "message": self.message,
            "principle_violated": self.principle_violated,
            "details": self.details,
        }


def set_current_user_id(usuario_id: str | None) -> None:
    """Establece la identidad del usuario autenticado para el contexto actual."""
    _current_user_id.set(usuario_id)


def get_current_user_id() -> str | None:
    """Obtiene la identidad del usuario en sesión en el contexto actual."""
    return _current_user_id.get()


def get_user_info(usuario_id: str, conn=None) -> dict[str, Any]:
    """
    Recupera el rol y las organizaciones asignadas de un usuario directamente desde SQLite.
    """
    def _fetch(connection):
        cursor = connection.cursor()
        cursor.execute("SELECT usuario_id, nombre, rol FROM usuarios WHERE usuario_id = ?", (usuario_id,))
        user_row = cursor.fetchone()
        if not user_row:
            raise McpSecurityError(
                message=f"El usuario '{usuario_id}' no existe en el sistema.",
                code="USER_NOT_FOUND",
            )
        
        user_dict = dict(user_row)
        if user_dict["rol"] == "jefe_implementacion":
            # Jefatura tiene visibilidad global de todas las organizaciones
            cursor.execute("SELECT org_id FROM organizaciones ORDER BY org_id")
            user_dict["orgs_asignadas"] = [r[0] for r in cursor.fetchall()]
        elif user_dict["rol"] == "ejecutivo_implementacion":
            # Ejecutivos solo las organizaciones donde figuran como ejecutivo_id
            cursor.execute("SELECT org_id FROM organizaciones WHERE ejecutivo_id = ? ORDER BY org_id", (usuario_id,))
            user_dict["orgs_asignadas"] = [r[0] for r in cursor.fetchall()]
        else:
            # Comercial: mínimo privilegio, ninguna organización asignada
            user_dict["orgs_asignadas"] = []

        return user_dict

    if conn is not None:
        return _fetch(conn)
    with get_db_connection() as connection:
        return _fetch(connection)


def validate_user_access_to_org(
    org_id: str,
    usuario_id: str | None = None,
    conn=None,
) -> dict[str, Any]:
    """
    Valida si el usuario en sesión tiene permisos para consultar o intervenir una organización (PR-7).
    - U-I4 (comercial): Acceso bloqueado a cualquier organización.
    - U-I1/U-I2 (ejecutivos): Solo acceden a organizaciones asignadas (U-I1: ORG-05, ORG-07; U-I2: ORG-06, ORG-08).
    - U-I3 (jefa): Acceso global.
    """
    uid = get_current_user_id()
    if not uid:
        raise McpSecurityError(
            message="Acceso denegado: Se requiere sesión de usuario autenticada para consultar datos organizacionales.",
            code="UNAUTHENTICATED_SESSION",
        )

    if usuario_id is not None and usuario_id != uid:
        raise McpSecurityError(
            message="El argumento usuario_id discrepa de la identidad autenticada.",
            code="USER_IDENTITY_MISMATCH",
        )

    user_info = get_user_info(uid, conn=conn)

    # Rol comercial no tiene acceso a datos organizacionales (mínimo privilegio FR-017)
    if user_info["rol"] == "comercial":
        raise McpSecurityError(
            message=(
                f"El usuario {uid} con rol comercial no posee permisos para consultar checklists "
                f"ni datos operativos de la organización {org_id}. Solo puede consultar documentación general y plantillas."
            ),
            code="FORBIDDEN_ROLE_ACCESS",
            details={"usuario_id": uid, "rol": "comercial", "org_id": org_id},
        )

    # Verificar existencia de la organización
    def _check_org_exists(connection):
        cursor = connection.cursor()
        cursor.execute("SELECT org_id FROM organizaciones WHERE org_id = ?", (org_id,))
        return cursor.fetchone() is not None

    exists = _check_org_exists(conn) if conn else False
    if not conn:
        with get_db_connection() as c:
            exists = _check_org_exists(c)

    if not exists:
        raise McpSecurityError(
            message=f"La organización '{org_id}' no existe en el sistema.",
            code="ORGANIZATION_NOT_FOUND",
            details={"org_id": org_id},
        )

    # Validar asignación de organización
    if org_id not in user_info["orgs_asignadas"]:
        raise McpSecurityError(
            message=f"El usuario {uid} no tiene permisos de acceso sobre la organización {org_id}.",
            code="FORBIDDEN_ORGANIZATION_ACCESS",
            details={"usuario_id": uid, "rol": user_info["rol"], "org_id": org_id},
        )

    return user_info


def validate_e5_stage_authorization(
    etapa: str,
    user_info: dict[str, Any],
    tarea_id: str,
) -> None:
    """
    Valida la restricción de que las tareas de etapa E5 solo pueden ser modificadas
    por usuarios con rol jefe_implementacion (PR-1, PR-7, FR-013, GUI-INC v2 §4).
    """
    if etapa == "E5" and user_info["rol"] != "jefe_implementacion":
        raise McpSecurityError(
            message=(
                f"La tarea de salida a producción '{tarea_id}' (etapa E5) solo puede ser autorizada "
                f"y marcada como completada por la jefatura de implementación (GUI-INC v2 §4). "
                f"El usuario {user_info['usuario_id']} ostenta el rol '{user_info['rol']}'."
            ),
            code="FORBIDDEN_STAGE_E5",
            details={"tarea_id": tarea_id, "etapa": etapa, "rol": user_info["rol"]},
        )

