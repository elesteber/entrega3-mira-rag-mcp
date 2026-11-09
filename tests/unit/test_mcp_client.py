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
def mock_mcp_server(mcp_delegation_env):
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
        u1 = SimulatedUser(usuario_id="U-I1", nombre="Sofía Tapia", rol="ejecutivo_implementacion", orgs_asignadas=["ORG-05"])
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            result = await client.call_tool_for_llm(
                "buscar_reglas",
                {"query": "requisitos SFTP", "top_k": 3},
                user_context=u1,
            )
            assert result.success is True
            assert result.tool_name == "buscar_reglas"
            assert result.data["total_found"] == 1
            assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_confirmed_mutation_requires_token(self, mock_mcp_server):
        u1 = SimulatedUser(usuario_id="U-I1", nombre="Sofía Tapia", rol="ejecutivo_implementacion", orgs_asignadas=["ORG-05"])
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            with pytest.raises(McpSecurityError) as exc_info:
                await client.execute_confirmed_mutation(
                    tarea_id="T-006",
                    nuevo_estado="completada",
                    token_confirmacion="",
                    user_context=u1,
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
        u1 = SimulatedUser(usuario_id="U-I1", nombre="Sofía Tapia", rol="ejecutivo_implementacion", orgs_asignadas=["ORG-05"])
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            with pytest.raises(McpExecutionError) as exc_info:
                await client.call_tool("failing_tool", {}, user_context=u1)
            assert "Fallo" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_tool_timeout_handling(self, mock_mcp_server):
        u1 = SimulatedUser(usuario_id="U-I1", nombre="Sofía Tapia", rol="ejecutivo_implementacion", orgs_asignadas=["ORG-05"])
        # Configurar timeout muy breve (0.1s)
        async with MiraMcpClient(transport=mock_mcp_server, timeout=0.1) as client:
            with pytest.raises(McpTimeoutError) as exc_info:
                await client.call_tool("slow_tool", {}, user_context=u1)
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
            "mira_delegation": "eyJhbGciOiJIUzI1NiIsInR5cCI6Im1pcmEtbWNwLWRlbGVnYXRpb24rand0In0.eyJzdWIiOiJVLUkxIn0.sig",
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
        assert clean["mira_delegation"] == "[REDACTED_SECRET]"
        assert clean["user_data"]["password"] == "[REDACTED_SECRET]"
        assert clean["user_data"]["session_token"] == "[REDACTED_SECRET]"
        assert clean["user_data"]["normal_field"] == "valor_ordinario"
        assert clean["random_jwt"] == "[REDACTED_JWT]"

    @pytest.mark.asyncio
    async def test_traces_are_recorded_and_sanitized(self, mock_mcp_server):
        u1 = SimulatedUser(usuario_id="U-I1", nombre="Sofía Tapia", rol="ejecutivo_implementacion", orgs_asignadas=["ORG-05"])
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            client.clear_traces()
            await client.execute_confirmed_mutation(
                tarea_id="T-006",
                nuevo_estado="completada",
                token_confirmacion="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake.signature",
                user_context=u1,
            )
            traces = client.get_traces()
            assert len(traces) == 1
            trace = traces[0]
            assert trace.tool_name == "marcar_tarea"
            assert trace.success is True
            # Comprobar que en argumentos y salida se censuró el token
            assert trace.sanitized_arguments["token_confirmacion"] == "[REDACTED_SECRET]"
            assert trace.sanitized_output["token_confirmacion"] == "[REDACTED_SECRET]"


class TestMcpDelegationAuthentication:
    """Pruebas del mecanismo de autenticación por delegación MCP (AUD-03, PR-7)."""

    def test_delegation_token_contract_and_structure(self, mcp_delegation_env):
        """Verifica que el JWT de delegación cumpla estrictamente el contrato acordado con FastMCP."""
        import jwt
        from backend.app.security import (
            create_mcp_delegation_token,
            verify_mcp_delegation_token,
            MCP_DELEGATION_TYP,
            MCP_DELEGATION_TOKEN_TYPE,
            MCP_DELEGATION_ISSUER,
            MCP_DELEGATION_AUDIENCE,
        )

        u1 = SimulatedUser(
            usuario_id="U-I1",
            nombre="Sofía Tapia",
            rol="ejecutivo_implementacion",
            orgs_asignadas=["ORG-05", "ORG-07"],
        )
        token = create_mcp_delegation_token(u1)
        assert isinstance(token, str)

        header = jwt.get_unverified_header(token)
        assert header.get("typ") == MCP_DELEGATION_TYP
        assert header.get("alg") == "HS256"

        payload = verify_mcp_delegation_token(token)
        assert payload["sub"] == "U-I1"
        assert payload["iss"] == MCP_DELEGATION_ISSUER
        assert payload["aud"] == MCP_DELEGATION_AUDIENCE
        assert payload["token_type"] == MCP_DELEGATION_TOKEN_TYPE
        assert type(payload["iat"]) is int
        assert type(payload["exp"]) is int
        assert 0 < (payload["exp"] - payload["iat"]) <= 300
        assert isinstance(payload["jti"], str) and len(payload["jti"].strip()) > 0

        # Contrato AUD-03: Sin roles ni organizaciones en los claims del token
        assert "rol" not in payload
        assert "roles" not in payload
        assert "orgs" not in payload
        assert "orgs_asignadas" not in payload

    def test_delegation_token_rejection_on_invalid_secrets(self, mcp_delegation_env):
        """Verifica rechazo de secretos débiles, ausentes, idénticos a JWT_SECRET o inseguros conocidos."""
        from backend.app.config import get_settings
        from backend.app.security import (
            create_mcp_delegation_token,
            validate_mcp_delegation_secret,
            SecurityError,
        )

        u1 = SimulatedUser(
            usuario_id="U-I1",
            nombre="Sofía Tapia",
            rol="ejecutivo_implementacion",
            orgs_asignadas=["ORG-05"],
        )
        jwt_sec = get_settings().JWT_SECRET

        # 1. Secreto ausente o vacío
        with pytest.raises(SecurityError) as exc_info:
            validate_mcp_delegation_secret("", jwt_secret=jwt_sec)
        assert exc_info.value.code == "MCP_DELEGATION_SECRET_MISSING"

        # 2. Secreto demasiado corto (< 32 bytes)
        with pytest.raises(SecurityError) as exc_info:
            validate_mcp_delegation_secret("corto_de_20_caracter", jwt_secret=jwt_sec)
        assert exc_info.value.code == "MCP_DELEGATION_SECRET_TOO_SHORT"

        # 3. Secreto idéntico a JWT_SECRET
        with pytest.raises(SecurityError) as exc_info:
            validate_mcp_delegation_secret(jwt_sec, jwt_secret=jwt_sec)
        assert exc_info.value.code == "MCP_DELEGATION_SECRET_IDENTICAL_TO_JWT"

        # 4. Secreto inseguro conocido o histórico
        with pytest.raises(SecurityError) as exc_info:
            validate_mcp_delegation_secret("super-secret-key-change-in-production", jwt_secret=jwt_sec)
        assert exc_info.value.code == "MCP_DELEGATION_SECRET_INSECURE"

    @pytest.mark.asyncio
    async def test_mcp_calls_rejected_without_authenticated_user_context(self, mock_mcp_server):
        """Verifica que cualquier invocación al servidor MCP sin usuario autenticado sea rechazada (PR-7)."""
        async with MiraMcpClient(transport=mock_mcp_server) as client:
            # Consulta para LLM sin usuario
            with pytest.raises(McpSecurityError) as exc_info:
                await client.call_tool_for_llm("buscar_reglas", {"query": "normas"}, user_context=None)
            assert "usuario autenticado" in str(exc_info.value).lower()

            # Invocación directa sin usuario
            with pytest.raises(McpSecurityError) as exc_info:
                await client.call_tool("checklist_organizacion", {"org_id": "ORG-05"}, user_context=None)
            assert "usuario autenticado" in str(exc_info.value).lower()

            # Mutación confirmada sin usuario
            with pytest.raises(McpSecurityError) as exc_info:
                await client.execute_confirmed_mutation(
                    tarea_id="T-006",
                    nuevo_estado="completada",
                    token_confirmacion="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.sig",
                    user_context=None,
                )
            assert "usuario autenticado" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_mcp_calls_transmit_mira_delegation_metadata(self, mcp_delegation_env):
        """Verifica que el cliente pase meta={'mira_delegation': token} a la llamada interna de FastMCP."""
        from unittest.mock import AsyncMock, MagicMock
        from backend.mcp.client import McpToolResult

        client = MiraMcpClient()
        mock_raw_result = MagicMock()
        mock_raw_result.is_error = False
        mock_raw_result.data = {"resultado": "ok"}
        mock_raw_result.content = []

        mock_fastmcp = MagicMock()
        mock_fastmcp.call_tool = AsyncMock(return_value=mock_raw_result)
        client._client = mock_fastmcp
        client._is_connected = True

        u1 = SimulatedUser(
            usuario_id="U-I1",
            nombre="Sofía Tapia",
            rol="ejecutivo_implementacion",
            orgs_asignadas=["ORG-05"],
        )

        res = await client.call_tool_for_llm("buscar_reglas", {"query": "plazos"}, user_context=u1)
        assert res.success is True

        # Verificar que call_tool recibió el keyword argument meta con mira_delegation
        assert mock_fastmcp.call_tool.called
        call_kwargs = mock_fastmcp.call_tool.call_args.kwargs
        assert "meta" in call_kwargs
        meta = call_kwargs["meta"]
        assert "mira_delegation" in meta
        token = meta["mira_delegation"]
        assert isinstance(token, str) and token.count(".") == 2

    @pytest.mark.asyncio
    async def test_mcp_mutation_and_call_tool_transmit_mira_delegation(self, mcp_delegation_env):
        """Verifica que execute_confirmed_mutation y call_tool también transmitan la delegación por meta."""
        from unittest.mock import AsyncMock, MagicMock

        client = MiraMcpClient()
        mock_raw_result = MagicMock()
        mock_raw_result.is_error = False
        mock_raw_result.data = {"resultado": "ok"}
        mock_raw_result.content = []

        mock_fastmcp = MagicMock()
        mock_fastmcp.call_tool = AsyncMock(return_value=mock_raw_result)
        client._client = mock_fastmcp
        client._is_connected = True

        u1 = SimulatedUser(
            usuario_id="U-I1",
            nombre="Sofía Tapia",
            rol="ejecutivo_implementacion",
            orgs_asignadas=["ORG-05"],
        )

        # 1. Invocación administrativa call_tool
        await client.call_tool("checklist_organizacion", {"org_id": "ORG-05"}, user_context=u1)
        assert mock_fastmcp.call_tool.called
        meta = mock_fastmcp.call_tool.call_args.kwargs.get("meta", {})
        assert "mira_delegation" in meta
        assert isinstance(meta["mira_delegation"], str)

        # 2. Mutación confirmada execute_confirmed_mutation
        mock_fastmcp.call_tool.reset_mock()
        await client.execute_confirmed_mutation(
            tarea_id="T-006",
            nuevo_estado="completada",
            token_confirmacion="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.sig",
            user_context=u1,
        )
        assert mock_fastmcp.call_tool.called
        meta_mut = mock_fastmcp.call_tool.call_args.kwargs.get("meta", {})
        assert "mira_delegation" in meta_mut
        assert isinstance(meta_mut["mira_delegation"], str)

    def test_interoperability_with_pr7_server_contract(self, mcp_delegation_env):
        """Valida que la credencial emitida sea aceptada por el algoritmo de verify_delegation de Rodrigo."""
        import os
        import time
        import jwt
        from backend.app.config import get_settings
        from backend.app.security import create_mcp_delegation_token

        u1 = SimulatedUser(
            usuario_id="U-I1",
            nombre="Sofía Tapia",
            rol="ejecutivo_implementacion",
            orgs_asignadas=["ORG-05"],
        )
        token = create_mcp_delegation_token(u1)
        settings = get_settings()

        # Algoritmo idéntico a backend/mcp/transport_auth.py:verify_delegation (PR #7 / AUD-03)
        secret = settings.MIRA_MCP_DELEGATION_SECRET
        assert len(secret.encode("utf-8")) >= 32
        assert secret != "super-secret-key-change-in-production"
        assert secret != settings.JWT_SECRET

        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="mira-cu3-mcp",
            issuer="mira-api",
            options={
                "require": ["sub", "iss", "aud", "exp", "iat", "jti", "token_type"],
                "strict_aud": True,
            },
        )
        assert jwt.get_unverified_header(token).get("typ") == "mira-mcp-delegation+jwt"
        assert payload["token_type"] == "mcp_delegation"
        assert all(type(payload[k]) is int for k in ("iat", "exp"))
        assert 0 < payload["exp"] - payload["iat"] <= 300
        assert payload["iat"] <= time.time()
        assert all(isinstance(payload[k], str) and payload[k].strip() for k in ("sub", "jti"))
        assert payload["sub"] == "U-I1"

    def test_delegation_secret_with_surrounding_whitespace_preserved_consistently(self):
        """Regresión: Verifica que un secreto con espacios iniciales o finales preserve sus bytes literales sin strip()."""
        import jwt
        from backend.app.security import (
            create_mcp_delegation_token,
            verify_mcp_delegation_token,
        )

        raw_secret_with_spaces = "  secreto-con-espacios-al-inicio-y-final-32b  "
        u1 = SimulatedUser(
            usuario_id="U-I1",
            nombre="Sofía Tapia",
            rol="ejecutivo_implementacion",
            orgs_asignadas=["ORG-05"],
        )

        # 1. Emisión con secreto literal con espacios
        token = create_mcp_delegation_token(u1, secret_override=raw_secret_with_spaces)

        # 2. verify_mcp_delegation_token decodifica exitosamente con el secreto literal
        payload = verify_mcp_delegation_token(token, secret_override=raw_secret_with_spaces)
        assert payload["sub"] == "U-I1"

        # 3. Si se intentara verificar con secret.strip(), la firma HMAC falla
        stripped_secret = raw_secret_with_spaces.strip()
        with pytest.raises(Exception):
            verify_mcp_delegation_token(token, secret_override=stripped_secret)

        # 4. Decodificación simulando FastMCP transport_auth.py:verify_delegation con la clave exacta
        decoded_server = jwt.decode(
            token,
            raw_secret_with_spaces,
            algorithms=["HS256"],
            audience="mira-cu3-mcp",
            issuer="mira-api",
            options={"require": ["sub", "iss", "aud", "exp", "iat", "jti", "token_type"], "strict_aud": True},
        )
        assert decoded_server["sub"] == "U-I1"

    @pytest.mark.asyncio
    async def test_fails_safely_when_mira_mcp_delegation_secret_is_missing(self, monkeypatch):
        """Verifica que sin MIRA_MCP_DELEGATION_SECRET configurado el sistema falle de forma segura sin inventar secretos."""
        from backend.app.config import get_settings
        from backend.app.security import (
            create_mcp_delegation_token,
            validate_mcp_delegation_secret,
            SecurityError,
        )

        monkeypatch.delenv("MIRA_MCP_DELEGATION_SECRET", raising=False)
        get_settings.cache_clear()

        # 1. validate_mcp_delegation_secret falla con código específico
        with pytest.raises(SecurityError) as exc_val:
            validate_mcp_delegation_secret(get_settings().MIRA_MCP_DELEGATION_SECRET)
        assert exc_val.value.code == "MCP_DELEGATION_SECRET_MISSING"

        # 2. create_mcp_delegation_token falla de forma segura
        u1 = SimulatedUser(
            usuario_id="U-I1",
            nombre="Sofía Tapia",
            rol="ejecutivo_implementacion",
            orgs_asignadas=["ORG-05"],
        )
        with pytest.raises(SecurityError) as exc_tok:
            create_mcp_delegation_token(u1)
        assert exc_tok.value.code == "MCP_DELEGATION_SECRET_MISSING"

        # 3. MiraMcpClient.call_tool_for_llm falla de forma segura con McpSecurityError
        from unittest.mock import MagicMock
        client = MiraMcpClient()
        client._is_connected = True
        client._client = MagicMock()
        with pytest.raises(McpSecurityError) as exc_client:
            await client.call_tool_for_llm("buscar_reglas", {"query": "test"}, user_context=u1)
        assert "Fallo al emitir la delegación MCP" in str(exc_client.value) or "no está configurado" in str(exc_client.value)
