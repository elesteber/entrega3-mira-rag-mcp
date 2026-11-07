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
        default="backend/rag/chroma_db",
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
        """Impide de forma explícita el arranque en producción con una clave JWT insegura o predeterminada."""
        if self.is_production:
            secret = (self.JWT_SECRET or "").strip()
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


@lru_cache
def get_settings() -> Settings:
    """Retorna la instancia única de configuración en caché."""
    return Settings()
