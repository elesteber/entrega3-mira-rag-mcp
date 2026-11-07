"""Esquemas de datos Pydantic para los endpoints de sesión simulada (PR-7).

Define los contratos de entrada y error para /api/session/users y /api/session/switch
conforme a contracts/api-rest.yaml.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ApiError(BaseModel):
    """Modelo de error unificado de la API REST conforme a api-rest.yaml."""

    code: str = Field(description="Código semántico de error de la API")
    message: str = Field(description="Descripción legible del error")
    principle_violated: Optional[str] = Field(
        default=None,
        description="Principio operativo vulnerado si aplica (e.g., PR-1, PR-6, PR-7)",
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadatos o contexto adicional sobre la causa del error",
    )


class SwitchSessionRequest(BaseModel):
    """Cuerpo de solicitud para conmutar la identidad de demostración académica."""

    user_id: str = Field(
        description="Identificador del usuario simulado ('U-I1', 'U-I2', 'U-I3', 'U-I4')",
        examples=["U-I1"],
    )

