"""
Cliente MCP externo e independiente para demostración del paso D7 (PR-5, PR-7).
Permite verificar la interoperabilidad del servidor FastMCP de forma desacoplada de la UI web.

Uso CLI:
    uv run python -m tests.clients.test_external_mcp_client --user U-I1 --tool checklist_organizacion --args '{"org_id": "ORG-05"}'
    uv run python -m tests.clients.test_external_mcp_client --user U-I1 --tool checklist_organizacion --args '{"org_id": "ORG-06"}'
    uv run python -m tests.clients.test_external_mcp_client --user U-I4 --tool listar_plantillas
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from backend.mcp.access_control import McpSecurityError, set_current_user_id
from backend.mcp.server import mcp


def get_available_tools() -> list[str]:
    """Retorna la lista de herramientas registradas en el servidor FastMCP."""
    tools = []
    for k in mcp._local_provider._components.keys():
        if k.startswith("tool:"):
            # Extraer nombre limpio (ej. 'tool:checklist_organizacion@' -> 'checklist_organizacion')
            tool_name = k.replace("tool:", "").replace("@", "")
            tools.append(tool_name)
    return sorted(tools)


def execute_tool_call(user_id: str | None, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Ejecuta una llamada a una herramienta registrada en FastMCP inyectando el contexto
    de identidad confiable en el servidor (PR-7).
    """
    set_current_user_id(user_id)

    component_key = f"tool:{tool_name}@"
    component = mcp._local_provider._components.get(component_key)
    if not component:
        raise ValueError(f"Herramienta '{tool_name}' no encontrada en el catálogo del servidor FastMCP.")

    # Invocación directa de la función subyacente registrada en el componente FastMCP
    fn = component.fn
    try:
        result = fn(**arguments)
        return {
            "status": 200,
            "success": True,
            "user_id": user_id,
            "tool": tool_name,
            "result": result,
        }
    except McpSecurityError as sec_err:
        return {
            "status": 403,
            "success": False,
            "user_id": user_id,
            "tool": tool_name,
            "error_code": sec_err.code,
            "message": sec_err.message,
            "principle_violated": sec_err.principle_violated,
            "details": sec_err.details,
        }
    except Exception as err:
        return {
            "status": 500,
            "success": False,
            "user_id": user_id,
            "tool": tool_name,
            "error_type": type(err).__name__,
            "message": str(err),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Cliente externo independiente para el servidor FastMCP de MIRA CU-3 (Demostración D7)."
    )
    parser.add_argument("--user", type=str, default="U-I1", help="ID de usuario autenticado (ej. U-I1, U-I2, U-I3, U-I4)")
    parser.add_argument("--tool", type=str, default=None, help="Nombre de la herramienta MCP a ejecutar")
    parser.add_argument("--args", type=str, default="{}", help="Argumentos JSON para la herramienta")
    args = parser.parse_args()

    available_tools = get_available_tools()

    if not args.tool:
        print(json.dumps({
            "message": "Servidor FastMCP MIRA CU-3 - Catálogo de herramientas disponibles",
            "available_tools": available_tools,
        }, indent=2, ensure_ascii=False))
        return

    try:
        parsed_args = json.loads(args.args)
    except json.JSONDecodeError as err:
        print(f"[ERROR] Argumentos JSON inválidos: {err}", file=sys.stderr)
        sys.exit(1)

    res = execute_tool_call(user_id=args.user, tool_name=args.tool, arguments=parsed_args)
    print(json.dumps(res, indent=2, ensure_ascii=False))

    if not res["success"]:
        sys.exit(1)


# --- Pruebas automatizadas pytest para D7 ---

import pytest
from backend.data.init_db import init_database


@pytest.fixture(autouse=True)
def base_temporal(tmp_path, monkeypatch):
    """Aísla las pruebas directas del cliente de cualquier base local persistente."""
    db = tmp_path / "cliente.db"
    init_database(db_path=db, quiet=True)
    monkeypatch.setenv("SQLITE_DB_PATH", str(db))
    yield
    set_current_user_id(None)


def test_external_client_catalog():
    tools = get_available_tools()
    assert "checklist_organizacion" in tools
    assert "listar_plantillas" in tools
    assert "consultar_integracion" in tools
    assert "consultar_formularios" in tools
    assert "marcar_tarea" in tools


def test_external_client_u_i1_queries_org05_success():
    res = execute_tool_call("U-I1", "checklist_organizacion", {"org_id": "ORG-05"})
    assert res["status"] == 200
    assert res["success"] is True
    assert res["result"]["org_id"] == "ORG-05"


def test_external_client_u_i1_queries_org06_forbidden_403():
    res = execute_tool_call("U-I1", "checklist_organizacion", {"org_id": "ORG-06"})
    assert res["status"] == 403
    assert res["success"] is False
    assert res["error_code"] == "FORBIDDEN_ORGANIZATION_ACCESS"


def test_external_client_u_i4_commercial_catalog_allowed_and_checklist_forbidden():
    # Catálogo de plantillas permitido a comercial
    res_plantillas = execute_tool_call("U-I4", "listar_plantillas", {})
    assert res_plantillas["status"] == 200
    assert res_plantillas["success"] is True

    # Checklist bloqueado a comercial
    res_checklist = execute_tool_call("U-I4", "checklist_organizacion", {"org_id": "ORG-05"})
    assert res_checklist["status"] == 403
    assert res_checklist["error_code"] == "FORBIDDEN_ROLE_ACCESS"


if __name__ == "__main__":
    main()

