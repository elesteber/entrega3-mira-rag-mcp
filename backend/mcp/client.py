"""Cliente FastMCP estándar para la orquestación del backend MIRA CU-3.

Permite que FastAPI y el orquestador interactúen con el servidor FastMCP mediante
el protocolo estándar Model Context Protocol (MCP) utilizando transporte stdio.

RESPONSABILIDADES Y CONTROLES OPERATIVOS (PR-1, PR-5, PR-6, PR-7):
1. Sesión y ciclo de vida: Administra apertura, invocación y cierre seguro de conexiones.
2. Descubrimiento y filtrado:
   - Descubre dinámicamente las herramientas disponibles en el servidor MCP.
   - get_tools_for_llm() filtra taxativamente herramientas de mutación (marcar_tarea),
     asegurando que el modelo generativo (Gemini) sólo reciba herramientas de consulta (PR-1, PR-6).
3. Invocación segura y desacoplada:
   - Invocación estructurada por nombre con tipado Pydantic y timeout configurable.
   - La ejecución de escrituras protegidas (marcar_tarea) se aísla en execute_confirmed_mutation()
     y requiere obligatoriamente un token de confirmación criptográfico generado tras interacción humana.
4. Identidad confiable:
   - El cliente acepta el contexto de usuario validado por FastAPI (SimulatedUser).
   - No confía en identificadores de usuario enviados libremente por el modelo generativo (PR-7).
5. Trazas estructuradas y sanitizadas:
   - Registra auditoría de llamadas con duración, resultado y argumentos/respuestas sanitizados,
     evitando registrar secretos, tokens JWT o credenciales sensibles.

DEPENDENCIAS PENDIENTES CON EL PR DE RODRIGO (backend/mcp/server.py):
1. Propagación de identidad: El servidor de Rodrigo debe validar el contexto de sesión de la petición
   o los permisos inyectados por el backend desde SimulatedUser.
2. Control anti-replay en mutación: La herramienta marcar_tarea en el servidor de Rodrigo debe
   verificar la unicidad de token_hash en la tabla tarea_eventos_cambio dentro de BEGIN IMMEDIATE.
3. Trazabilidad RAG: La herramienta buscar_reglas (Ángel) debe retornar chunk_id y metadatos unificados.
"""

import asyncio
import copy
from datetime import datetime
import logging
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Set

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from backend.app.config import get_settings
from backend.app.security import SimulatedUser, create_mcp_delegation_token

logger = logging.getLogger("mira_cu3.mcp_client")

# Herramientas protegidas de mutación: JAMÁS expuestas al LLM (PR-1, PR-6)
PROTECTED_MUTATION_TOOLS: frozenset[str] = frozenset({"marcar_tarea"})

# Herramientas oficiales de consulta definidas en contracts/mcp-tools.json
KNOWN_QUERY_TOOLS: frozenset[str] = frozenset({
    "buscar_reglas",
    "checklist_organizacion",
    "listar_plantillas",
    "consultar_integracion",
    "consultar_formularios",
})

# Patrones para detección y censura de secretos en trazas y registros
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset({
    "token",
    "session_token",
    "token_confirmacion",
    "token_hash",
    "password",
    "secret",
    "jwt_secret",
    "api_key",
    "authorization",
    "bearer",
    "mira_delegation",
    "delegation",
    "mcp_delegation",
    "delegation_token",
    "mira_mcp_delegation_secret",
})

JWT_REGEX = re.compile(r"^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}$")


# ==============================================================================
# Excepciones Tipadas del Cliente MCP
# ==============================================================================

class McpClientError(Exception):
    """Excepción base para errores originados en el cliente MCP."""

    def __init__(self, message: str, code: str = "MCP_CLIENT_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class McpConnectionError(McpClientError):
    """Falla de conexión, inicio de subproceso o transporte con el servidor MCP."""

    def __init__(self, message: str = "Error de conexión con el servidor MCP."):
        super().__init__(message, code="MCP_CONNECTION_ERROR")


class McpTimeoutError(McpClientError):
    """Tiempo de espera agotado durante una operación MCP."""

    def __init__(self, message: str = "Tiempo de espera agotado en la llamada MCP."):
        super().__init__(message, code="MCP_TIMEOUT_ERROR")


class McpToolNotFoundError(McpClientError):
    """La herramienta solicitada no existe o no está registrada en el servidor."""

    def __init__(self, message: str = "Herramienta MCP no encontrada."):
        super().__init__(message, code="MCP_TOOL_NOT_FOUND")


class McpExecutionError(McpClientError):
    """Error devuelto durante la ejecución interna de la herramienta en el servidor."""

    def __init__(self, message: str = "Fallo en la ejecución de la herramienta MCP."):
        super().__init__(message, code="MCP_EXECUTION_ERROR")


class McpSecurityError(McpClientError):
    """Violación de directrices de seguridad (PR-1, PR-6, PR-7) en invocación MCP."""

    def __init__(self, message: str = "Violación de control de acceso o seguridad en herramienta MCP."):
        super().__init__(message, code="MCP_SECURITY_VIOLATION")


# ==============================================================================
# Modelos de Datos del Cliente MCP
# ==============================================================================

class McpToolDefinition(BaseModel):
    """Definición normalizada de una herramienta MCP."""

    name: str = Field(description="Nombre canónico de la herramienta")
    description: Optional[str] = Field(default=None, description="Descripción funcional de la herramienta")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="Esquema JSON Schema de parámetros")
    category: str = Field(default="query", description="Categoría: 'query' o 'mutation'")
    exposed_to_llm: bool = Field(default=True, description="Indica si es segura para exposición al modelo")


class McpToolResult(BaseModel):
    """Resultado estructurado de la ejecución de una herramienta MCP."""

    tool_name: str
    success: bool
    data: Any = Field(default=None, description="Datos procesados devueltos por la herramienta")
    raw_content: List[Any] = Field(default_factory=list, description="Contenido en bruto del protocolo MCP")
    error: Optional[str] = None
    duration_ms: float = 0.0


class McpTrace(BaseModel):
    """Traza de auditoría de una llamada MCP con datos sanitizados (PR-5, PR-7)."""

    tool_name: str
    duration_ms: float
    success: bool
    error: Optional[str] = None
    sanitized_arguments: Dict[str, Any] = Field(default_factory=dict)
    sanitized_output: Optional[Any] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ==============================================================================
# Función de Sanitización de Cargas Útiles y Argumentos
# ==============================================================================

def sanitize_payload(payload: Any) -> Any:
    """Censura recursivamente secretos, tokens JWT y contraseñas de estructuras de datos.

    Garantiza que ninguna traza de auditoría ni log contenga credenciales utilizables.
    """
    if isinstance(payload, dict):
        sanitized = {}
        for key, val in payload.items():
            key_lower = str(key).lower()
            if any(sens in key_lower for sens in SENSITIVE_FIELD_NAMES):
                sanitized[key] = "[REDACTED_SECRET]"
            else:
                sanitized[key] = sanitize_payload(val)
        return sanitized
    elif isinstance(payload, (list, tuple, set)):
        return [sanitize_payload(item) for item in payload]
    elif isinstance(payload, str):
        val_clean = payload.strip()
        if JWT_REGEX.match(val_clean) or (val_clean.startswith("eyJ") and val_clean.count(".") >= 2):
            return "[REDACTED_JWT]"
        return payload
    return payload


PATH_POSIX_REGEX = re.compile(r"(?:/[a-zA-Z0-9_\.\-]+){2,}")
PATH_WINDOWS_REGEX = re.compile(r"[a-zA-Z]:\\[a-zA-Z0-9_\.\-\\]+")
SECRET_MARKER_REGEX = re.compile(r"(?i)\b(?:MARCADOR_SECRETO[a-zA-Z0-9_]*|SECRET_[a-zA-Z0-9_]*|API_KEY[a-zA-Z0-9_]*)\b")
SECRET_KV_REGEX = re.compile(r"(?i)\b(token|key|secret|password|bearer|mira_delegation|delegation)[:=\s]+([^\s,;]+)")


def sanitize_mcp_error(error_text: Optional[str]) -> Optional[str]:
    """Censura secretos, rutas de archivos y tokens en mensajes de error para trazas públicas (AUD-04).

    Garantiza que ningún traceback, ruta absoluta de archivos ni credencial confidencial
    quede expuesto al frontend o en respuestas HTTP.
    """
    if not error_text:
        return None

    cleaned = str(error_text)
    # 1. Censurar JWTs
    cleaned = re.sub(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", "[REDACTED_JWT]", cleaned)
    # 2. Censurar marcadores y tokens confidenciales ficticios o reales
    cleaned = SECRET_MARKER_REGEX.sub("[REDACTED_SECRET]", cleaned)
    cleaned = SECRET_KV_REGEX.sub(r"\1=[REDACTED_SECRET]", cleaned)
    # 3. Censurar rutas de archivos del sistema operativo
    cleaned = PATH_POSIX_REGEX.sub("[REDACTED_PATH]", cleaned)
    cleaned = PATH_WINDOWS_REGEX.sub("[REDACTED_PATH]", cleaned)

    return cleaned


# ==============================================================================
# Principio de Mínimo Privilegio: Filtrado Seguro de Entorno para Subprocesos MCP
# ==============================================================================

# Variables de sistema estrictamente indispensables para que uv y Python ejecuten el subproceso
MCP_ALLOWED_SYSTEM_ENV_VARS: frozenset[str] = frozenset({
    "PATH",
    "VIRTUAL_ENV",
    "PYTHONPATH",
    "PYTHONHOME",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "USER",
    "LOGNAME",
    "LD_LIBRARY_PATH",
    # Entornos Windows
    "SYSTEMROOT",
    "COMSPEC",
    "PATHEXT",
    "WINDIR",
})

# Variables operativas de configuración y datos permitidas para el servidor FastMCP
MCP_ALLOWED_APPLICATION_ENV_VARS: frozenset[str] = frozenset({
    "MIRA_MCP_DELEGATION_SECRET",
    "JWT_SECRET",
    "SQLITE_DB_PATH",
    "DATABASE_URL",
    "CHROMADB_PATH",
    "CHROMA_PERSIST_DIRECTORY",
    "CORPUS_DIR",
    "EXCEL_DATA_PATH",
    "EMBEDDING_MODEL_NAME",
    "EMBEDDING_MAX_SEQ_LENGTH",
    "RAG_MODO_BUSQUEDA",
    "RAG_BM25_PREFIJO",
    "RAG_TOP_K",
    "RAG_SCORE_THRESHOLD",
    "LOG_LEVEL",
    "ENVIRONMENT",
})

# Variables explícitamente prohibidas para el subproceso MCP (credenciales LLM y frontend)
MCP_PROHIBITED_ENV_VARS: frozenset[str] = frozenset({
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "VITE_API_BASE_URL",
})


def build_mcp_subprocess_env(
    settings: Any,
    base_environ: Optional[Dict[str, str]] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Construye un entorno mínimo, seguro y estrictamente filtrado para PythonStdioTransport (PR-7).

    Aplica el principio de mínimo privilegio:
    1. Preserva exclusivamente las variables del sistema indispensables para iniciar Python y uv.
    2. Incorpora únicamente las variables operativas requeridas por el servidor MCP (SQLite, ChromaDB, secretos de transporte).
    3. Excluye taxativamente GEMINI_API_KEY, credenciales del frontend y tokens de servicios externos.
    4. Filtra extra_env (self._env) permitiendo únicamente overrides legítimos autorizados.
    """
    env_source = base_environ if base_environ is not None else os.environ
    filtered_env: Dict[str, str] = {}

    # 1. Variables imprescindibles del sistema para ejecutar Python en el entorno uv
    for key in MCP_ALLOWED_SYSTEM_ENV_VARS:
        if key in env_source:
            filtered_env[key] = env_source[key]

    # 2. Variables operativas autorizadas presentes en el entorno
    for key in MCP_ALLOWED_APPLICATION_ENV_VARS:
        if key in env_source:
            filtered_env[key] = env_source[key]

    # 3. Inyección controlada y tipada desde Settings
    if getattr(settings, "MIRA_MCP_DELEGATION_SECRET", None):
        filtered_env["MIRA_MCP_DELEGATION_SECRET"] = settings.MIRA_MCP_DELEGATION_SECRET
    if getattr(settings, "JWT_SECRET", None):
        filtered_env["JWT_SECRET"] = settings.JWT_SECRET
    if getattr(settings, "SQLITE_DB_PATH", None):
        filtered_env["SQLITE_DB_PATH"] = str(settings.resolved_sqlite_path)
    if getattr(settings, "CHROMADB_PATH", None):
        filtered_env["CHROMADB_PATH"] = str(settings.resolved_chroma_path)
    if getattr(settings, "CORPUS_DIR", None):
        filtered_env["CORPUS_DIR"] = settings.CORPUS_DIR
    if getattr(settings, "LOG_LEVEL", None):
        filtered_env["LOG_LEVEL"] = settings.LOG_LEVEL
    if getattr(settings, "ENVIRONMENT", None):
        filtered_env["ENVIRONMENT"] = settings.ENVIRONMENT

    # 4. Overrides legítimos pasados explícitamente en extra_env (self._env)
    if extra_env:
        for k, v in extra_env.items():
            k_clean = str(k).strip()
            k_upper = k_clean.upper()
            if (
                k_clean in MCP_ALLOWED_APPLICATION_ENV_VARS
                or k_clean in MCP_ALLOWED_SYSTEM_ENV_VARS
                or k_upper in MCP_ALLOWED_APPLICATION_ENV_VARS
            ):
                if k_upper not in MCP_PROHIBITED_ENV_VARS and not k_upper.startswith("VITE_"):
                    filtered_env[k_clean] = str(v)

    # 5. Salvaguarda final: purga absoluta de cualquier variable prohibida o credencial externa
    for prohibited in MCP_PROHIBITED_ENV_VARS:
        filtered_env.pop(prohibited, None)
    for k in list(filtered_env.keys()):
        if k.upper().startswith("VITE_") or "GEMINI" in k.upper():
            filtered_env.pop(k, None)

    return filtered_env


# ==============================================================================
# Cliente FastMCP Principal
# ==============================================================================

class MiraMcpClient:
    """Cliente asíncrono para interactuar con el servidor FastMCP de MIRA CU-3.

    Implementa el transporte stdio oficial, descubrimiento seguro de herramientas,
    exclusión estricta de escrituras para el LLM y trazabilidad estructurada.
    """

    def __init__(
        self,
        transport: Optional[Any] = None,
        script_path: Optional[str] = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ):
        """Inicializa el cliente MCP.

        Args:
            transport: Objeto de transporte FastMCP opcional (e.g., para pruebas en memoria).
            script_path: Ruta al script del servidor FastMCP (por defecto desde configuración).
            timeout: Tiempo máximo de espera en segundos para llamadas MCP.
            env: Variables de entorno adicionales para el subproceso del servidor.
            cwd: Directorio de trabajo para la ejecución del subproceso.
        """
        settings = get_settings()
        self._timeout: float = float(timeout if timeout is not None else settings.MCP_TIMEOUT_SECONDS)
        self._script_path: str = script_path or settings.MCP_SERVER_SCRIPT
        self._env: Optional[Dict[str, str]] = env
        self._cwd: Optional[str] = cwd

        # Si no se proveyó un transporte explícito, se configura PythonStdioTransport
        self._custom_transport = transport
        self._transport = transport
        self._client: Optional[Client] = None
        self._is_connected: bool = False
        self._traces: List[McpTrace] = []
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        """Indica si el cliente mantiene una sesión activa con el servidor MCP."""
        if not self._is_connected or self._client is None:
            return False
        try:
            return bool(self._client.is_connected())
        except Exception:
            return False

    async def connect(self) -> None:
        """Establece la conexión con el servidor MCP mediante el transporte configurado."""
        async with self._lock:
            if self.is_connected:
                return

            if self._custom_transport is not None:
                self._transport = self._custom_transport
            else:
                resolved = Path(self._script_path).resolve()
                if not resolved.exists():
                    raise McpConnectionError(
                        f"No se encontró el script del servidor FastMCP en '{resolved}'. "
                        "El PR de Rodrigo implementará backend/mcp/server.py."
                    )
                settings = get_settings()
                mcp_env = build_mcp_subprocess_env(settings=settings, extra_env=self._env)

                self._transport = PythonStdioTransport(
                    script_path=str(resolved),
                    env=mcp_env,
                    cwd=self._cwd,
                )

            try:
                self._client = Client(transport=self._transport, timeout=self._timeout)
                await self._client.__aenter__()
                self._is_connected = True
                logger.info("Sesión FastMCP iniciada exitosamente.")
            except Exception as e:
                self._is_connected = False
                if self._client is not None:
                    try:
                        await self._client.__aexit__(type(e), e, e.__traceback__)
                    except Exception:
                        pass
                self._client = None
                raise McpConnectionError(f"Fallo al iniciar el servidor MCP: {str(e)}") from e

    async def close(self) -> None:
        """Cierra la sesión MCP y termina el subproceso limpiamente."""
        async with self._lock:
            if self._client is not None:
                try:
                    await self._client.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error menor al cerrar cliente MCP: {str(e)}")
                finally:
                    self._client = None
                    self._is_connected = False
                    logger.info("Sesión FastMCP cerrada.")

    async def __aenter__(self) -> "MiraMcpClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # ==========================================================================
    # Descubrimiento de Herramientas
    # ==========================================================================

    async def list_tools(self) -> List[McpToolDefinition]:
        """Descubre todas las herramientas registradas en el servidor MCP."""
        if not self.is_connected:
            await self.connect()

        try:
            assert self._client is not None
            raw_tools = await asyncio.wait_for(
                self._client.list_tools(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as e:
            raise McpTimeoutError("Tiempo de espera agotado al consultar list_tools().") from e
        except Exception as e:
            raise McpConnectionError(f"Error al listar herramientas MCP: {str(e)}") from e

        definitions: List[McpToolDefinition] = []
        for tool in raw_tools:
            name = getattr(tool, "name", "")
            description = getattr(tool, "description", None)
            input_schema = getattr(tool, "input_schema", getattr(tool, "inputSchema", {}))

            is_query = (name in KNOWN_QUERY_TOOLS) and (name not in PROTECTED_MUTATION_TOOLS)
            category = "query" if is_query else "mutation"
            exposed_to_llm = is_query

            definitions.append(
                McpToolDefinition(
                    name=name,
                    description=description,
                    input_schema=input_schema if isinstance(input_schema, dict) else {},
                    category=category,
                    exposed_to_llm=exposed_to_llm,
                )
            )

        return definitions

    async def get_tools_for_llm(self) -> List[McpToolDefinition]:
        """Retorna exclusivamente las herramientas de consulta autorizadas para el LLM.

        Aplica política de mínimo privilegio y denegación por defecto (AUD-07):
        Únicamente herramientas catalogadas en KNOWN_QUERY_TOOLS y explícitamente no protegidas (PR-1, PR-6).
        """
        all_tools = await self.list_tools()
        return [
            tool for tool in all_tools
            if tool.name in KNOWN_QUERY_TOOLS and tool.name not in PROTECTED_MUTATION_TOOLS
        ]

    # ==========================================================================
    # Invocación de Herramientas
    # ==========================================================================

    async def call_tool_for_llm(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_context: Optional[SimulatedUser] = None,
    ) -> McpToolResult:
        """Invoca una herramienta en nombre del LLM con validaciones estrictas de seguridad (AUD-07).

        Raises:
            McpSecurityError: Si se intenta invocar una herramienta de mutación protegida (PR-1, PR-6).
            McpToolNotFoundError: Si la herramienta no existe en el catálogo seguro de consultas (AUD-07).
        """
        clean_name = tool_name.strip()
        if clean_name in PROTECTED_MUTATION_TOOLS:
            raise McpSecurityError(
                f"Violación de seguridad (PR-1, PR-6): La herramienta '{clean_name}' "
                "es de mutación protegida y no puede ser invocada por el modelo de lenguaje."
            )

        # Política de mínimo privilegio y denegación por defecto (AUD-07)
        if clean_name not in KNOWN_QUERY_TOOLS:
            raise McpToolNotFoundError(
                f"La herramienta '{clean_name}' no existe o no está autorizada para consultas del modelo (AUD-07)."
            )

        return await self._call_tool_internal(
            tool_name=clean_name,
            arguments=arguments,
            user_context=user_context,
            is_llm_invocation=True,
        )

    async def execute_confirmed_mutation(
        self,
        tarea_id: str,
        nuevo_estado: str,
        token_confirmacion: str,
        justificacion: Optional[str] = None,
        user_context: Optional[SimulatedUser] = None,
    ) -> McpToolResult:
        """Ejecuta la mutación protegida marcar_tarea tras confirmación humana en 2 pasos (PR-1, PR-6).

        Este método es invocado exclusivamente por el endpoint /api/action/confirm del backend,
        nunca por el flujo conversacional directo del LLM.

        Args:
            tarea_id: Código de tarea ('T-001' a 'T-037').
            nuevo_estado: Estado confirmado ('pendiente', 'en_curso', 'completada').
            token_confirmacion: JWT efímero firmado por el backend.
            justificacion: Texto explicativo de la mutación.
            user_context: Identidad verificada del operador en sesión (PR-7).

        Raises:
            McpSecurityError: Si falta el token criptográfico o el usuario carece de permisos.
        """
        clean_token = token_confirmacion.strip() if token_confirmacion else ""
        if not clean_token:
            raise McpSecurityError(
                "No se puede ejecutar la mutación marcar_tarea sin un token_confirmacion válido (PR-6)."
            )

        if user_context and user_context.rol == "comercial":
            raise McpSecurityError(
                "El rol comercial no posee facultades para mutar tareas operativas (PR-7)."
            )

        arguments: Dict[str, Any] = {
            "tarea_id": tarea_id.strip().upper(),
            "nuevo_estado": nuevo_estado.strip().lower(),
            "token_confirmacion": clean_token,
        }
        if justificacion is not None:
            arguments["justificacion"] = justificacion.strip()

        return await self._call_tool_internal(
            tool_name="marcar_tarea",
            arguments=arguments,
            user_context=user_context,
            is_llm_invocation=False,
        )

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_context: Optional[SimulatedUser] = None,
    ) -> McpToolResult:
        """Invocación directa de herramientas para uso administrativo del backend.

        Si se invoca una herramienta protegida, valida la presencia de token_confirmacion.
        """
        clean_name = tool_name.strip()
        if clean_name in PROTECTED_MUTATION_TOOLS and "token_confirmacion" not in arguments:
            raise McpSecurityError(
                f"La herramienta protegida '{clean_name}' exige el parámetro 'token_confirmacion' (PR-6)."
            )

        return await self._call_tool_internal(
            tool_name=clean_name,
            arguments=arguments,
            user_context=user_context,
            is_llm_invocation=False,
        )

    # ==========================================================================
    # Ejecución Interna y Trazabilidad
    # ==========================================================================

    async def _call_tool_internal(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_context: Optional[SimulatedUser],
        is_llm_invocation: bool,
    ) -> McpToolResult:
        """Ejecuta una herramienta en el servidor FastMCP registrando auditoría sanitizada."""
        if not self.is_connected:
            await self.connect()

        assert self._client is not None
        sanitized_args = sanitize_payload(arguments)
        start_time = time.perf_counter()

        try:
            # 1. Validación de contexto de usuario autenticado confiable (PR-7, AUD-03)
            if user_context is None or not isinstance(user_context, SimulatedUser):
                err_msg = (
                    "Delegación MCP denegada: se requiere un usuario autenticado SimulatedUser válido (PR-7, AUD-03)."
                )
                logger.warning(err_msg)
                self._record_trace(tool_name, 0.0, False, sanitized_args, None, sanitize_mcp_error(err_msg))
                raise McpSecurityError(err_msg)

            # 2. Generación segura del token de delegación de identidad por invocación (AUD-03)
            try:
                delegation_token = create_mcp_delegation_token(user_context)
            except Exception as e:
                err_msg = f"Fallo al emitir la delegación MCP para el usuario '{user_context.usuario_id}': {str(e)}"
                logger.error(err_msg)
                self._record_trace(tool_name, 0.0, False, sanitized_args, None, sanitize_mcp_error(err_msg))
                raise McpSecurityError(err_msg) from e

            # 3. Propagación de identidad confiable y validación de aislamiento (PR-7, AUD-03)
            final_args = dict(arguments)
            if "org_id" in final_args and final_args["org_id"]:
                req_org = str(final_args["org_id"]).strip().upper()
                from backend.app.security import check_user_organization_access
                if not check_user_organization_access(user_context, req_org):
                    err_msg = (
                        f"Violación de aislamiento organizacional (PR-7): El usuario {user_context.usuario_id} "
                        f"({user_context.rol}) no tiene autorización sobre la organización {req_org}."
                    )
                    logger.warning(err_msg)
                    self._record_trace(tool_name, 0.0, False, sanitized_args, None, sanitize_mcp_error(err_msg))
                    raise McpSecurityError(err_msg)

            # El backend asegura identidad validada (PR-7, AUD-03): sustituir usuario_id si aplica
            if "usuario_id" in final_args:
                final_args["usuario_id"] = user_context.usuario_id

            # 4. Invocación al cliente FastMCP con metadata de delegación fuera del payload LLM
            mcp_meta = {"mira_delegation": delegation_token}
            call_coro = self._client.call_tool(tool_name, final_args, meta=mcp_meta)
            raw_result = await asyncio.wait_for(call_coro, timeout=self._timeout)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Verificar si el resultado reportó error a nivel del protocolo MCP
            is_error = getattr(raw_result, "is_error", False)
            data = getattr(raw_result, "data", None)
            raw_content = getattr(raw_result, "content", [])

            if is_error:
                error_msg = sanitize_mcp_error(f"La herramienta '{tool_name}' reportó un fallo: {data}")
                self._record_trace(tool_name, duration_ms, False, sanitized_args, None, error_msg)
                raise McpExecutionError(error_msg)

            # Validar que la respuesta MCP corresponda a la organización solicitada (PR-7, AUD-03)
            if "org_id" in arguments and isinstance(data, dict) and "org_id" in data:
                req_org = str(arguments["org_id"]).strip().upper()
                ret_org = str(data["org_id"]).strip().upper()
                if ret_org != req_org:
                    mismatch_err = (
                        f"Discrepancia en respuesta MCP: la organización devuelta ({ret_org}) "
                        f"no coincide con la organización solicitada ({req_org}) (PR-7)."
                    )
                    logger.error(mismatch_err)
                    self._record_trace(tool_name, duration_ms, False, sanitized_args, None, sanitize_mcp_error(mismatch_err))
                    raise McpSecurityError(mismatch_err)

            sanitized_out = sanitize_payload(data)
            self._record_trace(tool_name, duration_ms, True, sanitized_args, sanitized_out, None)

            return McpToolResult(
                tool_name=tool_name,
                success=True,
                data=data,
                raw_content=raw_content if isinstance(raw_content, list) else [],
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            error_msg = f"Tiempo de espera agotado ({self._timeout}s) al ejecutar '{tool_name}'."
            self._record_trace(tool_name, duration_ms, False, sanitized_args, None, error_msg)
            raise McpTimeoutError(error_msg) from e

        except ToolError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            msg = str(e)
            if "unknown tool" in msg.lower():
                error_msg = f"Herramienta '{tool_name}' no encontrada en el servidor FastMCP."
                self._record_trace(tool_name, duration_ms, False, sanitized_args, None, error_msg)
                raise McpToolNotFoundError(error_msg) from e

            error_msg = sanitize_mcp_error(f"Fallo al ejecutar '{tool_name}': {msg}")
            self._record_trace(tool_name, duration_ms, False, sanitized_args, None, error_msg)
            raise McpExecutionError(error_msg) from e

        except (McpClientError, McpSecurityError):
            raise

        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            error_msg = sanitize_mcp_error(f"Error inesperado en comunicación MCP con '{tool_name}': {str(e)}")
            self._record_trace(tool_name, duration_ms, False, sanitized_args, None, error_msg)
            raise McpConnectionError(error_msg) from e

    def _record_trace(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        sanitized_args: Dict[str, Any],
        sanitized_output: Optional[Any],
        error: Optional[str],
    ) -> None:
        """Almacena una traza de auditoría estructurada y sanitizada (AUD-04)."""
        trace = McpTrace(
            tool_name=tool_name,
            duration_ms=duration_ms,
            success=success,
            error=sanitize_mcp_error(error),
            sanitized_arguments=sanitized_args,
            sanitized_output=sanitized_output,
        )
        self._traces.append(trace)

    def get_traces(self) -> List[McpTrace]:
        """Retorna las trazas acumuladas de llamadas a herramientas."""
        return list(self._traces)

    def clear_traces(self) -> None:
        """Limpia el histórico de trazas acumuladas en memoria."""
        self._traces.clear()
