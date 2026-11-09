"""Pruebas unitarias para el ruteador de acciones (backend/app/routers/actions.py).

Verifica validaciones de esquema, control de transiciones, formatos y dependencias
de los endpoints POST /api/action/prepare y POST /api/action/confirm (T037, T038).
"""

from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.routers.actions import get_mcp_client
from backend.app.schemas.actions import (
    ActionConfirmRequest,
    ActionConfirmResponse,
    ActionPrepareRequest,
    ActionPrepareResponse,
)
from backend.app.security import create_confirmation_token, create_session_token
from backend.mcp.client import McpSecurityError, McpTimeoutError


class TestActionsRouterUnit:
    """Pruebas unitarias sobre las validaciones y contratos de actions.py."""

    def test_openapi_schema_contains_action_endpoints(self):
        """Verifica que el esquema OpenAPI contenga las rutas de /api/action."""
        client = TestClient(app)
        res = client.get("/openapi.json")
        assert res.status_code == 200
        paths = res.json()["paths"]
        assert "/api/action/prepare" in paths
        assert "/api/action/confirm" in paths
        assert "post" in paths["/api/action/prepare"]
        assert "post" in paths["/api/action/confirm"]

    def test_prepare_invalid_task_id_format_rejected_400(self):
        """Formato inválido de tarea_id (ej. no cumple T-XXX) genera HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        client = TestClient(app)

        res = client.post(
            "/api/action/prepare",
            json={"tarea_id": "TAREA_INVALIDA", "nuevo_estado": "completada", "justificacion": "Test"},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res.status_code == 400
        assert res.json()["code"] == "INVALID_TASK_ID"

    def test_prepare_invalid_state_value_rejected_400(self):
        """Estado solicitado no reconocido genera HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        client = TestClient(app)

        res = client.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "estado_inventado", "justificacion": "Test"},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res.status_code == 400
        assert res.json()["code"] == "INVALID_TASK_STATE"

    def test_confirm_empty_token_rejected_400(self):
        """Confirmación con token vacío genera HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        client = TestClient(app)

        res = client.post(
            "/api/action/confirm",
            json={"confirmation_token": "   "},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res.status_code == 400
        assert res.json()["code"] == "MISSING_CONFIRMATION_TOKEN"

    def test_prepare_empty_justification_rejected_400(self):
        """Preparación con justificación vacía o sólo espacios genera HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        client = TestClient(app)

        res = client.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "   "},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res.status_code == 400
        assert res.json()["code"] == "EMPTY_JUSTIFICATION"

    def test_prepare_unauthorized_org_rejected_403(self):
        """Preparación con org_id no asignada explícitamente genera HTTP 403."""
        token_u1, _, _ = create_session_token("U-I1")
        client = TestClient(app)

        res = client.post(
            "/api/action/prepare",
            json={
                "tarea_id": "T-006",
                "org_id": "ORG-06",
                "nuevo_estado": "completada",
                "justificacion": "Test org ajena",
            },
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res.status_code == 403
        assert res.json()["code"] == "FORBIDDEN_ORGANIZATION_ACCESS"

    def test_prepare_commercial_role_rejected_403(self):
        """Rol comercial U-I4 en prepare es rechazado con HTTP 403 (PR-7)."""
        token_u4, _, _ = create_session_token("U-I4")
        client = TestClient(app)

        res = client.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Test comercial"},
            headers={"Authorization": f"Bearer {token_u4}"},
        )
        assert res.status_code == 403
        assert res.json()["code"] == "FORBIDDEN_ACTION"

    def test_confirm_commercial_role_rejected_403(self):
        """Rol comercial U-I4 en confirm es rechazado con HTTP 403 (PR-7)."""
        token_u4, _, _ = create_session_token("U-I4")
        client = TestClient(app)

        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I4",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        res = client.post(
            "/api/action/confirm",
            json={"confirmation_token": valid_token},
            headers={"Authorization": f"Bearer {token_u4}"},
        )
        assert res.status_code == 403
        assert res.json()["code"] == "FORBIDDEN_ACTION"

    def test_confirm_timeout_error_returns_504(self):
        """Timeout al confirmar mutación en MCP retorna HTTP 504."""
        token_u1, _, _ = create_session_token("U-I1")
        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        mock_client = MagicMock()
        mock_client.execute_confirmed_mutation = AsyncMock(side_effect=McpTimeoutError("Timeout stdio"))
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)
            res = client.post(
                "/api/action/confirm",
                json={"confirmation_token": valid_token},
                headers={"Authorization": f"Bearer {token_u1}"},
            )
            assert res.status_code == 504
            assert res.json()["code"] == "MCP_TIMEOUT_ERROR"
        finally:
            app.dependency_overrides.clear()

    def test_confirm_security_error_returns_403(self):
        """Violación de seguridad en MCP retorna HTTP 403."""
        token_u1, _, _ = create_session_token("U-I1")
        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        mock_client = MagicMock()
        mock_client.execute_confirmed_mutation = AsyncMock(
            side_effect=McpSecurityError("Invocación no autorizada de mutación protegida")
        )
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)
            res = client.post(
                "/api/action/confirm",
                json={"confirmation_token": valid_token},
                headers={"Authorization": f"Bearer {token_u1}"},
            )
            assert res.status_code == 403
            assert res.json()["code"] == "MUTATION_SECURITY_ERROR"
        finally:
            app.dependency_overrides.clear()
