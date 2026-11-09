"""Módulo de configuración centralizada para MIRA CU-3.

Administra las variables de entorno, rutas de almacenamiento local y secretos
utilizando Pydantic Settings, garantizando que no se expongan credenciales reales
en el repositorio y respetando los contratos técnicos y principios PR-1 a PR-7.
"""

from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any, List, Set, Union

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("mira_cu3.config")

# Conjunto de claves secretas prohibidas en entorno productivo
KNOWN_INSECURE_JWT_SECRETS: Set[str] = {
    "",
    "mira_demo_secret_key_development_only_2026",
    "super-secret-key-change-in-production",
    "secret",
    "changeme",
    "jwt_secret",
    "password",
    "admin",
    "test",
    "testing",
    "demo",
    "default",
}


class Settings(BaseSettings):
    """Configuración del sistema MIRA CU-3."""

    # Entorno y logs
    ENVIRONMENT: str = Field(default="development", description="Entorno de ejecución: development, testing, production")
    LOG_LEVEL: str = Field(default="INFO", description="Nivel de logging")

    # Servidor FastAPI (127.0.0.1 para ejecución local de la PoC)
    BACKEND_HOST: str = Field(default="127.0.0.1", description="Host del servidor backend local")
    BACKEND_PORT: int = Field(default=8000, description="Puerto del servidor backend")
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Orígenes permitidos para CORS",
    )

    # Almacenamiento local estructurado (SQLite) y vectorial (ChromaDB)
    SQLITE_DB_PATH: str = Field(
        default="backend/data/mira_cu3.db",
        description="Ruta al archivo de base de datos SQLite hidratado desde el kit",
    )
    CHROMADB_PATH: str = Field(
        default="backend/data/chroma_db",
        description="Ruta al directorio de persistencia de ChromaDB",
    )
    CORPUS_DIR: str = Field(
        default="archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus",
        description="Directorio de los 5 documentos Markdown oficiales del CU-3",
    )
    EXCEL_DATA_PATH: str = Field(
        default="archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/datos/CU-3_datos.xlsx",
        description="Ruta al Excel del kit con los datos de prueba inmutables",
    )

    # Proveedor LLM (Google Gemini Flash API)
    # Modelo configurable; no confundir con modelos de desarrollo de Antigravity
    GEMINI_API_KEY: str = Field(default="", description="Clave de API de Google Gemini (Google AI Studio)")
    GEMINI_MODEL: str = Field(default="gemini-3.8-flash", description="Modelo Gemini Flash candidato vigente")
    GEMINI_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Tiempo de espera máximo en segundos para llamadas de generación a Gemini API (AUD-08)",
    )

    # Seguridad y Sesión de Demostración
    JWT_SECRET: str = Field(
        default="mira_demo_secret_key_development_only_2026",
        description="Clave secreta para firma HMAC de sesiones y tokens efímeros",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="Algoritmo de firma HMAC")
    SESSION_TTL_MINUTES: int = Field(default=120, description="Duración en minutos de la sesión simulada de demostración")
    CONFIRMATION_TOKEN_TTL_MINUTES: int = Field(
        default=5,
        description="Duración en minutos del token de confirmación de acción (TTL estricto de 5 min)",
    )

    # Delegación de identidad MCP por transporte (AUD-03, PR-7)
    MIRA_MCP_DELEGATION_SECRET: str = Field(
        default="",
        description="Clave secreta compartida e independiente para delegación de identidad en FastMCP (AUD-03, PR-7)",
    )

    # Servidor FastMCP y Transporte stdio
    MCP_SERVER_COMMAND: str = Field(default="python", description="Comando o intérprete para el servidor MCP")
    MCP_SERVER_SCRIPT: str = Field(
        default="backend/mcp/server.py",
        description="Ruta relativa o absoluta al servidor FastMCP",
    )
    MCP_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        description="Tiempo de espera en segundos para llamadas a herramientas MCP",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> List[str]:
        """Convierte una cadena separada por comas o JSON en una lista de orígenes."""
        if isinstance(value, str):
            val = value.strip()
            if val.startswith("[") and val.endswith("]"):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in val.split(",") if origin.strip()]
        if isinstance(value, (list, tuple)):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        return value

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        """Impide el arranque en producción con claves inseguras, débiles o duplicadas (AUD-03)."""
        secret = self.JWT_SECRET or ""
        mcp_secret = self.MIRA_MCP_DELEGATION_SECRET or ""

        if self.is_production:
            if not secret:
                raise ValueError(
                    "CONFIGURACIÓN CRÍTICA: En entorno 'production' no se permite una clave JWT_SECRET vacía."
                )
            if secret.lower() in KNOWN_INSECURE_JWT_SECRETS or "development_only" in secret.lower():
                raise ValueError(
                    "CONFIGURACIÓN CRÍTICA: En entorno 'production' está prohibido utilizar la clave "
                    "predeterminada de desarrollo o una clave conocida en JWT_SECRET."
                )
            if len(secret) < 16:
                raise ValueError(
                    "CONFIGURACIÓN CRÍTICA: En entorno 'production' JWT_SECRET debe tener al menos 16 caracteres."
                )
            # Validación estricta en producción para la clave de delegación MCP (AUD-03)
            if not mcp_secret:
                raise ValueError(
                    "CONFIGURACIÓN CRÍTICA: En entorno 'production' MIRA_MCP_DELEGATION_SECRET es obligatoria."
                )
            if len(mcp_secret.encode("utf-8")) < 32:
                raise ValueError(
                    "CONFIGURACIÓN CRÍTICA: En entorno 'production' MIRA_MCP_DELEGATION_SECRET debe tener al menos 32 bytes UTF-8."
                )
            if mcp_secret == secret:
                raise ValueError(
                    "CONFIGURACIÓN CRÍTICA: MIRA_MCP_DELEGATION_SECRET no puede ser idéntica a JWT_SECRET."
                )
            if mcp_secret.lower() in KNOWN_INSECURE_JWT_SECRETS or "development_only" in mcp_secret.lower():
                raise ValueError(
                    "CONFIGURACIÓN CRÍTICA: En entorno 'production' MIRA_MCP_DELEGATION_SECRET no puede ser una clave insegura conocida."
                )
        else:
            # En entornos no productivos: si se configura MIRA_MCP_DELEGATION_SECRET, debe ser independiente de JWT_SECRET
            if mcp_secret and secret and mcp_secret == secret:
                raise ValueError(
                    "MIRA_MCP_DELEGATION_SECRET debe ser independiente y estrictamente distinta de JWT_SECRET."
                )
        return self

    @property
    def is_production(self) -> bool:
        """Indica si el entorno actual es producción."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def resolved_sqlite_path(self) -> Path:
        """Retorna la ruta resuelta al archivo SQLite."""
        return Path(self.SQLITE_DB_PATH).resolve()

    @property
    def resolved_chroma_path(self) -> Path:
        """Retorna la ruta resuelta al directorio de ChromaDB."""
        return Path(self.CHROMADB_PATH).resolve()

    @property
    def resolved_mcp_server_path(self) -> Path:
        """Retorna la ruta resuelta al script del servidor FastMCP."""
        return Path(self.MCP_SERVER_SCRIPT).resolve()


@lru_cache
def get_settings() -> Settings:
    """Retorna la instancia única de configuración en caché."""
    return Settings()
