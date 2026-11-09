"""Autenticación por invocación MCP, independiente de los argumentos de negocio."""

import os
import time

import jwt
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from backend.mcp.access_control import _current_user_id, get_user_info, McpSecurityError
from backend.mcp.tools.mutation_tools import DEFAULT_JWT_SECRET

METADATA_FIELD = "mira_delegation"
TOKEN_TYPE = "mira-mcp-delegation+jwt"


def verify_delegation(credential: object) -> str:
    """Verifica criptografía y contrato sin divulgar credenciales ni errores internos."""
    secret = os.getenv("MIRA_MCP_DELEGATION_SECRET", "")
    if (len(secret.encode("utf-8")) < 32
            or secret == DEFAULT_JWT_SECRET
            or secret == os.getenv("JWT_SECRET", DEFAULT_JWT_SECRET)):
        raise ToolError("Configuración de delegación MCP inválida.")
    try:
        if not isinstance(credential, str) or not credential:
            raise ValueError()
        payload = jwt.decode(
            credential, secret, algorithms=["HS256"],
            audience="mira-cu3-mcp", issuer="mira-api",
            options={"require": ["sub", "iss", "aud", "exp", "iat", "jti", "token_type"],
                     "strict_aud": True},
        )
        if jwt.get_unverified_header(credential).get("typ") != TOKEN_TYPE:
            raise ValueError()
        if payload["token_type"] != "mcp_delegation":
            raise ValueError()
        if any(type(payload[k]) is not int for k in ("iat", "exp")):
            raise ValueError()
        if not 0 < payload["exp"] - payload["iat"] <= 300:
            raise ValueError()
        if payload["iat"] > time.time():
            raise ValueError()
        if any(not isinstance(payload[k], str) or not payload[k].strip() for k in ("sub", "jti")):
            raise ValueError()
        get_user_info(payload["sub"])
        return payload["sub"]
    except (jwt.InvalidTokenError, ValueError, TypeError, McpSecurityError):
        raise ToolError("Delegación MCP ausente o inválida.") from None


class DelegationMiddleware(Middleware):
    """No permite que un contexto de prueba heredado autentique el transporte."""

    async def on_call_tool(self, context, call_next):
        reset_token = _current_user_id.set(None)
        try:
            # FastMCP reconstruye message.meta con la versión; la metadata original
            # del transporte permanece en request_context.meta (API 4.1.6).
            ctx = context.fastmcp_context
            request = ctx.request_context if ctx else None
            meta = request.meta if request else None
            credential = meta.get(METADATA_FIELD) if meta else None
            _current_user_id.set(verify_delegation(credential))
            if context.message.name == "marcar_tarea":
                # El valor histórico de demostración solo se conserva para pruebas
                # directas; nunca autoriza una mutación expuesta por transporte.
                confirmation_secret = os.getenv("JWT_SECRET", "")
                if (len(confirmation_secret.encode("utf-8")) < 32
                        or confirmation_secret == DEFAULT_JWT_SECRET):
                    raise ToolError("Configuración de confirmación MCP inválida.")
            return await call_next(context)
        finally:
            _current_user_id.reset(reset_token)
