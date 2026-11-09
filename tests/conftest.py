"""Configuración global y fixtures compartidas para MIRA CU-3."""

import sys
from pathlib import Path
from typing import Generator

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEST_MCP_DELEGATION_SECRET = (
    "mira-cu3-mcp-delegation-secret-for-testing-purposes-32b"
)


@pytest.fixture
def mcp_delegation_env(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[str, None, None]:
    """Configura delegación MCP solo durante la prueba."""
    monkeypatch.setenv(
        "MIRA_MCP_DELEGATION_SECRET",
        TEST_MCP_DELEGATION_SECRET,
    )

    from backend.app.config import get_settings

    get_settings.cache_clear()
    yield TEST_MCP_DELEGATION_SECRET
    get_settings.cache_clear()
