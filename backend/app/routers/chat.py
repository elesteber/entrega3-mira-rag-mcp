"""Ruteador para el endpoint conversacional POST /api/chat (T020).

Expone el asistente conversacional fundamentado en RAG documental y herramientas MCP,
verificando la sesión simulada del operador en el servidor (PR-7) y aplicando
el aislamiento organizacional estricto antes de cualquier consulta.
"""

import logging
from typing import Optional, Set
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.orchestrator import MiraOrchestrator, ORG_ID_REGEX
from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.schemas.session import ApiError
from backend.app.security import (
    SimulatedUser,
    check_user_organization_access,
    get_current_user_from_header,
)

logger = logging.getLogger("mira_cu3.routers.chat")

router = APIRouter(prefix="/api", tags=["chat"])

_orchestrator_instance: Optional[MiraOrchestrator] = None


def get_orchestrator() -> MiraOrchestrator:
    """Retorna la instancia activa del orquestador conversacional."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = MiraOrchestrator()
    return _orchestrator_instance


def set_orchestrator(orchestrator: Optional[MiraOrchestrator]) -> None:
    """Permite sobrescribir la instancia del orquestador (útil para pruebas de integración)."""
    global _orchestrator_instance
    _orchestrator_instance = orchestrator


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Enviar consulta al asistente conversacional",
    description=(
        "Procesa la consulta del operador mediante orquestación RAG y MCP. "
        "La identidad se valida en el servidor mediante el token de sesión demo en "
        "Authorization: Bearer <token> o X-MIRA-Demo-Session (PR-7)."
    ),
    responses={
        200: {
            "description": "Respuesta generada con citas estructuradas y trazas MCP.",
            "model": ChatResponse,
        },
        400: {
            "description": "Solicitud malformada o mensaje vacío.",
            "model": ApiError,
        },
        401: {
            "description": "Sesión de demostración no provista o firma inválida.",
            "model": ApiError,
        },
        403: {
            "description": "Violación de control de acceso por rol u organización no asignada (PR-7).",
            "model": ApiError,
        },
        500: {
            "description": "Error interno del orquestador.",
            "model": ApiError,
        },
    },
)
async def chat_endpoint(
    payload: ChatRequest,
    current_user: SimulatedUser = Depends(get_current_user_from_header),
    orchestrator: MiraOrchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    """Endpoint principal de conversación y diagnóstico de MIRA CU-3."""
    clean_message = payload.message.strip() if payload.message else ""
    if not clean_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EMPTY_MESSAGE",
                "message": "El mensaje de la consulta no puede estar vacío.",
                "principle_violated": "PR-7",
                "details": None,
            },
        )

    # 1. Identificar TODAS las organizaciones involucradas (contexto explícito y menciones en mensaje)
    referenced_orgs: Set[str] = set()
    if payload.organization_context and payload.organization_context.strip():
        referenced_orgs.add(payload.organization_context.strip().upper())
    for match in ORG_ID_REGEX.findall(clean_message):
        referenced_orgs.add(match.strip().upper())

    # 2. Control de Acceso por Rol (PR-7): Rol comercial jamás accede a datos de organizaciones operativas
    if current_user.rol == "comercial" and referenced_orgs:
        denied_org = sorted(referenced_orgs)[0]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ORGANIZATION_ACCESS",
                "message": (
                    f"El usuario {current_user.usuario_id} ({current_user.nombre}) "
                    f"con rol comercial no tiene permisos de acceso sobre la organización {denied_org} (PR-7)."
                ),
                "principle_violated": "PR-7",
                "details": {
                    "usuario_id": current_user.usuario_id,
                    "rol": current_user.rol,
                    "org_solicitada": denied_org,
                    "orgs_asignadas": current_user.orgs_asignadas,
                },
            },
        )

    # 3. Control de Aislamiento Organizacional: Validar cada organización referenciada
    for org in referenced_orgs:
        if not check_user_organization_access(current_user, org):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN_ORGANIZATION_ACCESS",
                    "message": (
                        f"El usuario {current_user.usuario_id} ({current_user.nombre}) "
                        f"con rol '{current_user.rol}' no tiene permisos de acceso sobre la organización {org}."
                    ),
                    "principle_violated": "PR-7",
                    "details": {
                        "usuario_id": current_user.usuario_id,
                        "rol": current_user.rol,
                        "org_solicitada": org,
                        "orgs_asignadas": current_user.orgs_asignadas,
                    },
                },
            )

    # 4. Ejecución del orquestador con captura segura de excepciones internas
    try:
        response = await orchestrator.process_chat(user=current_user, request=payload)
        return response
    except HTTPException:
        # Re-lanzar excepciones HTTP legítimas (400, 401, 403) sin atraparlas en 500
        raise
    except Exception as e:
        # Logging sanitizado de la excepción interna para diagnóstico en servidor sin fugar secretos
        logger.exception(f"Error no controlado durante la orquestación conversacional en /api/chat: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ORCHESTRATOR_ERROR",
                "message": "Ha ocurrido un error interno al procesar la consulta. Intente nuevamente más tarde.",
                "principle_violated": None,
                "details": None,
            },
        ) from None
