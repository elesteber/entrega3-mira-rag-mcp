"""Pruebas unitarias para el ruteador de sesiones simuladas (/api/session).

Verifica la conformidad estricta con contracts/api-rest.yaml, la correcta
emisión y validación de tokens JWT de demostración, el aislamiento de secretos,
el manejo de errores con formato ApiError y los controles de CORS.
"""

from fastapi.testclient import TestClient
import pytest

from backend.app.main import app
from backend.app.security import verify_session_token


@pytest.fixture
def client():
    """Fixture de cliente HTTP de pruebas para la aplicación FastAPI."""
    return TestClient(app)


class TestGetSessionUsers:
    """Pruebas del endpoint GET /api/session/users."""

    def test_get_session_users_success(self, client):
        response = client.get("/api/session/users")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 4

        users_by_id = {u["usuario_id"]: u for u in data}
        expected_ids = {"U-I1", "U-I2", "U-I3", "U-I4"}
        assert set(users_by_id.keys()) == expected_ids

        # Verificación de Sofía Tapia (U-I1)
        u1 = users_by_id["U-I1"]
        assert u1["nombre"] == "Sofía Tapia"
        assert u1["rol"] == "ejecutivo_implementacion"
        assert u1["orgs_asignadas"] == ["ORG-05", "ORG-07"]

        # Verificación de Diego Fuentes (U-I2)
        u2 = users_by_id["U-I2"]
        assert u2["nombre"] == "Diego Fuentes"
        assert u2["rol"] == "ejecutivo_implementacion"
        assert u2["orgs_asignadas"] == ["ORG-06", "ORG-08"]

        # Verificación de Carolina Vera (U-I3)
        u3 = users_by_id["U-I3"]
        assert u3["nombre"] == "Carolina Vera"
        assert u3["rol"] == "jefe_implementacion"
        assert set(u3["orgs_asignadas"]) == {"ORG-05", "ORG-06", "ORG-07", "ORG-08"}

        # Verificación de Pablo Reyes (U-I4)
        u4 = users_by_id["U-I4"]
        assert u4["nombre"] == "Pablo Reyes"
        assert u4["rol"] == "comercial"
        assert u4["orgs_asignadas"] == []

        # Garantizar que no se expongan campos sensibles o secretos
        for u in data:
            assert "token" not in u
            assert "secret" not in u
            assert "password" not in u


class TestSwitchSessionUser:
    """Pruebas del endpoint POST /api/session/switch."""

    @pytest.mark.parametrize("user_id,expected_name,expected_role", [
        ("U-I1", "Sofía Tapia", "ejecutivo_implementacion"),
        ("U-I2", "Diego Fuentes", "ejecutivo_implementacion"),
        ("U-I3", "Carolina Vera", "jefe_implementacion"),
        ("U-I4", "Pablo Reyes", "comercial"),
    ])
    def test_switch_session_each_user_success(self, client, user_id, expected_name, expected_role):
        response = client.post("/api/session/switch", json={"user_id": user_id})
        assert response.status_code == 200

        data = response.json()
        assert "session_token" in data
        assert "user" in data
        assert "expires_at" in data

        # Validar usuario devuelto
        user = data["user"]
        assert user["usuario_id"] == user_id
        assert user["nombre"] == expected_name
        assert user["rol"] == expected_role

        # Validar criptográficamente el token retornado
        token = data["session_token"]
        assert isinstance(token, str)
        assert len(token) > 20

        verified_user = verify_session_token(token)
        assert verified_user.usuario_id == user_id
        assert verified_user.nombre == expected_name
        assert verified_user.rol == expected_role

    def test_switch_session_case_insensitive(self, client):
        response = client.post("/api/session/switch", json={"user_id": "u-i1"})
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["usuario_id"] == "U-I1"

    def test_switch_session_nonexistent_user_rejected(self, client):
        response = client.post("/api/session/switch", json={"user_id": "U-99"})
        assert response.status_code == 400

        data = response.json()
        assert data["code"] == "INVALID_USER_ID"
        assert "no es válido" in data["message"]
        assert data["principle_violated"] == "PR-7"

    def test_switch_session_empty_user_id_rejected(self, client):
        response = client.post("/api/session/switch", json={"user_id": "   "})
        assert response.status_code == 400

        data = response.json()
        assert data["code"] == "INVALID_USER_ID"
        assert data["principle_violated"] == "PR-7"

    def test_switch_session_missing_user_id_field_rejected(self, client):
        # Cuerpo sin el campo requerido user_id
        response = client.post("/api/session/switch", json={"another_field": "test"})
        assert response.status_code == 400

        data = response.json()
        assert data["code"] == "INVALID_REQUEST_BODY"
        assert data["principle_violated"] == "PR-7"
        assert "details" in data
        assert "errors" in data["details"]

    def test_switch_session_empty_body_rejected(self, client):
        response = client.post(
            "/api/session/switch",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

        data = response.json()
        assert data["code"] == "INVALID_REQUEST_BODY"
        assert data["principle_violated"] == "PR-7"


class TestCorsAndOpenApiSpecification:
    """Pruebas de comportamiento de CORS y correspondencia con OpenAPI."""

    def test_cors_preflight_allowed_origin(self, client):
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        response = client.options("/api/session/switch", headers=headers)
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert "POST" in response.headers.get("access-control-allow-methods", "")

    def test_cors_preflight_disallowed_origin(self, client):
        headers = {
            "Origin": "http://sitio-malicioso-no-autorizado.com",
            "Access-Control-Request-Method": "GET",
        }
        response = client.options("/api/session/users", headers=headers)
        # CORS middleware no debe reflejar el origen no autorizado
        assert response.headers.get("access-control-allow-origin") != "http://sitio-malicioso-no-autorizado.com"

    def test_openapi_schema_contains_session_paths(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()

        paths = schema.get("paths", {})
        assert "/api/session/users" in paths
        assert "get" in paths["/api/session/users"]

        assert "/api/session/switch" in paths
        assert "post" in paths["/api/session/switch"]
