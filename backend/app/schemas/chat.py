"""Esquemas de datos Pydantic para el endpoint /api/chat y orquestación conversacional (PR-1 a PR-7).

Define los contratos de entrada y salida para la interacción con el asistente MIRA CU-3,
garantizando compatibilidad estricta con contracts/api-rest.yaml.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

TaskStateLiteral = Literal["pendiente", "en_curso", "completada"]
ActionTypeLiteral = Literal["CAMBIO_ESTADO_TAREA"]


class EvidenceStatusEnum(str, Enum):
    """Estado cualitativo de la evidencia documental y de sistema encontrada (PR-2, PR-3, PR-4)."""

    COMPLETA = "COMPLETA"
    PARCIAL = "PARCIAL"
    ABSTENCION = "ABSTENCION"
    CONFLICTO_FUENTES = "CONFLICTO_FUENTES"


class HistoryMessage(BaseModel):
    """Mensaje previo en el historial de conversación (con límites defensivos de entrada AUD-08)."""

    role: str = Field(description="Rol del emisor: 'user' o 'assistant'")
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="Contenido textual del mensaje previo",
    )


class ChatRequest(BaseModel):
    """Cuerpo de solicitud para el endpoint POST /api/chat (con límites de entrada AUD-08)."""

    message: str = Field(
        min_length=1,
        max_length=4000,
        description="Mensaje o consulta en lenguaje natural del usuario",
        examples=["¿Qué le falta a la organización ORG-07 para pasar a producción con la plantilla de admisión clínica?"],
    )
    organization_context: Optional[str] = Field(
        default=None,
        description="Código opcional de organización en foco (ej. 'ORG-05', 'ORG-07')",
        examples=["ORG-07"],
    )
    organization_context_is_explicit: bool = Field(
        default=False,
        description="Indica si organization_context fue seleccionado explícitamente por el usuario en la UI (True) o asignado implícitamente por el sistema (False)",
    )
    conversation_history: Optional[List[HistoryMessage]] = Field(
        default=None,
        max_length=50,
        description="Historial previo de la conversación para contexto multi-turno (máximo 50 turnos)",
    )


class Citation(BaseModel):
    """Cita formal de respaldo normativo verificado contra un chunk real de RAG (PR-2)."""

    chunk_id: str = Field(
        description="Identificador determinista del fragmento en ChromaDB",
        examples=["GUI-INC-V2-SEC3-P1"],
    )
    doc_code: str = Field(
        description="Código normalizado del documento en el corpus oficial (ej. GUI-INC, FIC-PLA)",
        examples=["GUI-INC"],
    )
    doc_title: str = Field(
        description="Título formal del documento",
        examples=["Guía Integral de Incorporación de Clientes"],
    )
    section: str = Field(
        description="Sección exacta donde se ubica el extracto normativo",
        examples=["§3"],
    )
    version: str = Field(
        description="Versión del documento fuente (ej. v1.0, v2.0)",
        examples=["v2.0"],
    )
    status: str = Field(
        description="Estado de vigencia: 'vigente', 'derogada' o 'en_revision'",
        examples=["vigente"],
    )
    excerpt: str = Field(
        description="Extracto textual literal verificado contra el fragmento recuperado",
        examples=["Una organización pasa a producción solo si se cumplen todos los criterios siguientes..."],
    )


class McpTrace(BaseModel):
    """Traza estructurada y sanitizada de invocación a herramientas FastMCP (PR-5)."""

    tool_name: str = Field(
        description="Nombre de la herramienta FastMCP invocada",
        examples=["checklist_organizacion"],
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parámetros sanitizados enviados a la herramienta (sin tokens ni secretos)",
    )
    response_summary: Optional[str] = Field(
        default=None,
        description="Resumen semántico del resultado retornado",
        examples=["10 tareas registradas (5 completadas, 1 en curso, 4 pendientes)"],
    )
    execution_time_ms: float = Field(
        description="Tiempo de ejecución en milisegundos",
        examples=[14.2],
    )
    success: bool = Field(
        description="Indica si la ejecución de la herramienta fue exitosa",
        examples=[True],
    )
    error: Optional[str] = Field(
        default=None,
        description="Detalle del error si la invocación falló",
    )


class ActionDraft(BaseModel):
    """Borrador estructurado de acción informativa sin token efímero ni vencimiento (PR-1, PR-6)."""

    action_type: ActionTypeLiteral = Field(
        default="CAMBIO_ESTADO_TAREA",
        description="Tipo de acción propuesta",
    )
    tarea_id: str = Field(
        description="Identificador de la tarea objetivo",
        examples=["T-006"],
    )
    org_id: str = Field(
        description="Código de la organización propietaria",
        examples=["ORG-05"],
    )
    estado_actual: TaskStateLiteral = Field(
        description="Estado efectivo actual de la tarea",
        examples=["en_curso"],
    )
    estado_propuesto: TaskStateLiteral = Field(
        description="Estado propuesto tras la confirmación",
        examples=["completada"],
    )
    justificacion: str = Field(
        description="Motivo o justificación documentada del cambio propuesto",
        examples=["Se habilitó carpeta SFTP compartida y se verificó recepción de archivos."],
    )


class ActionProposal(ActionDraft):
    """Propuesta estructurada de acción con token efímero para confirmación humana (PR-1, PR-6)."""

    confirmation_token: str = Field(
        description="Token criptográfico efímero firmado por el backend (TTL 5 min)",
    )
    expires_at: datetime = Field(
        description="Fecha y hora de expiración en UTC del token",
    )


class ChatResponse(BaseModel):
    """Respuesta unificada del asistente conversacional MIRA CU-3."""

    answer: str = Field(
        description="Respuesta en lenguaje natural fundamentada en evidencia documental y MCP o abstención explícita",
    )
    citations: List[Citation] = Field(
        default_factory=list,
        description="Lista de citas documentales verificables que sustentan la respuesta",
    )
    mcp_traces: List[McpTrace] = Field(
        default_factory=list,
        description="Trazas de auditoría de herramientas MCP invocadas durante la consulta",
    )
    evidence_status: EvidenceStatusEnum = Field(
        description="Estado cualitativo de la evidencia: COMPLETA, PARCIAL, ABSTENCION, CONFLICTO_FUENTES",
    )
    action_proposal: Optional[ActionDraft] = Field(
        default=None,
        description="Borrador de propuesta informativa si la consulta solicitó un cambio de estado válido (sin token efímero)",
    )
