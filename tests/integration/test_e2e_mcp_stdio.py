"""Prueba de punta a punta: MiraMcpClient (FastAPI) -> servidor FastMCP real por stdio (AUD-03).

A diferencia de test_mcp_stdio.py (servidor mínimo sin middleware), aquí el
cliente del backend lanza backend/mcp/server.py real (PR #7 + #18) como
subproceso, con SQLite temporal y secretos aleatorios, y verifica:

1. Compatibilidad del contrato: el token emitido por el backend lo acepta el
   verificador del servidor.
2. Consultas delegadas de dos usuarios sobre el mismo proceso MCP.
3. Rechazos del servidor: sin delegación, RBAC del servidor y secreto distinto.
4. Mutación confirmada (PR-6) con registro del evento y anti-replay.
5. Mínimo privilegio: el subproceso MCP no recibe GEMINI_API_KEY.

Se omite si la rama todavía no contiene el servidor real (backend.mcp.transport_auth).
"""

from __future__ import annotations

import os
import secrets
import sqlite3

import pytest

pytest.importorskip("backend.mcp.transport_auth", reason="servidor MCP real (#7 + #18) no presente en la rama")

from backend.app.config import get_settings  # noqa: E402
from backend.app.security import (  # noqa: E402
    create_confirmation_token,
    create_mcp_delegation_token,
    get_simulated_user,
)
from backend.data.init_db import init_database  # noqa: E402
from backend.mcp.client import McpClientError, MiraMcpClient  # noqa: E402
from backend.mcp.transport_auth import verify_delegation  # noqa: E402

MARCADOR_GEMINI = "MARCADOR_GEMINI_E2E_NO_DEBE_LLEGAR_AL_MCP"


@pytest.fixture
def entorno_e2e(tmp_path, monkeypatch):
    """SQLite temporal y secretos aleatorios, restaurados al terminar (sin fugas de entorno)."""
    db = tmp_path / "mira_e2e.db"
    init_database(db_path=db, quiet=True)
    monkeypatch.setenv("SQLITE_DB_PATH", str(db))
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("MIRA_MCP_DELEGATION_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("GEMINI_API_KEY", MARCADOR_GEMINI)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    get_settings.cache_clear()
    yield db
    get_settings.cache_clear()


def _eventos(db) -> int:
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0]


def test_token_del_backend_aceptado_por_el_servidor(entorno_e2e):
    token = create_mcp_delegation_token(get_simulated_user("U-I1"))
    assert verify_delegation(token) == "U-I1"


@pytest.mark.asyncio
async def test_consultas_delegadas_y_rechazos_del_servidor(entorno_e2e):
    u1, u2 = get_simulated_user("U-I1"), get_simulated_user("U-I2")
    async with MiraMcpClient() as cliente:
        # Dos usuarios sobre el mismo proceso MCP, cada uno con su delegación.
        r1 = await cliente.call_tool("checklist_organizacion", {"org_id": "ORG-05"}, user_context=u1)
        r2 = await cliente.call_tool("checklist_organizacion", {"org_id": "ORG-06"}, user_context=u2)
        assert r1.success, r1.error
        assert r2.success, r2.error

        # Sin delegación, declarando otra identidad en los argumentos: el servidor rechaza.
        crudo = await cliente._client.call_tool(
            "checklist_organizacion", {"org_id": "ORG-06", "usuario_id": "U-I3"}, raise_on_error=False
        )
        assert crudo.is_error

        # Saltándose el chequeo del cliente: el RBAC del servidor sigue rechazando.
        crudo = await cliente._client.call_tool(
            "checklist_organizacion", {"org_id": "ORG-06"},
            meta={"mira_delegation": create_mcp_delegation_token(u1)}, raise_on_error=False,
        )
        assert crudo.is_error


@pytest.mark.asyncio
async def test_mutacion_confirmada_y_anti_replay(entorno_e2e):
    db = entorno_e2e
    u1 = get_simulated_user("U-I1")
    token, _hash, _expira = create_confirmation_token(
        "U-I1", "T-006", "ORG-05", "en_curso", "completada", "Prueba E2E AUD-03"
    )
    async with MiraMcpClient() as cliente:
        resultado = await cliente.execute_confirmed_mutation(
            "T-006", "completada", token, "Prueba E2E AUD-03", user_context=u1
        )
        assert resultado.success, resultado.error
        assert _eventos(db) == 1

        with pytest.raises(McpClientError):
            await cliente.execute_confirmed_mutation(
                "T-006", "completada", token, "Prueba E2E AUD-03", user_context=u1
            )
    assert _eventos(db) == 1


@pytest.mark.asyncio
async def test_secreto_distinto_entre_cliente_y_servidor_es_rechazado(entorno_e2e):
    servidor = {"MIRA_MCP_DELEGATION_SECRET": secrets.token_urlsafe(48)}
    async with MiraMcpClient(env=servidor) as cliente:
        with pytest.raises(McpClientError, match="Delegación MCP ausente o inválida"):
            await cliente.call_tool(
                "checklist_organizacion", {"org_id": "ORG-05"}, user_context=get_simulated_user("U-I1")
            )


@pytest.mark.asyncio
async def test_subproceso_mcp_no_recibe_gemini_api_key(entorno_e2e):
    async with MiraMcpClient() as cliente:
        env = cliente._transport.env or {}
        assert "GEMINI_API_KEY" not in env
        assert MARCADOR_GEMINI not in env.values()

        # Verificación complementaria sobre el entorno efectivo del proceso hijo
        proc = getattr(cliente._transport, "_process", None)
        if proc and hasattr(proc, "pid") and proc.pid:
            proc_environ = f"/proc/{proc.pid}/environ"
            if os.path.exists(proc_environ):
                try:
                    with open(proc_environ, "rb") as f:
                        raw = f.read().decode("utf-8", errors="ignore")
                    assert "GEMINI_API_KEY" not in raw
                    assert MARCADOR_GEMINI not in raw
                except (PermissionError, FileNotFoundError, ProcessLookupError):
                    pass
