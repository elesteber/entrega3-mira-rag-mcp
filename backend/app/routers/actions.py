"""Ruteador para los endpoints de mutación en dos pasos POST /api/action/prepare y confirm (T037, T038).

Implementa el protocolo estricto de confirmación humana interactiva (PR-1, PR-6, PR-7),
aislando la preparación de la ejecución atómica delegada al servidor FastMCP y
asegurando el control criptográfico anti-replay, la validación fail-closed y la consistencia de identidad en el servidor.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.schemas.actions import (
    ActionConfirmRequest,
    ActionConfirmResponse,
    ActionPrepareRequest,
    ActionPrepareResponse,
)
from backend.app.schemas.chat import ActionProposal
from backend.app.schemas.session import ApiError
from backend.app.security import (
    InvalidTokenError,
    SimulatedUser,
    TAREA_ID_PATTERN,
    TokenExpiredError,
    VALID_TASK_STATES,
    check_user_organization_access,
    check_user_task_mutation_permission,
    create_confirmation_token,
    get_current_user_from_header,
    verify_confirmation_token,
)
from backend.mcp.client import (
    MiraMcpClient,
    McpConnectionError,
    McpExecutionError,
    McpSecurityError,
    McpTimeoutError,
)

logger = logging.getLogger("mira_cu3.routers.actions")

router = APIRouter(prefix="/api/action", tags=["actions"])

_mcp_client_instance: Optional[MiraMcpClient] = None


def get_mcp_client() -> MiraMcpClient:
    """Retorna la instancia activa del cliente FastMCP."""
    global _mcp_client_instance
    if _mcp_client_instance is None:
        _mcp_client_instance = MiraMcpClient()
    return _mcp_client_instance


def set_mcp_client(client: Optional[MiraMcpClient]) -> None:
    """Permite inyectar un cliente MCP alternativo (para pruebas unitarias e integración)."""
    global _mcp_client_instance
    _mcp_client_instance = client


# ==============================================================================
# POST /api/action/prepare (T037, Paso 1)
# ==============================================================================

@router.post(
    "/prepare",
    response_model=ActionPrepareResponse,
    summary="Preparar propuesta de cambio de estado en tarea (Paso 1)",
    description=(
        "Genera una propuesta formal de mutación y emite un token de confirmación criptográfico efímero "
        "firmado con HMAC-SHA256 (TTL 5 min) tras validar precondiciones, estado actual y permisos del usuario (PR-1, PR-6, PR-7). "
        "No altera los registros de la base de datos ni ejecuta escrituras autónomas."
    ),
    responses={
        200: {
            "description": "Propuesta generada y token efímero emitido.",
            "model": ActionPrepareResponse,
        },
        400: {
            "description": "Transición de estado inválida, redundante o parámetros incorrectos.",
            "model": ApiError,
        },
        401: {
            "description": "Sesión de demostración no provista o inválida.",
            "model": ApiError,
        },
        403: {
            "description": "El usuario no tiene permisos sobre la organización, tarea o etapa (PR-7).",
            "model": ApiError,
        },
        404: {
            "description": "Tarea u organización no encontrada.",
            "model": ApiError,
        },
        500: {
            "description": "Error interno del servidor.",
            "model": ApiError,
        },
        502: {
            "description": "Fallo devuelto por el servidor MCP al consultar el checklist.",
            "model": ApiError,
        },
        503: {
            "description": "Servicio MCP no disponible temporalmente.",
            "model": ApiError,
        },
        504: {
            "description": "Tiempo de espera agotado al consultar el servidor MCP.",
            "model": ApiError,
        },
    },
)
async def prepare_action_endpoint(
    payload: ActionPrepareRequest,
    current_user: SimulatedUser = Depends(get_current_user_from_header),
    mcp_client: MiraMcpClient = Depends(get_mcp_client),
) -> ActionPrepareResponse:
    """Prepara una propuesta estructurada de cambio de estado sobre una tarea de incorporación."""
    # 1. Control de mínimo privilegio para rol comercial (PR-7)
    if current_user.rol == "comercial":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ACTION",
                "message": "El rol comercial no posee facultades operativas para modificar tareas (PR-7).",
                "principle_violated": "PR-7",
                "details": {
                    "usuario_id": current_user.usuario_id,
                    "rol": current_user.rol,
                },
            },
        )

    # 2. Validación sintáctica de parámetros
    clean_tarea = payload.tarea_id.strip().upper() if payload.tarea_id else ""
    if not clean_tarea or not TAREA_ID_PATTERN.match(clean_tarea):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TASK_ID",
                "message": f"Formato inválido de tarea_id: '{payload.tarea_id}'. Se esperaba 'T-XXX'.",
                "principle_violated": "PR-1",
                "details": None,
            },
        )

    clean_nuevo_est = payload.nuevo_estado.strip().lower() if payload.nuevo_estado else ""
    if clean_nuevo_est not in VALID_TASK_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TASK_STATE",
                "message": f"nuevo_estado '{payload.nuevo_estado}' no es válido. Permitidos: {sorted(VALID_TASK_STATES)}.",
                "principle_violated": "PR-1",
                "details": None,
            },
        )

    clean_justificacion = payload.justificacion.strip() if payload.justificacion else ""
    if not clean_justificacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EMPTY_JUSTIFICATION",
                "message": "La justificación de la acción es obligatoria y no puede estar vacía.",
                "principle_violated": "PR-1",
                "details": None,
            },
        )

    # 3. Determinación estricta de las organizaciones a consultar (PR-7)
    # Únicamente se consultan organizaciones dentro del ámbito autorizado del usuario.
    # Jamás se consultan organizaciones no asignadas ni se utiliza un catálogo global como fallback.
    if payload.org_id:
        target_org = payload.org_id.strip().upper()
        if not check_user_organization_access(current_user, target_org):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN_ORGANIZATION_ACCESS",
                    "message": (
                        f"El usuario {current_user.usuario_id} ({current_user.nombre}) "
                        f"no tiene permisos sobre la organización {target_org} (PR-7)."
                    ),
                    "principle_violated": "PR-7",
                    "details": {
                        "usuario_id": current_user.usuario_id,
                        "rol": current_user.rol,
                        "org_solicitada": target_org,
                        "orgs_asignadas": current_user.orgs_asignadas,
                    },
                },
            )
        orgs_to_search = [target_org]
    else:
        orgs_to_search = list(current_user.orgs_asignadas)

    # 4. Consulta de la tarea y su estado efectivo actual mediante fuente MCP confiable de lectura
    found_task: Optional[Dict[str, Any]] = None
    found_org: Optional[str] = None

    try:
        for org in orgs_to_search:
            chk_res = await mcp_client.call_tool(
                "checklist_organizacion",
                {"org_id": org},
                user_context=current_user,
            )
            if not chk_res.success:
                logger.error(f"Herramienta checklist_organizacion falló para {org}: {chk_res.error}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail={
                        "code": "MCP_QUERY_FAILED",
                        "message": "No se pudo recuperar el estado de las tareas desde el servidor MCP.",
                        "principle_violated": "PR-5",
                        "details": None,
                    },
                )
            if isinstance(chk_res.data, dict):
                for t in chk_res.data.get("tareas", []):
                    if str(t.get("tarea_id", "")).strip().upper() == clean_tarea:
                        found_task = t
                        found_org = org
                        break
            if found_task:
                break
    except HTTPException:
        raise
    except McpConnectionError as e:
        logger.error(f"Fallo de conexión MCP durante prepare: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MCP_CONNECTION_ERROR",
                "message": "No se pudo conectar con el servicio MCP para consultar el estado de la tarea.",
                "principle_violated": "PR-5",
                "details": None,
            },
        ) from None
    except McpTimeoutError as e:
        logger.error(f"Timeout MCP durante prepare: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": "MCP_TIMEOUT_ERROR",
                "message": "Tiempo de espera agotado al consultar el estado de la tarea en MCP.",
                "principle_violated": "PR-5",
                "details": None,
            },
        ) from None
    except Exception as e:
        logger.exception(f"Error inesperado al consultar checklist en prepare: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ACTION_ERROR",
                "message": "Ha ocurrido un error interno al verificar el estado de la tarea.",
                "principle_violated": None,
                "details": None,
            },
        ) from None

    # 5. Si la tarea no se encontró dentro del ámbito autorizado:
    # Se responde 404 genérico sin revelar si la tarea existe en otras organizaciones (PR-7).
    if not found_task or not found_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "TASK_NOT_FOUND",
                "message": f"La tarea {clean_tarea} no fue encontrada en las organizaciones autorizadas.",
                "principle_violated": "PR-1",
                "details": None,
            },
        )

    # 6. Comprobación de permisos por rol, organización y etapa (PR-7)
    etapa = str(found_task.get("etapa", "")).strip().upper()
    is_authorized, err_msg = check_user_task_mutation_permission(current_user, found_org, etapa)
    if not is_authorized:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_TASK_MUTATION",
                "message": err_msg or "Usuario no autorizado para modificar esta tarea.",
                "principle_violated": "PR-7",
                "details": {
                    "tarea_id": clean_tarea,
                    "org_id": found_org,
                    "etapa": etapa,
                    "rol": current_user.rol,
                },
            },
        )

    # 7. Rechazar transiciones inválidas o redundantes
    estado_actual = str(found_task.get("estado", "")).strip().lower()
    if estado_actual == clean_nuevo_est:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REDUNDANT_TRANSITION",
                "message": (
                    f"Transición redundante: la tarea {clean_tarea} ya se encuentra "
                    f"en el estado solicitado ('{estado_actual}')."
                ),
                "principle_violated": "PR-1",
                "details": {
                    "tarea_id": clean_tarea,
                    "estado_actual": estado_actual,
                    "nuevo_estado": clean_nuevo_est,
                },
            },
        )

    # 8. Generar token criptográfico efímero (TTL 5 min) con vinculación a identidad y estados
    token, _, expires_at = create_confirmation_token(
        usuario_id=current_user.usuario_id,
        tarea_id=clean_tarea,
        org_id=found_org,
        estado_actual=estado_actual,
        nuevo_estado=clean_nuevo_est,
        justificacion=clean_justificacion,
    )

    proposal = ActionProposal(
        action_type="CAMBIO_ESTADO_TAREA",
        tarea_id=clean_tarea,
        org_id=found_org,
        estado_actual=estado_actual,
        estado_propuesto=clean_nuevo_est,
        justificacion=clean_justificacion,
        confirmation_token=token,
        expires_at=expires_at,
    )

    return ActionPrepareResponse(proposal=proposal)


# ==============================================================================
# POST /api/action/confirm (T038, Paso 2)
# ==============================================================================

@router.post(
    "/confirm",
    response_model=ActionConfirmResponse,
    summary="Confirmar y ejecutar cambio de estado en tarea (Paso 2)",
    description=(
        "Valida el token efímero (firma, expiración, un solo uso mediante hash) y la coincidencia con la identidad "
        "en sesión. Invoca la mutación protegida en el servidor FastMCP dentro de una transacción atómica SQLite "
        "re-verificando el estado efectivo actual (concurrencia optimista) y registrando el evento en tarea_eventos_cambio (PR-1, PR-6)."
    ),
    responses={
        200: {
            "description": "Mutación ejecutada y registrada atómicamente en el almacén de eventos.",
            "model": ActionConfirmResponse,
        },
        400: {
            "description": "Token inválido, expirado, ya consumido o error en la mutación.",
            "model": ApiError,
        },
        401: {
            "description": "Sesión no provista o firma de sesión inválida.",
            "model": ApiError,
        },
        403: {
            "description": "Usuario no autorizado para confirmar esta acción o identidad inconsistente.",
            "model": ApiError,
        },
        409: {
            "description": "Conflicto de concurrencia optimista (el estado efectivo cambió desde la preparación).",
            "model": ApiError,
        },
        500: {
            "description": "Error interno del servidor.",
            "model": ApiError,
        },
        502: {
            "description": "Respuesta inválida, incompleta o contradictoria del servidor MCP (fail-closed).",
            "model": ApiError,
        },
        503: {
            "description": "Servicio de mutaciones MCP no disponible temporalmente.",
            "model": ApiError,
        },
        504: {
            "description": "Tiempo de espera agotado al confirmar la mutación en el servidor MCP.",
            "model": ApiError,
        },
    },
)
async def confirm_action_endpoint(
    payload: ActionConfirmRequest,
    current_user: SimulatedUser = Depends(get_current_user_from_header),
    mcp_client: MiraMcpClient = Depends(get_mcp_client),
) -> ActionConfirmResponse:
    """Ejecuta la mutación protegida tras la confirmación explícita de un operador humano."""
    # 1. Validar presencia del token
    token = payload.confirmation_token.strip() if payload.confirmation_token else ""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MISSING_CONFIRMATION_TOKEN",
                "message": "El token de confirmación es obligatorio.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    # 2. Verificar criptográficamente el token (algoritmo, firma, TTL y formato de claims)
    try:
        claims = verify_confirmation_token(token)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TOKEN_EXPIRED",
                "message": e.message,
                "principle_violated": "PR-6",
                "details": None,
            },
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TOKEN",
                "message": e.message,
                "principle_violated": "PR-6",
                "details": None,
            },
        ) from e

    # 3. Comparar identidad de la sesión activa con la identidad vinculada en el token (PR-1, PR-7)
    token_sub = claims.get("sub") or claims.get("usuario_id")
    if token_sub != current_user.usuario_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "IDENTITY_MISMATCH",
                "message": (
                    f"El usuario autenticado en sesión ({current_user.usuario_id}) no coincide "
                    f"con la identidad que preparó la propuesta de confirmación ({token_sub}) (PR-1, PR-6, PR-7)."
                ),
                "principle_violated": "PR-7",
                "details": {
                    "usuario_sesion": current_user.usuario_id,
                    "usuario_token": token_sub,
                },
            },
        )

    # 4. Validar permisos nuevamente en el servidor
    if current_user.rol == "comercial":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ACTION",
                "message": "El rol comercial no posee facultades operativas para mutar tareas (PR-7).",
                "principle_violated": "PR-7",
                "details": None,
            },
        )

    token_org = claims.get("org_id", "")
    if not check_user_organization_access(current_user, token_org):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ORGANIZATION_ACCESS",
                "message": f"El usuario {current_user.usuario_id} no tiene autorización sobre la organización {token_org} (PR-7).",
                "principle_violated": "PR-7",
                "details": {"usuario_id": current_user.usuario_id, "org_id": token_org},
            },
        )

    # 5. Invocar la herramienta protegida marcar_tarea mediante el cliente MCP
    try:
        mcp_result = await mcp_client.execute_confirmed_mutation(
            tarea_id=claims["tarea_id"],
            nuevo_estado=claims["nuevo_estado"],
            token_confirmacion=token,
            justificacion=claims.get("justificacion"),
            user_context=current_user,
        )
    except McpSecurityError:
        logger.warning("Violación de seguridad detectada en cliente MCP durante confirmación.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "MUTATION_SECURITY_ERROR",
                "message": "Operación denegada por directivas de seguridad o control de acceso en la mutación.",
                "principle_violated": "PR-7",
                "details": None,
            },
        ) from None
    except McpTimeoutError:
        logger.error("Tiempo de espera agotado al confirmar mutación en servidor MCP.")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": "MCP_TIMEOUT_ERROR",
                "message": "Tiempo de espera agotado al confirmar la mutación en el servidor MCP.",
                "principle_violated": "PR-6",
                "details": None,
            },
        ) from None
    except McpConnectionError:
        logger.error("Fallo de conexión MCP durante confirmación.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MCP_CONNECTION_ERROR",
                "message": (
                    "Error de conexión con el servicio de mutaciones MCP. "
                    "El resultado de la operación es indeterminado; no reintente automáticamente."
                ),
                "principle_violated": "PR-5",
                "details": None,
            },
        ) from None
    except McpExecutionError as e:
        err_text = str(e).lower()
        if any(k in err_text for k in ["replay", "ya utilizado", "token_hash", "duplicado", "token_already_used"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "TOKEN_ALREADY_USED",
                    "message": "El token de confirmación ya ha sido consumido previamente (control anti-replay PR-6).",
                    "principle_violated": "PR-6",
                    "details": None,
                },
            ) from None
        if any(k in err_text for k in ["concurrencia", "optimist", "conflicto", "estado efectivo", "cambió", "concurrency_conflict"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CONCURRENCY_CONFLICT",
                    "message": "Conflicto de concurrencia optimista: el estado efectivo de la tarea cambió desde la preparación.",
                    "principle_violated": "PR-6",
                    "details": None,
                },
            ) from None
        # Mensaje sanitizado sin divulgar excepciones internas, rutas ni secretos
        logger.error(f"Fallo de ejecución en mutación MCP: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MUTATION_EXECUTION_FAILED",
                "message": "No se pudo ejecutar la mutación de estado en el servidor de datos.",
                "principle_violated": "PR-6",
                "details": None,
            },
        ) from None
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error inesperado al confirmar acción: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ACTION_ERROR",
                "message": "Ha ocurrido un error interno al ejecutar la confirmación de la acción.",
                "principle_violated": None,
                "details": None,
            },
        ) from None

    # 6. Validación fail-closed de la respuesta de mutación devuelta por el servidor MCP
    if not mcp_result.success or not isinstance(mcp_result.data, dict):
        logger.error(
            f"Servidor MCP retornó resultado no exitoso o datos inválidos. success: {mcp_result.success}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "El servidor MCP no pudo confirmar la persistencia de la mutación solicitada.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    res_data = mcp_result.data

    # Validar confirmación explícita de éxito
    if res_data.get("success") is not True:
        logger.error("El servidor MCP retornó success distinto de True en el cuerpo de datos.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "La respuesta de confirmación de mutación no certifica la persistencia exitosa del cambio.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    # Validar campos obligatorios devueltos por el servidor MCP según contracts/mcp-tools.json
    res_evento_id = res_data.get("evento_id")
    if not isinstance(res_evento_id, int) or res_evento_id <= 0:
        logger.error(f"evento_id inválido o ausente en respuesta MCP: {res_evento_id}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "La respuesta del servidor MCP carece de un identificador de evento válido.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    res_fecha_cambio = res_data.get("fecha_cambio")
    if not isinstance(res_fecha_cambio, str) or not res_fecha_cambio.strip():
        logger.error("fecha_cambio ausente o inválida en respuesta MCP.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "La respuesta del servidor MCP carece de la marca de tiempo oficial del evento.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    res_tarea_id = res_data.get("tarea_id")
    if not isinstance(res_tarea_id, str) or res_tarea_id.strip().upper() != claims["tarea_id"].strip().upper():
        logger.error(
            f"Discrepancia en tarea_id devuelto por MCP ({res_tarea_id}) vs token ({claims['tarea_id']})"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "Discrepancia entre la tarea confirmada por MCP y la requerida en el token.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    res_org_id = res_data.get("org_id")
    if not isinstance(res_org_id, str) or res_org_id.strip().upper() != claims["org_id"].strip().upper():
        logger.error(
            f"Discrepancia en org_id devuelto por MCP ({res_org_id}) vs token ({claims['org_id']})"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "Discrepancia entre la organización confirmada por MCP y la requerida en el token.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    res_nuevo_estado = res_data.get("nuevo_estado")
    if not isinstance(res_nuevo_estado, str) or res_nuevo_estado.strip().lower() != claims["nuevo_estado"].strip().lower():
        logger.error(
            f"Discrepancia en nuevo_estado devuelto por MCP ({res_nuevo_estado}) vs token ({claims['nuevo_estado']})"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "Discrepancia entre el estado efectivo confirmado por MCP y el solicitado.",
                "principle_violated": "PR-6",
                "details": None,
            },
        )

    # Validar coincidencia de usuario si viene en los datos del evento
    res_usuario_id = res_data.get("usuario_id")
    if res_usuario_id is not None and str(res_usuario_id).strip().upper() != current_user.usuario_id:
        logger.error(
            f"Discrepancia en usuario_id devuelto por MCP ({res_usuario_id}) vs sesión ({current_user.usuario_id})"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "MUTATION_CONFIRMATION_INVALID",
                "message": "Discrepancia entre la identidad registrada por MCP y la sesión autenticada.",
                "principle_violated": "PR-7",
                "details": None,
            },
        )

    return ActionConfirmResponse(
        success=True,
        evento_id=res_evento_id,
        tarea_id=res_tarea_id.strip().upper(),
        org_id=res_org_id.strip().upper(),
        nuevo_estado=res_nuevo_estado.strip().lower(),
        usuario_id=current_user.usuario_id,
        justificacion=res_data.get("justificacion") or claims.get("justificacion"),
        fecha_cambio=res_fecha_cambio.strip(),
    )
