"""Regresiones AUD-03 con FastMCP real, proceso stdio y SQLite temporal."""

import asyncio
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time

import jwt
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from backend.data.init_db import init_database
from backend.mcp.transport_auth import TOKEN_TYPE


@pytest.fixture
def entorno(tmp_path):
    db = tmp_path / "mira.db"
    init_database(db_path=db, quiet=True)
    secret = secrets.token_urlsafe(48)
    confirmation_secret = secrets.token_urlsafe(48)
    env = {**os.environ, "SQLITE_DB_PATH": str(db),
           "MIRA_MCP_DELEGATION_SECRET": secret, "JWT_SECRET": confirmation_secret}
    return db, secret, confirmation_secret, env


def credencial(secret, user="U-I1", **changes):
    now = int(time.time())
    payload = dict(sub=user, iss="mira-api", aud="mira-cu3-mcp", iat=now,
                   exp=now + 120, jti=secrets.token_hex(8), token_type="mcp_delegation")
    payload.update(changes)
    return jwt.encode(payload, secret, algorithm="HS256", headers={"typ": TOKEN_TYPE})


def cliente(env):
    return Client(StdioTransport(sys.executable, ["-m", "backend.mcp.server"],
                                cwd=str(Path(__file__).resolve().parents[2]), env=env))


@pytest.mark.asyncio
async def test_regresiones_identidad_stdio(entorno):
    _, secret, _, env = entorno
    async with cliente(env) as client:
        async def call(org="ORG-05", token=None, **arguments):
            return await client.call_tool("checklist_organizacion", {"org_id": org, **arguments},
                                          meta={"mira_delegation": token} if token else None,
                                          raise_on_error=False)
        assert (await call()).is_error
        assert (await call("ORG-06", usuario_id="U-I3")).is_error
        valid = credencial(secret)
        assert not (await call(token=valid)).is_error
        assert (await call("ORG-06", token=valid)).is_error
        assert (await call(token=valid, usuario_id="U-I3")).is_error
        assert (await call(token=credencial(secrets.token_urlsafe(48)))).is_error
        assert (await call(token=credencial(secret, iat=int(time.time())-180, exp=int(time.time())-60))).is_error
        for changes in ({"iss": "otro"}, {"aud": "otra"}, {"token_type": "confirmacion"}, {"sub": "inexistente"},
                        {"jti": ""}, {"exp": None}, {"iat": int(time.time())+30}):
            assert (await call(token=credencial(secret, **changes))).is_error
        payload = jwt.decode(valid, options={"verify_signature": False})
        for claim in payload:
            incomplete = {k: v for k, v in payload.items() if k != claim}
            token = jwt.encode(incomplete, secret, algorithm="HS256", headers={"typ": TOKEN_TYPE})
            assert (await call(token=token)).is_error
        for algorithm, key, header in (("none", "", TOKEN_TYPE),
                                       ("HS384", secret, TOKEN_TYPE),
                                       ("HS256", secret, "JWT")):
            token = jwt.encode(payload, key, algorithm=algorithm, headers={"typ": header})
            assert (await call(token=token)).is_error
        other = credencial(secret, "U-I2")
        results = await asyncio.gather(call(token=valid), call("ORG-06", token=other),
                                       call("ORG-06", token=valid), call(token=other))
        assert [r.is_error for r in results] == [False, False, True, True]
        assert (await call()).is_error
        assert not (await call("ORG-06", token=other)).is_error
        assert (await call("ORG-06", token=valid)).is_error
        for tool in ("consultar_integracion", "consultar_formularios"):
            assert (await client.call_tool(tool, {"org_id": "ORG-06", "usuario_id": "U-I3"},
                                           raise_on_error=False)).is_error
        tools = await client.list_tools()
        assert all("mira_delegation" not in str(tool.input_schema) for tool in tools)


@pytest.mark.asyncio
async def test_mutacion_exige_delegacion_y_conserva_anti_replay(entorno):
    db, secret, confirmation_secret, env = entorno
    token = jwt.encode(dict(tarea_id="T-006", org_id="ORG-05", usuario_id="U-I1",
                            estado_anterior="en_curso", nuevo_estado="completada",
                            exp=int(time.time())+120), confirmation_secret, algorithm="HS256")
    args = dict(tarea_id="T-006", nuevo_estado="completada", token_confirmacion=token)
    async with cliente(env) as client:
        assert (await client.call_tool("marcar_tarea", args, raise_on_error=False)).is_error
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0] == 0
        meta = {"mira_delegation": credencial(secret)}
        assert not (await client.call_tool("marcar_tarea", args, meta=meta, raise_on_error=False)).is_error
        assert (await client.call_tool("marcar_tarea", args, meta=meta, raise_on_error=False)).is_error
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("configuracion", ["ausente", "debil", "compartida"])
async def test_secreto_delegacion_inseguro_rechazado(entorno, configuracion):
    _, secret, confirmation_secret, env = entorno
    if configuracion == "ausente":
        env.pop("MIRA_MCP_DELEGATION_SECRET")
    elif configuracion == "debil":
        env["MIRA_MCP_DELEGATION_SECRET"] = "corto"
    else:
        env["MIRA_MCP_DELEGATION_SECRET"] = confirmation_secret
    async with cliente(env) as client:
        result = await client.call_tool("checklist_organizacion", {"org_id": "ORG-05"},
                                       meta={"mira_delegation": credencial(secret)},
                                       raise_on_error=False)
        assert result.is_error


@pytest.mark.asyncio
async def test_delegacion_stdio_rechaza_clave_historica_con_confirmacion_independiente(entorno):
    from backend.mcp.tools.mutation_tools import DEFAULT_JWT_SECRET

    _, _, confirmation_secret, env = entorno
    assert confirmation_secret != DEFAULT_JWT_SECRET
    assert len(confirmation_secret.encode("utf-8")) >= 32
    env["MIRA_MCP_DELEGATION_SECRET"] = DEFAULT_JWT_SECRET
    async with cliente(env) as client:
        result = await client.call_tool(
            "checklist_organizacion", {"org_id": "ORG-05"},
            meta={"mira_delegation": credencial(DEFAULT_JWT_SECRET)},
            raise_on_error=False,
        )
        assert result.is_error
        assert result.structured_content is None
        assert any("Configuración de delegación MCP inválida." in block.text
                   for block in result.content if hasattr(block, "text"))


@pytest.mark.asyncio
async def test_contexto_directo_no_autentica_servidor_y_se_restaura():
    from backend.mcp.access_control import set_current_user_id, get_current_user_id
    from backend.mcp.server import mcp

    set_current_user_id("U-I3")
    try:
        async with Client(mcp) as client:
            result = await client.call_tool("checklist_organizacion", {"org_id": "ORG-06"},
                                           raise_on_error=False)
            assert result.is_error
        assert get_current_user_id() == "U-I3"
    finally:
        set_current_user_id(None)


@pytest.mark.asyncio
async def test_mutacion_stdio_no_acepta_clave_confirmacion_predeterminada(entorno):
    from backend.mcp.tools.mutation_tools import DEFAULT_JWT_SECRET

    db, secret, _, env = entorno
    env.pop("JWT_SECRET")
    token = jwt.encode(dict(tarea_id="T-006", org_id="ORG-05", usuario_id="U-I1",
                            estado_anterior="en_curso", nuevo_estado="completada",
                            exp=int(time.time())+120), DEFAULT_JWT_SECRET, algorithm="HS256")
    async with cliente(env) as client:
        result = await client.call_tool(
            "marcar_tarea", dict(tarea_id="T-006", nuevo_estado="completada", token_confirmacion=token),
            meta={"mira_delegation": credencial(secret)}, raise_on_error=False)
        assert result.is_error
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tarea_eventos_cambio").fetchone()[0] == 0
