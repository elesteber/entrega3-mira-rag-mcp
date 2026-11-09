"""
Herramienta FastMCP protegida de mutación sobre SQLite (PR-1, PR-6, PR-7).
MIRA CU-3 - Asistente de Incorporación de Organizaciones.

HERRAMIENTA PROTEGIDA:
marcar_tarea NO se expone al modelo de lenguaje (Gemini Flash).
Exclusivamente invocada por el backend tras confirmación humana interactiva en dos pasos.
Ejecuta la mutación atómica en tarea_eventos_cambio con control de hash anti-replay,
validación estricta fail-closed del token firmado (HMAC-SHA256 >= 32 bytes),
identidad efectiva obligatoria desde sesión confiable (PR-7) y revalidación
transaccional dentro de BEGIN IMMEDIATE contra SQLite.
"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
from typing import Any, Literal

import jwt

from backend.data.db import get_db_connection, transaction
from backend.mcp.access_control import (
    McpSecurityError,
    get_current_user_id,
    get_user_info,
    validate_e5_stage_authorization,
    validate_user_access_to_org,
)

TAREA_ID_REGEX = re.compile(r"^T-[0-9]{3}$")
# Clave HMAC por defecto de 44 bytes (>= 32 bytes / 256 bits) para cumplimiento estricto RFC 7518
DEFAULT_JWT_SECRET = "mira_secret_key_demo_2026_cu3_secure_jwt_32b"


def _verify_and_decode_token(token: str) -> dict[str, Any]:
    """
    Valida estrictamente y decodifica el token efímero de confirmación humana (PR-1, PR-6).

    Criterios de seguridad fail-closed:
    - Token no vacío y de tipo string.
    - Firma válida con algoritmo HS256 exclusivamente (algoritmos 'none', asimétricos o distintos son rechazados).
    - Verificación de expiración ('exp' obligatorio y no vencido).
    - Presencia obligatoria de claims vinculados: tarea_id, org_id, usuario_id, estado_anterior, nuevo_estado.
    - Ningún secreto ni fragmento de token se expone en mensajes de error o logs.
    """
    if not token or not isinstance(token, str) or not token.strip():
        raise McpSecurityError(
            message="Se requiere token_confirmacion para ejecutar la mutación de estado.",
            code="MISSING_CONFIRMATION_TOKEN",
        )

    jwt_secret = os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)

    try:
        # Decodificación estricta: solo algoritmo HS256, expiración obligatoria y verificación de firma
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp"], "verify_signature": True},
        )
    except jwt.ExpiredSignatureError:
        raise McpSecurityError(
            message="El token de confirmación ha expirado (TTL máximo de 5 minutos excedido).",
            code="TOKEN_EXPIRED",
        )
    except jwt.InvalidAlgorithmError:
        raise McpSecurityError(
            message="Algoritmo de firma de token no permitido o inseguro.",
            code="INVALID_TOKEN_ALGORITHM",
        )
    except jwt.InvalidTokenError:
        raise McpSecurityError(
            message="Token de confirmación inválido, alterado o no firmado criptográficamente.",
            code="INVALID_CONFIRMATION_TOKEN",
        )
    except Exception:
        raise McpSecurityError(
            message="Error durante la validación criptográfica del token de confirmación.",
            code="INVALID_CONFIRMATION_TOKEN",
        )

    # Normalizar y validar claims obligatorios vinculados
    token_tarea_id = payload.get("tarea_id")
    token_org_id = payload.get("org_id") or payload.get("organizacion")
    token_usuario_id = payload.get("usuario_id") or payload.get("usuario") or payload.get("operador")
    token_estado_anterior = payload.get("estado_anterior")
    token_nuevo_estado = payload.get("nuevo_estado")

    missing_claims = []
    if not token_tarea_id:
        missing_claims.append("tarea_id")
    if not token_org_id:
        missing_claims.append("org_id")
    if not token_usuario_id:
        missing_claims.append("usuario_id")
    if not token_estado_anterior:
        missing_claims.append("estado_anterior")
    if not token_nuevo_estado:
        missing_claims.append("nuevo_estado")

    if missing_claims:
        raise McpSecurityError(
            message=f"El token carece de claims obligatorios requeridos: {', '.join(missing_claims)}.",
            code="MISSING_TOKEN_CLAIMS",
            details={"missing_claims": missing_claims},
        )

    payload["tarea_id"] = token_tarea_id
    payload["org_id"] = token_org_id
    payload["usuario_id"] = token_usuario_id
    payload["estado_anterior"] = token_estado_anterior
    payload["nuevo_estado"] = token_nuevo_estado

    return payload


def marcar_tarea(
    tarea_id: str,
    nuevo_estado: Literal["pendiente", "en_curso", "completada"],
    token_confirmacion: str,
    justificacion: str | None = None,
    usuario_id: str | None = None,
) -> dict[str, Any]:
    """
    HERRAMIENTA PROTEGIDA DE MUTACIÓN. NO EXPUESTA AL LLM (PR-1, PR-6).
    Registra un evento en tarea_eventos_cambio dentro de una transacción atómica SQLite
    con hash anti-replay, validación criptográfica del token y revalidación de concurrencia.

    Parámetros:
    - tarea_id: Identificador de la tarea (ej. T-006).
    - nuevo_estado: Nuevo estado propuesto ('pendiente', 'en_curso', 'completada').
    - token_confirmacion: Token HMAC-SHA256 firmado con los claims vinculados.
    - justificacion: Justificación del operador para la mutación.
    - usuario_id: Parámetro opcional que actúa EXCLUSIVAMENTE como assertion de compatibilidad.
                  NUNCA es fuente de identidad. La identidad efectiva se obtiene de la sesión confiable.
    """
    if not TAREA_ID_REGEX.match(tarea_id):
        raise ValueError(f"Formato de tarea_id inválido: '{tarea_id}'. Debe coincidir con '^T-[0-9]{{3}}$'.")

    valid_estados = {"pendiente", "en_curso", "completada"}
    if nuevo_estado not in valid_estados:
        raise ValueError(f"Estado '{nuevo_estado}' no válido. Opciones: pendiente, en_curso, completada.")

    # 1. Identidad efectiva obligatoria desde sesión confiable (PR-7)
    effective_user_id = get_current_user_id()
    if not effective_user_id:
        raise McpSecurityError(
            message="No se encontró contexto de usuario autenticado en la sesión confiable para autorizar la mutación (PR-7).",
            code="UNAUTHENTICATED_SESSION",
        )

    # 2. Validación obligatoria y fail-closed del token firmado
    token_payload = _verify_and_decode_token(token_confirmacion)

    # 3. Verificación de identidad y assertion de usuario_id
    if token_payload["usuario_id"] != effective_user_id:
        raise McpSecurityError(
            message=f"El token fue emitido para el usuario '{token_payload['usuario_id']}', pero la sesión activa es de '{effective_user_id}'.",
            code="TOKEN_USER_MISMATCH",
            details={"token_user": token_payload["usuario_id"], "session_user": effective_user_id},
        )

    if usuario_id is not None and usuario_id != effective_user_id:
        raise McpSecurityError(
            message=f"El argumento usuario_id '{usuario_id}' discrepa de la identidad efectiva de la sesión '{effective_user_id}'.",
            code="USER_IDENTITY_MISMATCH",
            details={"argument_user": usuario_id, "session_user": effective_user_id},
        )

    # 4. Vinculación de claims del token con la operación solicitada
    if token_payload["tarea_id"] != tarea_id:
        raise McpSecurityError(
            message=f"El token fue emitido para la tarea '{token_payload['tarea_id']}', no para '{tarea_id}'.",
            code="TOKEN_TASK_MISMATCH",
        )

    if token_payload["nuevo_estado"] != nuevo_estado:
        raise McpSecurityError(
            message=f"El token fue emitido para el nuevo estado '{token_payload['nuevo_estado']}', no para '{nuevo_estado}'.",
            code="TOKEN_STATE_MISMATCH",
        )

    # 5. Cálculo del hash SHA-256 del token para control anti-replay
    token_hash = hashlib.sha256(token_confirmacion.encode("utf-8")).hexdigest()
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 6. Revalidación transaccional en SQLite con BEGIN IMMEDIATE
    with get_db_connection() as conn:
        with transaction(conn, mode="IMMEDIATE") as cursor:
            # 6.1 Control anti-replay: verificar que token_hash no exista
            cursor.execute(
                "SELECT COUNT(*) FROM tarea_eventos_cambio WHERE token_hash = ?",
                (token_hash,),
            )
            if cursor.fetchone()[0] > 0:
                raise McpSecurityError(
                    message="El token de confirmación ya ha sido consumido previamente (control anti-replay PR-6).",
                    code="TOKEN_ALREADY_USED",
                    details={"token_hash": token_hash},
                )

            # 6.2 Extraer org_id legítimo y estado efectivo actual (concurrencia optimista)
            cursor.execute(
                """
                SELECT t.org_id, t.etapa, v.estado, v.responsable
                FROM tareas t
                JOIN v_tareas_estado_efectivo v ON t.tarea_id = v.tarea_id
                WHERE t.tarea_id = ?
                """,
                (tarea_id,),
            )
            task_row = cursor.fetchone()
            if not task_row:
                raise McpSecurityError(
                    message=f"La tarea '{tarea_id}' no existe en el sistema.",
                    code="TASK_NOT_FOUND",
                )

            org_id_legitimo = task_row["org_id"]
            etapa = task_row["etapa"]
            estado_actual = task_row["estado"]

            # 6.3 Revalidar vinculación del token con la organización en base de datos
            if token_payload["org_id"] != org_id_legitimo:
                raise McpSecurityError(
                    message=f"La organización en el token ('{token_payload['org_id']}') no coincide con la organización de la tarea ('{org_id_legitimo}').",
                    code="TOKEN_ORG_MISMATCH",
                    details={"token_org": token_payload["org_id"], "db_org": org_id_legitimo},
                )

            # 6.4 Revalidar que estado_anterior del token coincida con el estado actual en BD
            if token_payload["estado_anterior"] != estado_actual:
                raise McpSecurityError(
                    message=(
                        f"Conflicto de concurrencia: El estado anterior en el token ('{token_payload['estado_anterior']}') "
                        f"no coincide con el estado efectivo actual en base de datos ('{estado_actual}')."
                    ),
                    code="OPTIMISTIC_CONCURRENCY_CONFLICT",
                    details={"token_estado_anterior": token_payload["estado_anterior"], "db_estado_actual": estado_actual},
                )

            # 6.5 Control de transición válida
            if estado_actual == nuevo_estado:
                raise McpSecurityError(
                    message=f"La tarea '{tarea_id}' ya se encuentra en estado '{nuevo_estado}'.",
                    code="INVALID_STATE_TRANSITION",
                    details={"estado_actual": estado_actual, "nuevo_estado": nuevo_estado},
                )

            # 6.6 Validar permisos del usuario sobre la organización y la etapa
            user_info = get_user_info(effective_user_id, conn=conn)
            validate_user_access_to_org(org_id_legitimo, usuario_id=effective_user_id, conn=conn)
            validate_e5_stage_authorization(etapa, user_info, tarea_id)

            # 6.7 Insertar en tarea_eventos_cambio (la tabla tareas permanece inmutable)
            cursor.execute(
                """
                INSERT INTO tarea_eventos_cambio (
                    tarea_id, org_id, estado_anterior, nuevo_estado,
                    usuario_id, rol_usuario, justificacion, token_hash, fecha_cambio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tarea_id,
                    org_id_legitimo,
                    estado_actual,
                    nuevo_estado,
                    effective_user_id,
                    user_info["rol"],
                    justificacion,
                    token_hash,
                    now_utc,
                ),
            )
            evento_id = cursor.lastrowid

        return {
            "success": True,
            "evento_id": evento_id,
            "tarea_id": tarea_id,
            "org_id": org_id_legitimo,
            "nuevo_estado": nuevo_estado,
            "justificacion": justificacion,
            "fecha_cambio": now_utc,
        }
