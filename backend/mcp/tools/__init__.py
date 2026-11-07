"""
Herramientas modulares FastMCP para MIRA CU-3.
"""

from backend.mcp.tools.mutation_tools import marcar_tarea
from backend.mcp.tools.rag_tools import buscar_reglas
from backend.mcp.tools.sql_tools import (
    checklist_organizacion,
    consultar_formularios,
    consultar_integracion,
    listar_plantillas,
)

__all__ = [
    "buscar_reglas",
    "checklist_organizacion",
    "listar_plantillas",
    "consultar_integracion",
    "consultar_formularios",
    "marcar_tarea",
]

