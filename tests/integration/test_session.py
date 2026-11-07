"""Prueba de integración HTTP independiente para el ciclo de vida de sesiones simuladas (US5, PR-7).

Simula el flujo que ejecutará el frontend (SessionSelector.tsx):
1. Obtiene la lista de usuarios reales del kit (GET /api/session/users).
2. Conmuta la sesión al usuario ejecutivo U-I1 (POST /api/session/switch) y valida su token firmado.
3. Conmuta la sesión a jefatura U-I3 y verifica la renovación de credenciales.
4. Intenta conmutar a un usuario inexistente y verifica el rechazo HTTP 400 bajo el esquema ApiError.
"""

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.security import verify_session_token


@pytest.fixture
def client():
    return TestClient(app)


class TestSessionLifecycleIntegration:
    """Verifica el flujo integrado de selección y conmutación de identidad académica."""

    def test_complete_session_switching_lifecycle(self, client):
        # 1. Obtener usuarios disponibles para el selector
        users_resp = client.get("/api/session/users")
        assert users_resp.status_code == 200
        users = users_resp.json()
        assert len(users) == 4

        # 2. Seleccionar primer usuario: Sofía Tapia (U-I1, ejecutiva)
        switch_u1 = client.post("/api/session/switch", json={"user_id": "U-I1"})
        assert switch_u1.status_code == 200
        data_u1 = switch_u1.json()

        token_u1 = data_u1["session_token"]
        user_u1 = verify_session_token(token_u1)
        assert user_u1.usuario_id == "U-I1"
        assert user_u1.rol == "ejecutivo_implementacion"
        assert user_u1.orgs_asignadas == ["ORG-05", "ORG-07"]

        # 3. Conmutar a Carolina Vera (U-I3, jefatura)
        switch_u3 = client.post("/api/session/switch", json={"user_id": "U-I3"})
        assert switch_u3.status_code == 200
        data_u3 = switch_u3.json()

        token_u3 = data_u3["session_token"]
        assert token_u3 != token_u1  # Token renovado y específico
        user_u3 = verify_session_token(token_u3)
        assert user_u3.usuario_id == "U-I3"
        assert user_u3.rol == "jefe_implementacion"
        assert len(user_u3.orgs_asignadas) == 4

        # 4. Intentar conmutar a identidad fraudulenta
        invalid_resp = client.post("/api/session/switch", json={"user_id": "U-HACK"})
        assert invalid_resp.status_code == 400
        err = invalid_resp.json()
        assert err["code"] == "INVALID_USER_ID"
        assert err["principle_violated"] == "PR-7"

