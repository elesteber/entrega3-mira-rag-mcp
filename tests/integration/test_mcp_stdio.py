"""Prueba de integración del cliente MCP con transporte real stdio en subproceso (T013).

Verifica la comunicación punto a punto sobre el protocolo MCP entre el cliente
MiraMcpClient y un subproceso FastMCP mínimo real mediante entrada/salida estándar (stdio).
"""

import asyncio
from pathlib import Path
import tempfile
import pytest

from backend.mcp.client import MiraMcpClient, McpSecurityError


@pytest.fixture
def temp_stdio_server():
    """Genera un script temporal con un servidor FastMCP mínimo para pruebas stdio reales."""
    server_code = '''
from fastmcp import FastMCP

mcp = FastMCP("test_stdio_real_server")

@mcp.tool(description="Búsqueda de reglas normativas en RAG")
def buscar_reglas(query: str, top_k: int = 4) -> dict:
    return {
        "total_found": 1,
        "results": [
            {
                "chunk_id": "GUI-INC-V2-SEC3",
                "doc_code": "GUI-INC",
                "query": query,
                "top_k": top_k,
                "status": "vigente"
            }
        ]
    }

@mcp.tool(description="Herramienta protegida de mutación")
def marcar_tarea(tarea_id: str, nuevo_estado: str, token_confirmacion: str) -> dict:
    return {
        "success": True,
        "tarea_id": tarea_id,
        "nuevo_estado": nuevo_estado,
        "token_confirmacion": token_confirmacion
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(server_code)
        f.flush()
        temp_path = f.name

    yield temp_path

    # Limpieza
    try:
        Path(temp_path).unlink()
    except Exception:
        pass


class TestMcpStdioIntegration:
    """Verifica la interoperabilidad real con un proceso FastMCP ejecutando por stdio."""

    @pytest.mark.asyncio
    async def test_stdio_subproc_discovery_and_invocation(self, temp_stdio_server):
        async with MiraMcpClient(script_path=temp_stdio_server, timeout=10.0) as client:
            assert client.is_connected is True

            # 1. Descubrimiento dinámico de herramientas mediante el protocolo
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}
            assert "buscar_reglas" in tool_names
            assert "marcar_tarea" in tool_names

            # 2. Exclusión estricta de marcar_tarea en catálogo para el LLM (PR-1, PR-6)
            llm_tools = await client.get_tools_for_llm()
            llm_names = {t.name for t in llm_tools}
            assert "marcar_tarea" not in llm_names
            assert "buscar_reglas" in llm_names

            # 3. Invocación de consulta permitida para el LLM a través de stdio
            query_res = await client.call_tool_for_llm(
                "buscar_reglas",
                {"query": "plazos de entrega", "top_k": 2},
            )
            assert query_res.success is True
            assert query_res.tool_name == "buscar_reglas"
            assert query_res.data["total_found"] == 1
            assert query_res.data["results"][0]["query"] == "plazos de entrega"

            # 4. Bloqueo al LLM ante intento de invocar mutación
            with pytest.raises(McpSecurityError):
                await client.call_tool_for_llm("marcar_tarea", {"tarea_id": "T-006"})

            # 5. Ejecución administrativa protegida de mutación confirmada
            mutation_res = await client.execute_confirmed_mutation(
                tarea_id="T-006",
                nuevo_estado="completada",
                token_confirmacion="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_token.sig",
            )
            assert mutation_res.success is True
            assert mutation_res.data["tarea_id"] == "T-006"
            assert mutation_res.data["nuevo_estado"] == "completada"

            # 6. Comprobar que las trazas de auditoría quedaron registradas y sanitizadas
            traces = client.get_traces()
            assert len(traces) == 2
            assert traces[1].tool_name == "marcar_tarea"
            assert traces[1].sanitized_arguments["token_confirmacion"] == "[REDACTED_SECRET]"

        # Al salir del contexto, el subproceso se cierra
        assert client.is_connected is False
