"""Pruebas unitarias para el módulo de configuración centralizada (backend/app/config.py)."""

import os
from unittest.mock import patch
import pytest
from pydantic import ValidationError

from backend.app.config import Settings, get_settings


class TestSettings:
    """Verifica la carga, validación y comportamiento de la configuración."""

    @pytest.fixture(autouse=True)
    def clean_config_env(self, monkeypatch):
        """Aísla las pruebas de configuración frente a variables residuales en os.environ dejadas por otros módulos."""
        for var in [
            "SQLITE_DB_PATH",
            "JWT_SECRET",
            "MIRA_MCP_DELEGATION_SECRET",
            "ENVIRONMENT",
            "BACKEND_HOST",
            "BACKEND_PORT",
            "CORS_ORIGINS",
            "CHROMADB_PATH",
            "CORPUS_DIR",
            "EXCEL_DATA_PATH",
            "GEMINI_MODEL",
            "GEMINI_API_KEY",
            "LOG_LEVEL",
        ]:
            monkeypatch.delenv(var, raising=False)
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_default_settings_values(self):
        settings = Settings()
        assert settings.ENVIRONMENT == "development"
        assert settings.BACKEND_HOST == "127.0.0.1"
        assert settings.BACKEND_PORT == 8000
        assert settings.SQLITE_DB_PATH == "backend/data/mira_cu3.db"
        assert settings.CHROMADB_PATH == "backend/data/chroma_db"
        assert settings.CORPUS_DIR == "archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/corpus"
        assert settings.EXCEL_DATA_PATH == "archivos-base/Kit_Entrega_3_MIRA/CU-3_incorporacion_organizaciones/datos/CU-3_datos.xlsx"
        assert settings.GEMINI_MODEL == "gemini-3.8-flash"
        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.SESSION_TTL_MINUTES == 120
        assert settings.CONFIRMATION_TOKEN_TTL_MINUTES == 5
        assert settings.MCP_SERVER_COMMAND == "python"
        assert settings.MCP_SERVER_SCRIPT == "backend/mcp/server.py"
        assert settings.MCP_TIMEOUT_SECONDS == 15.0
        assert settings.is_production is False

    def test_cors_origins_parsing_from_string(self):
        settings = Settings(CORS_ORIGINS="http://localhost:3000, http://localhost:5173")
        assert isinstance(settings.CORS_ORIGINS, list)
        assert len(settings.CORS_ORIGINS) == 2
        assert "http://localhost:3000" in settings.CORS_ORIGINS
        assert "http://localhost:5173" in settings.CORS_ORIGINS

    def test_cors_origins_parsing_from_list(self):
        settings = Settings(CORS_ORIGINS=["http://localhost:5173"])
        assert settings.CORS_ORIGINS == ["http://localhost:5173"]

    def test_cors_origins_from_environment_variables_comma_separated(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": "https://mira.dprime.cl, https://panel.dprime.cl"}):
            settings = Settings()
            assert isinstance(settings.CORS_ORIGINS, list)
            assert len(settings.CORS_ORIGINS) == 2
            assert "https://mira.dprime.cl" in settings.CORS_ORIGINS
            assert "https://panel.dprime.cl" in settings.CORS_ORIGINS

    def test_cors_origins_from_environment_variables_json_format(self):
        with patch.dict(os.environ, {"CORS_ORIGINS": '["https://mira.dprime.cl", "https://api.dprime.cl"]'}):
            settings = Settings()
            assert isinstance(settings.CORS_ORIGINS, list)
            assert len(settings.CORS_ORIGINS) == 2
            assert "https://mira.dprime.cl" in settings.CORS_ORIGINS
            assert "https://api.dprime.cl" in settings.CORS_ORIGINS

    def test_backend_host_override_via_environment(self):
        with patch.dict(os.environ, {"BACKEND_HOST": "0.0.0.0"}):
            settings = Settings()
            assert settings.BACKEND_HOST == "0.0.0.0"

    def test_custom_environment_variable_override(self):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-3.5-flash", "LOG_LEVEL": "DEBUG"}):
            settings = Settings()
            assert settings.GEMINI_MODEL == "gemini-3.5-flash"
            assert settings.LOG_LEVEL == "DEBUG"

    def test_production_rejects_empty_jwt_secret(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(ENVIRONMENT="production", JWT_SECRET="")
        assert "no se permite una clave JWT_SECRET vacía" in str(exc_info.value)

    def test_production_rejects_default_development_jwt_secret(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(ENVIRONMENT="production")
        assert "está prohibido utilizar la clave predeterminada" in str(exc_info.value)

    def test_production_rejects_insecure_known_jwt_secrets(self):
        for weak in ["secret", "changeme", "admin", "password", "test", "jwt_secret"]:
            with pytest.raises(ValidationError) as exc_info:
                Settings(ENVIRONMENT="production", JWT_SECRET=weak)
            assert "está prohibido utilizar la clave predeterminada de desarrollo o una clave conocida" in str(exc_info.value)

    def test_production_rejects_short_jwt_secret(self):
        with pytest.raises(ValidationError) as exc_info:
            Settings(ENVIRONMENT="production", JWT_SECRET="short_secret_12")
        assert "al menos 16 caracteres" in str(exc_info.value)

    def test_production_accepts_strong_jwt_secret(self):
        strong_secret = "clave_de_produccion_mira_super_segura_2026_xyz"
        strong_mcp_secret = "clave_mcp_delegation_produccion_32_bytes_min_segura_2026"
        settings = Settings(
            ENVIRONMENT="production",
            JWT_SECRET=strong_secret,
            MIRA_MCP_DELEGATION_SECRET=strong_mcp_secret,
        )
        assert settings.is_production is True
        assert settings.JWT_SECRET == strong_secret
        assert settings.MIRA_MCP_DELEGATION_SECRET == strong_mcp_secret

    def test_production_rejects_missing_or_weak_mcp_delegation_secret(self):
        strong_secret = "clave_de_produccion_mira_super_segura_2026_xyz"
        # 1. Falta MIRA_MCP_DELEGATION_SECRET
        with pytest.raises(ValidationError) as exc_missing:
            Settings(ENVIRONMENT="production", JWT_SECRET=strong_secret, MIRA_MCP_DELEGATION_SECRET="")
        assert "MIRA_MCP_DELEGATION_SECRET es obligatoria" in str(exc_missing.value)

        # 2. MIRA_MCP_DELEGATION_SECRET demasiado corto
        with pytest.raises(ValidationError) as exc_short:
            Settings(
                ENVIRONMENT="production",
                JWT_SECRET=strong_secret,
                MIRA_MCP_DELEGATION_SECRET="secreto_corto_de_20_caract",
            )
        assert "al menos 32 bytes UTF-8" in str(exc_short.value)

        # 3. MIRA_MCP_DELEGATION_SECRET idéntico a JWT_SECRET
        with pytest.raises(ValidationError) as exc_same:
            Settings(
                ENVIRONMENT="production",
                JWT_SECRET=strong_secret,
                MIRA_MCP_DELEGATION_SECRET=strong_secret,
            )
        assert "no puede ser idéntica a JWT_SECRET" in str(exc_same.value)

    def test_resolved_paths(self):
        settings = Settings()
        assert str(settings.resolved_sqlite_path).endswith("mira_cu3.db")
        assert str(settings.resolved_chroma_path).endswith("chroma_db")
        assert str(settings.resolved_mcp_server_path).endswith("server.py")

    def test_get_settings_cached_singleton(self):
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
