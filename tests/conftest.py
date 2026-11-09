"""Configuración global y fixtures compartidas de pytest para MIRA CU-3.

Provee fixtures explícitas para pruebas que requieren delegación de identidad FastMCP
sin ocultar globalmente configuraciones ausentes (AUD-03, PR-7).
"""

from typing import Generator
import pytest

TEST_MCP_DELEGATION_SECRET = "mira-cu3-mcp-delegation-secret-for-testing-purposes-32b"


@pytest.fixture
def mcp_delegation_env(monkeypatch: pytest.MonkeyPatch) -> Generator[str, None, None]:
    """Fixture explícita para pruebas que requieren el secreto de delegación configurado en el entorno."""
    monkeypatch.setenv("MIRA_MCP_DELEGATION_SECRET", TEST_MCP_DELEGATION_SECRET)
    from backend.app.config import get_settings
    get_settings.cache_clear()
    yield TEST_MCP_DELEGATION_SECRET
    get_settings.cache_clear()
