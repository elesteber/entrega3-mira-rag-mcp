"""Ruteador de sesiones simuladas de demostración para MIRA CU-3 (PR-7).

Proporciona los endpoints:
- GET /api/session/users: Lista los 4 usuarios disponibles del kit CU-3.
- POST /api/session/switch: Conmuta la identidad activa y emite un JWT de sesión firmado.

AVISO DE ALCANCE ACADÉMICO:
Este selector implementa una simulación de identidad para evaluación y demostración académica.
No debe presentarse como un sistema de autenticación empresarial en producción (SAML/OIDC).
"""

from typing import List
from fastapi import APIRouter, HTTPException, status

from backend.app.schemas.session import ApiError, SwitchSessionRequest
from backend.app.security import (
    SimulatedUser,
    SessionTokenResponse,
    get_simulated_user,
    list_simulated_users,
    create_session_token,
    InvalidTokenError,
)

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get(
    "/users",
    response_model=List[SimulatedUser],
    summary="Listar usuarios simulados de demostración",
    description=(
        "Retorna la lista de identidades reales del personal de DPRIME presentes en el kit "
        "(tabla usuarios), con sus roles y organizaciones asignadas para el selector de demostración académica."
    ),
    responses={
        200: {
            "description": "Lista de usuarios de demostración disponible.",
            "model": List[SimulatedUser],
        }
    },
)
def get_session_users() -> List[SimulatedUser]:
    """Retorna los 4 usuarios del kit CU-3 sin exponer secretos ni credenciales."""
    return list_simulated_users()


@router.post(
    "/switch",
    response_model=SessionTokenResponse,
    summary="Cambiar usuario simulado activo",
    description=(
        "Emite una sesión de demostración administrada y firmada por el backend para el usuario seleccionado. "
        "Aviso: Esta simulación es exclusiva para evaluación académica y demostración (PR-7)."
    ),
    responses={
        200: {
            "description": "Sesión de demostración emitida exitosamente.",
            "model": SessionTokenResponse,
        },
        400: {
            "description": "Identificador de usuario no válido.",
            "model": ApiError,
        },
    },
)
def switch_session_user(payload: SwitchSessionRequest) -> SessionTokenResponse:
    """Conmuta la identidad de demostración activa y emite un token JWT firmado."""
    raw_user_id = payload.user_id.strip() if payload.user_id else ""
    user = get_simulated_user(raw_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_USER_ID",
                "message": (
                    f"El identificador de usuario '{payload.user_id}' no es válido o no existe en el kit. "
                    "Usuarios permitidos: U-I1, U-I2, U-I3, U-I4."
                ),
                "principle_violated": "PR-7",
                "details": None,
            },
        )

    try:
        token, user_model, expires_at = create_session_token(user.usuario_id)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_USER_ID",
                "message": e.message,
                "principle_violated": "PR-7",
                "details": None,
            },
        ) from e

    return SessionTokenResponse(
        session_token=token,
        user=user_model,
        expires_at=expires_at,
    )
