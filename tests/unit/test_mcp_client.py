"""Pruebas unitarias para el cliente FastMCP (backend/mcp/client.py).

Verifica el ciclo de vida de la conexión, descubrimiento y filtrado de herramientas,
exclusión estricta de 'marcar_tarea' para el LLM (PR-1, PR-6), manejo de errores,
tiempos de espera y sanitización de credenciales en trazas de auditoría.
"""

import asyncio
from fastmcp import FastMCP
import pytest

from backend.app.security import SimulatedUser
from backend.mcp.client import (
    MiraMcpClient,
    McpClientError,
    McpConnectionError,
    McpExecutionError,
    McpSecurityError,
    McpTimeoutError,
    McpToolNotFoundError,
    sanitize_payload,
)


@pytest.fixture
def mock_mcp_server():
    """Servidor FastMCP en memoria aislado exclusivamente para pruebas unitarias."""
    server = FastMCP("mock_test_server")

    @server.tool(description="Consulta reglas normativas")
    def buscar_reglas(query: str, top_k: int = 4) -> dict:
        return {
            "total_found": 1,
            "results": [{"chunk_id": "GUI-INC-V2-SEC3", "query": query, "top_k": top_k}],
        }

    @server.tool(description="Consulta tareas de la organización")
    def checklist_organizacion(org_id: str) -> dict:
        return {"org_id": org_id, "tareas": ["T-001", "T-002"]}

    @server.tool(description="Herramienta que genera fallo")
    def failing_tool() -> dict:
        raise ValueError("Error forzado en herramienta de prueba")

    @server.tool(description="Herramienta lenta para prueba de timeout")
    async def slow_tool() -> dict:
        await asyncio.sleep(0.5)
        return {"status": "delayed"}

    @server.tool(description="Herramienta protegida de mutación")
    def marcar_tarea(
        tarea_id: str,
        nuevo_estado: str,
        token_confirmacion: str,
        justificacion: str | None = None,
    ) -> dict:
        return {
            "success": True,
            "tarea_id": tarea_id,
            "nuevo_estado": nuevo_estado,
            "token_confirmacion": token_confirmacion,
            "justificacion": justificacion,
        }

    return server


class TestMcpClientLifecycleAndDiscovery:
    """Pruebas del ciclo de vida y descubrimiento de herramientas."""

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, mock_mcp_server):
        client = MiraMcpClient(transport=mock_mcp_server)
        assert client.is_connected is False

        async with client:
            assert client.is_connected is True

        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_list_tools_discovery(self, mock_mcp_server):
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            tools = await client.list_tools()
            assert len(tools) >= 4
            tool_names = {t.name for t in tools}
            assert "buscar_reglas" in tool_names
            assert "checklist_organizacion" in tool_names
            assert "marcar_tarea" in tool_names

            # Comprobar clasificación de categorías
            marcar = next(t for t in tools if t.name == "marcar_tarea")
            assert marcar.category == "mutation"
            assert marcar.exposed_to_llm is False

            buscar = next(t for t in tools if t.name == "buscar_reglas")
            assert buscar.category == "query"
            assert buscar.exposed_to_llm is True

    @pytest.mark.asyncio
    async def test_get_tools_for_llm_strictly_excludes_marcar_tarea(self, mock_mcp_server):
        """Verifica que el modelo generativo jamás reciba la herramienta de mutación (PR-1, PR-6)."""
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            llm_tools = await client.get_tools_for_llm()
            tool_names = {t.name for t in llm_tools}
            assert "marcar_tarea" not in tool_names
            assert "buscar_reglas" in tool_names
            assert "checklist_organizacion" in tool_names


class TestMcpClientInvocations:
    """Pruebas de invocación controlada de herramientas y barreras de seguridad."""

    @pytest.mark.asyncio
    async def test_call_tool_for_llm_blocks_marcar_tarea(self, mock_mcp_server):
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            with pytest.raises(McpSecurityError) as exc_info:
                await client.call_tool_for_llm(
                    "marcar_tarea",
                    {"tarea_id": "T-006", "nuevo_estado": "completada"},
                )
            assert "PR-1" in str(exc_info.value)
            assert "mutación protegida" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool_for_llm_blocks_unknown_tool(self, mock_mcp_server):
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            with pytest.raises(McpToolNotFoundError):
                await client.call_tool_for_llm("herramienta_fantasma", {})

    @pytest.mark.asyncio
    async def test_call_tool_for_llm_success(self, mock_mcp_server):
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            result = await client.call_tool_for_llm(
                "buscar_reglas",
                {"query": "requisitos SFTP", "top_k": 3},
            )
            assert result.success is True
            assert result.tool_name == "buscar_reglas"
            assert result.data["total_found"] == 1
            assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_confirmed_mutation_requires_token(self, mock_mcp_server):
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            with pytest.raises(McpSecurityError) as exc_info:
                await client.execute_confirmed_mutation(
                    tarea_id="T-006",
                    nuevo_estado="completada",
                    token_confirmacion="",
                )
            assert "token_confirmacion" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_confirmed_mutation_blocks_commercial_user(self, mock_mcp_server):
        u4 = SimulatedUser(usuario_id="U-I4", nombre="Pablo Reyes", rol="comercial", orgs_asignadas=[])
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            with pytest.raises(McpSecurityError) as exc_info:
                await client.execute_confirmed_mutation(
                    tarea_id="T-006",
                    nuevo_estado="completada",
                    token_confirmacion="dummy_jwt_token",
                    user_context=u4,
                )
            assert "rol comercial" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_confirmed_mutation_success(self, mock_mcp_server):
        u1 = SimulatedUser(usuario_id="U-I1", nombre="Sofía Tapia", rol="ejecutivo_implementacion", orgs_asignadas=["ORG-05"])
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            result = await client.execute_confirmed_mutation(
                tarea_id="T-006",
                nuevo_estado="completada",
                token_confirmacion="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.sig",
                justificacion="Carpeta SFTP validada",
                user_context=u1,
            )
            assert result.success is True
            assert result.tool_name == "marcar_tarea"
            assert result.data["tarea_id"] == "T-006"
            assert result.data["nuevo_estado"] == "completada"

    @pytest.mark.asyncio
    async def test_tool_execution_error_mapped(self, mock_mcp_server):
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            with pytest.raises(McpExecutionError) as exc_info:
                await client.call_tool("failing_tool", {})
            assert "Fallo" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self, mock_mcp_server):
        # Configurar timeout muy breve (0.1s)
        async with MiraMcpClient(transport=mock_mcp_server, timeout=0.1) as client:
            with pytest.raises(McpTimeoutError) as exc_info:
                await client.call_tool("slow_tool", {})
            assert "agotado" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_missing_script_raises_connection_error(self):
        client = MiraMcpClient(script_path="/ruta/inexistente/servidor.py")
        with pytest.raises(McpConnectionError) as exc_info:
            await client.connect()
        assert "No se encontró el script" in str(exc_info.value)


class TestSanitizationAndTraces:
    """Pruebas de censura de secretos y trazabilidad auditable."""

    def test_sanitize_payload_redacts_secrets_and_jwt(self):
        dirty = {
            "tarea_id": "T-006",
            "token_confirmacion": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.secret_signature",
            "user_data": {
                "password": "super_secret_password_123",
                "normal_field": "valor_ordinario",
                "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx.yyy",
            },
            "random_jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.body.sig",
        }
        clean = sanitize_payload(dirty)

        assert clean["tarea_id"] == "T-006"
        assert clean["token_confirmacion"] == "[REDACTED_SECRET]"
        assert clean["user_data"]["password"] == "[REDACTED_SECRET]"
        assert clean["user_data"]["session_token"] == "[REDACTED_SECRET]"
        assert clean["user_data"]["normal_field"] == "valor_ordinario"
        assert clean["random_jwt"] == "[REDACTED_JWT]"

    @pytest.mark.asyncio
    async def test_traces_are_recorded_and_sanitized(self, mock_mcp_server):
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            client.clear_traces()
            await client.execute_confirmed_mutation(
                tarea_id="T-006",
                nuevo_estado="completada",
                token_confirmacion="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature",
            )
            traces = client.get_traces()
            assert len(traces) == 1
            trace = traces[0]
            assert trace.tool_name == "marcar_tarea"
            assert trace.success is True
            # Comprobar que en argumentos y salida se censuró el token
            assert trace.sanitized_arguments["token_confirmacion"] == "[REDACTED_SECRET]"
            assert trace.sanitized_output["token_confirmacion"] == "[REDACTED_SECRET]"
