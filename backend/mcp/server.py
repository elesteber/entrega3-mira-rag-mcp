"""
Servidor FastMCP interoperable para MIRA CU-3 (Asistente de Incorporación de Organizaciones).
Registra modularmente herramientas de consulta (RAG + SQL parametrizado) y mutación protegida (PR-1, PR-5, PR-6, PR-7).
"""

from __future__ import annotations

from backend.mcp.transport_auth import DelegationMiddleware
from fastmcp import FastMCP

from backend.mcp.tools.mutation_tools import marcar_tarea
from backend.mcp.tools.rag_tools import buscar_reglas
from backend.mcp.tools.sql_tools import (
    checklist_organizacion,
    consultar_formularios,
    consultar_integracion,
    listar_plantillas,
)

# Instancia central del servidor FastMCP
mcp = FastMCP(
    name="mira-cu3-server",
    middleware=[DelegationMiddleware()],
)

# 1. Registro de herramientas de consulta (expuestas al LLM)
mcp.tool()(buscar_reglas)
mcp.tool()(checklist_organizacion)
mcp.tool()(listar_plantillas)
mcp.tool()(consultar_integracion)
mcp.tool()(consultar_formularios)

# 2. Registro de herramienta protegida de mutación (no expuesta a Gemini)
mcp.tool()(marcar_tarea)


def main():
    """Punto de entrada CLI para ejecutar el servidor MCP vía stdio."""
    mcp.run()


if __name__ == "__main__":
    main()

