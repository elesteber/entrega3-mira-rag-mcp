"""Esquemas de datos Pydantic para los endpoints /api/action/prepare y /api/action/confirm (T037, T038).

Define los contratos de entrada y salida para el flujo interactivo de confirmación
humana en dos pasos (PR-1, PR-6, PR-7) según contracts/api-rest.yaml.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from backend.app.schemas.chat import ActionProposal


class ActionPrepareRequest(BaseModel):
    """Cuerpo de solicitud para preparar una propuesta de cambio de estado (Paso 1)."""

    tarea_id: str = Field(
        description="Identificador de la tarea a actualizar (ej. T-006)",
        examples=["T-006"],
    )
    nuevo_estado: str = Field(
        description="Nuevo estado propuesto: 'pendiente', 'en_curso', 'completada'",
        examples=["completada"],
    )
    justificacion: str = Field(
        description="Justificación ingresada para la preparación del cambio",
        examples=["Se habilitó carpeta SFTP compartida y se verificó recepción de archivos."],
    )
    org_id: Optional[str] = Field(
        default=None,
        description="Código opcional de organización para validación explícita",
        examples=["ORG-05"],
    )


class ActionPrepareResponse(BaseModel):
    """Respuesta con la propuesta formal estructurada y el token efímero emitido."""

    proposal: ActionProposal = Field(
        description="Detalle estructurado de la acción preparada y token efímero firmado",
    )


class ActionConfirmRequest(BaseModel):
    """Cuerpo de solicitud para confirmar y ejecutar la mutación de estado (Paso 2)."""

    confirmation_token: str = Field(
        description="Token efímero firmado emitido en el flujo /api/action/prepare",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )


class ActionConfirmResponse(BaseModel):
    """Respuesta tras la ejecución atómica y registro del evento de cambio de estado."""

    success: bool = Field(
        default=True,
        description="Indica si la mutación fue persistida exitosamente",
        examples=[True],
    )
    evento_id: int = Field(
        description="Identificador secuencial del evento registrado en tarea_eventos_cambio",
        examples=[1],
    )
    tarea_id: str = Field(
        description="Identificador de la tarea actualizada",
        examples=["T-006"],
    )
    org_id: str = Field(
        description="Código de la organización propietaria de la tarea",
        examples=["ORG-05"],
    )
    nuevo_estado: str = Field(
        description="Estado efectivo resultante de la tarea",
        examples=["completada"],
    )
    usuario_id: str = Field(
        description="Identificador del usuario en sesión que confirmó la acción",
        examples=["U-I1"],
    )
    justificacion: Optional[str] = Field(
        default=None,
        description="Justificación registrada para la auditoría del cambio",
        examples=["Se habilitó carpeta SFTP compartida y se verificó recepción de archivos."],
    )
    fecha_cambio: str = Field(
        description="Marca de tiempo ISO-8601 del registro atómico del evento",
        examples=["2026-11-07T12:01:23Z"],
    )
