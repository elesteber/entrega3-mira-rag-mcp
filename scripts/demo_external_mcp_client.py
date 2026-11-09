"""Cliente MCP externo estándar por protocolo stdio para demostración del paso D7 (PR-5, PR-7).

Este script demuestra la interoperabilidad del servidor FastMCP de MIRA CU-3
conectándose como un cliente MCP independiente sobre el transporte estándar stdio.

Características:
1. Transporte oficial: utiliza `fastmcp.Client` con `StdioTransport` ejecutando `python -m backend.mcp.server`.
2. Autenticación y delegación (AUD-03, PR-7): genera un token JWT HS256 firmado con `MIRA_MCP_DELEGATION_SECRET`.
3. Seguridad: la identidad del usuario no proviene de un parámetro manipulable en la llamada, sino del claim `sub` firmado en el token.
4. Solo lectura: invoca exclusivamente herramientas de consulta (`checklist_organizacion`, `listar_plantillas`, `consultar_integracion`, `consultar_formularios`).

Ejemplos de uso:
    # 1. Consulta autorizada: U-I1 consulta checklist de su organización asignada ORG-05 (Éxito / HTTP 200)
    uv run python scripts/demo_external_mcp_client.py --user U-I1 --tool checklist_organizacion --org ORG-05

    # 2. Control de acceso PR-7: U-I1 intenta consultar ORG-06 que no tiene asignada (Denegado / 403 Forbidden)
    uv run python scripts/demo_external_mcp_client.py --user U-I1 --tool checklist_organizacion --org ORG-06

    # 3. Consulta de catálogo general de plantillas
    uv run python scripts/demo_external_mcp_client.py --user U-I1 --tool listar_plantillas
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
import time
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import jwt

from backend.mcp.transport_auth import TOKEN_TYPE, METADATA_FIELD

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def generar_token_delegacion(usuario_id: str, delegation_secret: str) -> str:
    """Genera un token JWT de delegación de identidad por invocación (AUD-03, PR-7)."""
    now = int(time.time())
    payload = {
        "sub": usuario_id.strip().upper(),
        "iss": "mira-api",
        "aud": "mira-cu3-mcp",
        "iat": now,
        "exp": now + 120,
        "jti": secrets.token_hex(8),
        "token_type": "mcp_delegation",
    }
    return jwt.encode(payload, delegation_secret, algorithm="HS256", headers={"typ": TOKEN_TYPE})


async def ejecutar_cliente_externo(
    usuario_id: str,
    tool_name: str,
    tool_args: dict[str, Any],
    delegation_secret: str,
    db_path: str,
) -> dict[str, Any]:
    """Inicia el proceso del servidor FastMCP sobre stdio y ejecuta la herramienta solicitada."""
    env = {
        **os.environ,
        "PYTHONPATH": str(PROJECT_ROOT),
        "SQLITE_DB_PATH": str(db_path),
        "MIRA_MCP_DELEGATION_SECRET": delegation_secret,
        "JWT_SECRET": os.environ.get("JWT_SECRET", "jwt_secret_demo_development_32bytes_min!"),
    }

    token = generar_token_delegacion(usuario_id, delegation_secret)
    transport = StdioTransport(
        sys.executable,
        ["-m", "backend.mcp.server"],
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    t0 = time.perf_counter()
    async with Client(transport) as client:
        # Descubrimiento dinámico de herramientas registradas
        tools_list = await client.list_tools()
        tools_dict = {t.name: t.description for t in tools_list}

        if tool_name not in tools_dict:
            return {
                "status": 404,
                "error": f"Herramienta '{tool_name}' no existe en el catálogo MCP.",
                "herramientas_disponibles": sorted(tools_dict.keys()),
                "tiempo_ms": round((time.perf_counter() - t0) * 1000, 2),
            }

        # Invocación pasando el token de delegación en los metadatos de la llamada
        call_result = await client.call_tool(
            tool_name,
            tool_args,
            meta={"mira_delegation": token},
            raise_on_error=False,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        if call_result.is_error:
            # Extraer contenido del error
            error_msg = "".join(str(c.text) for c in call_result.content if hasattr(c, "text"))
            return {
                "status": 403 if "no tiene permiso" in error_msg.lower() or "denegad" in error_msg.lower() or "acceso" in error_msg.lower() else 400,
                "success": False,
                "error": error_msg,
                "principio_violado": "PR-7" if "no tiene permiso" in error_msg.lower() or "acceso" in error_msg.lower() else "PR-5",
                "tiempo_ms": elapsed_ms,
            }

        # Extraer respuesta estructurada
        data = None
        for block in call_result.content:
            if hasattr(block, "text"):
                try:
                    data = json.loads(block.text)
                except Exception:
                    data = block.text

        return {
            "status": 200,
            "success": True,
            "usuario_solicitante": usuario_id,
            "herramienta": tool_name,
            "argumentos": tool_args,
            "tiempo_ms": elapsed_ms,
            "resultado": data,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Cliente MCP externo independiente vía transporte stdio para demostración D7 (PR-5, PR-7)."
    )
    parser.add_argument("--user", default="U-I1", help="ID del usuario simulado (ej: U-I1, U-I2, U-I3, U-I4)")
    parser.add_argument("--tool", default="checklist_organizacion", help="Nombre de la herramienta de consulta MCP")
    parser.add_argument("--org", default=None, help="ID de la organización para herramientas que la requieren (ej: ORG-05, ORG-06)")
    parser.add_argument("--args", default=None, help="Argumentos adicionales en formato JSON")
    parser.add_argument("--db", default=None, help="Ruta alternativa a base SQLite")
    args = parser.parse_args()

    # Resolver secreto de delegación: usar el del entorno o generar uno seguro de 48 caracteres
    secret = os.environ.get("MIRA_MCP_DELEGATION_SECRET")
    if not secret or len(secret.encode("utf-8")) < 32:
        secret = secrets.token_urlsafe(48)

    db_path = args.db or os.environ.get("SQLITE_DB_PATH", str(PROJECT_ROOT / "backend" / "data" / "mira_cu3.db"))

    # Armar argumentos de la herramienta
    tool_args = {}
    if args.args:
        try:
            tool_args = json.loads(args.args)
        except json.JSONDecodeError as err:
            print(f"[ERROR] --args debe ser un JSON válido: {err}", file=sys.stderr)
            sys.exit(1)
    elif args.org:
        tool_args["org_id"] = args.org.strip().upper()

    print("=" * 80)
    print(f"MIRA CU-3 · Cliente MCP Externo (Transporte Stdio · Protocolo MCP)")
    print("=" * 80)
    print(f"• Usuario autenticado (sub claim): {args.user}")
    print(f"• Herramienta solicitada:        {args.tool}")
    print(f"• Argumentos:                    {json.dumps(tool_args)}")
    print(f"• Transporte:                    stdio (`python -m backend.mcp.server`)")
    print(f"• Mecanismo de delegación:       JWT HS256 en metadata['mira_delegation'] (AUD-03, PR-7)")
    print("-" * 80)

    try:
        resultado = asyncio.run(
            ejecutar_cliente_externo(
                usuario_id=args.user,
                tool_name=args.tool,
                tool_args=tool_args,
                delegation_secret=secret,
                db_path=db_path,
            )
        )
        print(f"\nRespuesta recibida (HTTP {resultado.get('status')} · {resultado.get('tiempo_ms')} ms):")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))
        if resultado.get("success"):
            print("\n[OK] Demostración D7: Consulta MCP completada exitosamente vía protocolo stdio real.")
        else:
            print(f"\n[DENEGADO / SEGURIDAD] Demostración D7: Acceso bloqueado según control de acceso ({resultado.get('principio_violado', 'PR-7')}).")
    except Exception as ex:
        print(f"\n[ERROR] Fallo al ejecutar cliente MCP externo: {ex}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
