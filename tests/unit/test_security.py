"""Pruebas unitarias para el módulo de seguridad, sesión demo y control de acceso (PR-1, PR-6, PR-7).

Verifica la correcta emisión y validación de tokens de sesión firmados con HMAC,
la emisión de tokens efímeros de confirmación de acción con hash anti-replay,
la inmutabilidad del catálogo de usuarios del kit, las validaciones estrictas
de claims y algoritmos criptográficos, el control de encabezados contradictorios
y las reglas de autorización por rol y organización.
"""

from datetime import datetime, timedelta, timezone
import uuid
import jwt
import pytest
from fastapi import HTTPException

from backend.app.config import get_settings
from backend.app.security import (
    SIMULATED_USERS,
    SimulatedUser,
    SecurityError,
    TokenExpiredError,
    InvalidTokenError,
    get_simulated_user,
    list_simulated_users,
    create_session_token,
    verify_session_token,
    create_confirmation_token,
    verify_confirmation_token,
    compute_token_hash,
    check_user_organization_access,
    check_user_task_mutation_permission,
    get_current_user_from_header,
)


class TestSimulatedUsersCatalog:
    """Verifica el catálogo de usuarios reales del kit CU-3 y su inmutabilidad."""

    def test_catalog_contains_four_real_users(self):
        users = list_simulated_users()
        assert len(users) == 4
        ids = {u.usuario_id for u in users}
        assert ids == {"U-I1", "U-I2", "U-I3", "U-I4"}

    def test_user_u_i1_sofia_tapia(self):
        user = get_simulated_user("u-i1")
        assert user is not None
        assert user.usuario_id == "U-I1"
        assert user.nombre == "Sofía Tapia"
        assert user.rol == "ejecutivo_implementacion"
        assert user.orgs_asignadas == ["ORG-05", "ORG-07"]

    def test_user_u_i2_diego_fuentes(self):
        user = get_simulated_user("U-I2")
        assert user is not None
        assert user.usuario_id == "U-I2"
        assert user.nombre == "Diego Fuentes"
        assert user.rol == "ejecutivo_implementacion"
        assert user.orgs_asignadas == ["ORG-06", "ORG-08"]

    def test_user_u_i3_carolina_vera(self):
        user = get_simulated_user("U-I3")
        assert user is not None
        assert user.usuario_id == "U-I3"
        assert user.nombre == "Carolina Vera"
        assert user.rol == "jefe_implementacion"
        assert "ORG-05" in user.orgs_asignadas
        assert "ORG-08" in user.orgs_asignadas

    def test_user_u_i4_pablo_reyes_comercial(self):
        user = get_simulated_user("U-I4")
        assert user is not None
        assert user.usuario_id == "U-I4"
        assert user.nombre == "Pablo Reyes"
        assert user.rol == "comercial"
        assert user.orgs_asignadas == []

    def test_nonexistent_user_returns_none(self):
        assert get_simulated_user("U-99") is None
        assert get_simulated_user("") is None

    def test_simulated_user_catalog_immutability(self):
        """Verifica que modificar objetos devueltos no altere el catálogo interno."""
        user1 = get_simulated_user("U-I1")
        assert user1 is not None
        user1.orgs_asignadas.append("ORG-99_INTRUSION")
        user1.rol = "rol_modificado"

        # Segunda llamada independiente debe mantenerse inalterada
        user1_fresh = get_simulated_user("U-I1")
        assert user1_fresh is not None
        assert "ORG-99_INTRUSION" not in user1_fresh.orgs_asignadas
        assert user1_fresh.rol == "ejecutivo_implementacion"

        # Modificar lista de list_simulated_users tampoco altera catálogo
        users_list = list_simulated_users()
        users_list[0].orgs_asignadas.clear()
        assert len(get_simulated_user(users_list[0].usuario_id).orgs_asignadas) > 0


class TestSessionTokens:
    """Pruebas de emisión y validación de tokens de sesión demo."""

    def test_create_and_verify_session_token_success(self):
        token, user, expires_at = create_session_token("U-I1")
        assert isinstance(token, str)
        assert len(token) > 20
        assert user.usuario_id == "U-I1"

        verified_user = verify_session_token(token)
        assert verified_user.usuario_id == "U-I1"
        assert verified_user.nombre == "Sofía Tapia"
        assert verified_user.rol == "ejecutivo_implementacion"

    def test_create_session_with_invalid_user_raises_error(self):
        with pytest.raises(InvalidTokenError):
            create_session_token("U-UNKNOWN")

    def test_expired_session_token_raises_token_expired(self):
        token, _, _ = create_session_token("U-I1", expires_delta=timedelta(seconds=-10))
        with pytest.raises(TokenExpiredError):
            verify_session_token(token)

    def test_tampered_token_raises_invalid_token(self):
        token, _, _ = create_session_token("U-I1")
        tampered = token[:-4] + "abcd"
        with pytest.raises(InvalidTokenError):
            verify_session_token(tampered)

    def test_wrong_token_type_rejected(self):
        token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )
        with pytest.raises(InvalidTokenError) as exc_info:
            verify_session_token(token)
        assert "no corresponde a una sesión" in str(exc_info.value)

    def test_session_token_wrong_algorithm_rejected(self):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "U-I1",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=10)).timestamp()),
            "type": "demo_session",
        }
        # Intentar codificar sin firma o con algoritmo no permitido (ej. 'none')
        forged = jwt.encode(payload, key="", algorithm="none")
        with pytest.raises(InvalidTokenError):
            verify_session_token(forged)

    def test_session_token_missing_claims_rejected(self):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        incomplete_payload = {
            "sub": "U-I1",
            "type": "demo_session",
            # faltan iat y exp
        }
        token = jwt.encode(incomplete_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError) as exc_info:
            verify_session_token(token)
        assert "incompleto" in str(exc_info.value)


class TestConfirmationTokens:
    """Pruebas de tokens efímeros de confirmación de acción (PR-1, PR-6)."""

    def test_create_and_verify_confirmation_token_success(self):
        token, token_hash, expires_at = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
            justificacion="Prueba de integración exitosa",
        )
        assert isinstance(token, str)
        assert len(token_hash) == 64  # SHA-256 hexdigest
        assert compute_token_hash(token) == token_hash

        payload = verify_confirmation_token(token)
        assert payload["sub"] == "U-I1"
        assert payload["tarea_id"] == "T-006"
        assert payload["org_id"] == "ORG-05"
        assert payload["estado_actual"] == "en_curso"
        assert payload["nuevo_estado"] == "completada"
        assert payload["justificacion"] == "Prueba de integración exitosa"
        assert payload["type"] == "action_confirmation"
        assert "jti" in payload
        assert "iat" in payload
        assert "exp" in payload

    def test_expired_confirmation_token_raises_error(self):
        token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
            expires_delta=timedelta(seconds=-5),
        )
        with pytest.raises(TokenExpiredError):
            verify_confirmation_token(token)

    def test_create_confirmation_token_invalid_parameters(self):
        # Usuario desconocido
        with pytest.raises(InvalidTokenError) as exc:
            create_confirmation_token("U-99", "T-001", "ORG-05", "pendiente", "en_curso")
        assert "no reconocido" in str(exc.value)

        # Formato de tarea incorrecto
        with pytest.raises(InvalidTokenError) as exc:
            create_confirmation_token("U-I1", "tarea-1", "ORG-05", "pendiente", "en_curso")
        assert "tarea_id" in str(exc.value)

        # Formato de org_id incorrecto
        with pytest.raises(InvalidTokenError) as exc:
            create_confirmation_token("U-I1", "T-001", "ORGANIZACION_5", "pendiente", "en_curso")
        assert "org_id" in str(exc.value)

        # Estado actual inválido
        with pytest.raises(InvalidTokenError) as exc:
            create_confirmation_token("U-I1", "T-001", "ORG-05", "creada", "en_curso")
        assert "estado_actual" in str(exc.value)

        # Nuevo estado inválido
        with pytest.raises(InvalidTokenError) as exc:
            create_confirmation_token("U-I1", "T-001", "ORG-05", "pendiente", "finalizada")
        assert "nuevo_estado" in str(exc.value)

        # Estados idénticos
        with pytest.raises(InvalidTokenError) as exc:
            create_confirmation_token("U-I1", "T-001", "ORG-05", "en_curso", "en_curso")
        assert "no pueden ser idénticos" in str(exc.value)

    def test_verify_confirmation_token_missing_mandatory_claims(self):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        base_payload = {
            "sub": "U-I1",
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_actual": "en_curso",
            "nuevo_estado": "completada",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "type": "action_confirmation",
        }

        # Probar la ausencia de cada claim obligatorio
        mandatory_claims = ["sub", "tarea_id", "org_id", "estado_actual", "nuevo_estado", "jti", "iat", "exp", "type"]
        for claim in mandatory_claims:
            incomplete = dict(base_payload)
            del incomplete[claim]
            token = jwt.encode(incomplete, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
            with pytest.raises(InvalidTokenError) as exc_info:
                verify_confirmation_token(token)
            assert "incompleto" in str(exc_info.value) or "obligatorios" in str(exc_info.value)

    def test_verify_confirmation_token_tampered_payload_or_signature(self):
        token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )
        tampered = token[:-6] + "xxxxxx"
        with pytest.raises(InvalidTokenError):
            verify_confirmation_token(tampered)

    def test_verify_confirmation_token_wrong_algorithm(self):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "U-I1",
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_actual": "en_curso",
            "nuevo_estado": "completada",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "type": "action_confirmation",
        }
        forged = jwt.encode(payload, key="", algorithm="none")
        with pytest.raises(InvalidTokenError):
            verify_confirmation_token(forged)

    def test_verify_confirmation_token_wrong_type(self):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "U-I1",
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_actual": "en_curso",
            "nuevo_estado": "completada",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "type": "unexpected_type",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError) as exc_info:
            verify_confirmation_token(token)
        assert "no corresponde a una propuesta" in str(exc_info.value)

    def test_verify_confirmation_token_invalid_sub_user(self):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "U-UNKNOWN",
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_actual": "en_curso",
            "nuevo_estado": "completada",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "type": "action_confirmation",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError) as exc_info:
            verify_confirmation_token(token)
        assert "no existe en el catálogo" in str(exc_info.value)

    def test_verify_confirmation_token_rodrigo_claims_compatibility(self):
        """Verifica compatibilidad con claims de Rodrigo (usuario_id y estado_anterior)."""
        settings = get_settings()
        now = datetime.now(timezone.utc)
        payload = {
            "usuario_id": "U-I1",
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_anterior": "en_curso",
            "nuevo_estado": "completada",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "type": "action_confirmation",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        verified = verify_confirmation_token(token)
        assert verified["sub"] == "U-I1"
        assert verified["usuario_id"] == "U-I1"
        assert verified["estado_actual"] == "en_curso"
        assert verified["estado_anterior"] == "en_curso"

    def test_verify_confirmation_token_inconsistent_equivalent_claims_rejected(self):
        """Verifica que discrepancias entre claims equivalentes sean rechazadas con error."""
        settings = get_settings()
        now = datetime.now(timezone.utc)
        base = {
            "sub": "U-I1",
            "usuario_id": "U-I2",  # Discrepancia con sub
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_actual": "en_curso",
            "estado_anterior": "en_curso",
            "nuevo_estado": "completada",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "type": "action_confirmation",
        }
        token1 = jwt.encode(base, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError) as exc:
            verify_confirmation_token(token1)
        assert "Inconsistencia" in str(exc.value)

        # Discrepancia en estado_actual vs estado_anterior
        base["usuario_id"] = "U-I1"
        base["estado_anterior"] = "pendiente"  # Discrepancia con en_curso
        token2 = jwt.encode(base, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(InvalidTokenError) as exc:
            verify_confirmation_token(token2)
        assert "Inconsistencia" in str(exc.value)

    def test_verify_confirmation_token_inconsistent_timestamps(self):
        settings = get_settings()
        now = datetime.now(timezone.utc)
        # exp <= iat
        payload = {
            "sub": "U-I1",
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_actual": "en_curso",
            "nuevo_estado": "completada",
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(now.timestamp()) - 10,
            "type": "action_confirmation",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
        with pytest.raises(SecurityError):
            verify_confirmation_token(token)


class TestAccessControlPermissions:
    """Pruebas de aislamiento organizacional y control de mutación (PR-7)."""

    def test_executive_organization_isolation(self):
        u1 = get_simulated_user("U-I1")  # Sofía: ORG-05, ORG-07
        u2 = get_simulated_user("U-I2")  # Diego: ORG-06, ORG-08

        # U-I1 accede a sus organizaciones
        assert check_user_organization_access(u1, "ORG-05") is True
        assert check_user_organization_access(u1, "ORG-07") is True
        # U-I1 no puede acceder a las de U-I2
        assert check_user_organization_access(u1, "ORG-06") is False
        assert check_user_organization_access(u1, "ORG-08") is False

        # U-I2 accede a sus organizaciones
        assert check_user_organization_access(u2, "ORG-06") is True
        assert check_user_organization_access(u2, "ORG-08") is True
        # U-I2 no puede acceder a las de U-I1
        assert check_user_organization_access(u2, "ORG-05") is False
        assert check_user_organization_access(u2, "ORG-07") is False

    def test_commercial_user_denied_to_all_organizations(self):
        u4 = get_simulated_user("U-I4")  # Pablo: comercial
        assert check_user_organization_access(u4, "ORG-05") is False
        assert check_user_organization_access(u4, "ORG-06") is False
        assert check_user_organization_access(u4, "ORG-07") is False
        assert check_user_organization_access(u4, "ORG-08") is False

    def test_chief_user_has_global_organization_access(self):
        u3 = get_simulated_user("U-I3")  # Carolina: jefe_implementacion
        assert check_user_organization_access(u3, "ORG-05") is True
        assert check_user_organization_access(u3, "ORG-06") is True
        assert check_user_organization_access(u3, "ORG-07") is True
        assert check_user_organization_access(u3, "ORG-08") is True

    def test_mutation_permission_rules(self):
        u1 = get_simulated_user("U-I1")
        u3 = get_simulated_user("U-I3")
        u4 = get_simulated_user("U-I4")

        # U-I1 mutando tarea de etapa ordinaria E3 en su organización: permitido
        allowed, msg = check_user_task_mutation_permission(u1, "ORG-05", "E3")
        assert allowed is True
        assert msg is None

        # U-I1 mutando tarea de otra organización: denegado
        allowed, msg = check_user_task_mutation_permission(u1, "ORG-06", "E3")
        assert allowed is False
        assert "no tiene permisos sobre la organización" in msg

        # U-I1 intentando autorizar salida a producción E5: denegado (exclusivo de jefatura)
        allowed, msg = check_user_task_mutation_permission(u1, "ORG-05", "E5")
        assert allowed is False
        assert "etapa E5" in msg
        assert "exclusiva de la jefatura" in msg

        # U-I3 (jefatura) autorizando etapa E5: permitido
        allowed, msg = check_user_task_mutation_permission(u3, "ORG-05", "E5")
        assert allowed is True
        assert msg is None

        # U-I4 (comercial) intentando mutar tarea: denegado taxativamente
        allowed, msg = check_user_task_mutation_permission(u4, "ORG-05", "E1")
        assert allowed is False
        assert "rol comercial no posee facultades" in msg


class TestFastAPIDependency:
    """Pruebas de la dependencia get_current_user_from_header y manejo de encabezados."""

    def test_missing_header_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_from_header(authorization=None, x_mira_demo_session=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "MISSING_SESSION_TOKEN"
        assert exc_info.value.detail["principle_violated"] == "PR-7"

    def test_valid_bearer_token_resolves_user(self):
        token, _, _ = create_session_token("U-I1")
        user = get_current_user_from_header(authorization=f"Bearer {token}")
        assert user.usuario_id == "U-I1"

    def test_valid_x_mira_demo_session_resolves_user(self):
        token, _, _ = create_session_token("U-I2")
        user = get_current_user_from_header(authorization=None, x_mira_demo_session=token)
        assert user.usuario_id == "U-I2"

    def test_invalid_bearer_scheme_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_from_header(authorization="Basic token_invalido_123")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "INVALID_AUTHORIZATION_SCHEME"

    def test_invalid_token_in_header_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_from_header(authorization="Bearer token_invalido_123")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "INVALID_TOKEN"

    def test_both_headers_identical_accepted(self):
        token, _, _ = create_session_token("U-I3")
        user = get_current_user_from_header(
            authorization=f"Bearer {token}",
            x_mira_demo_session=token,
        )
        assert user.usuario_id == "U-I3"

    def test_both_headers_contradictory_raises_400(self):
        token1, _, _ = create_session_token("U-I1")
        token2, _, _ = create_session_token("U-I2")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_from_header(
                authorization=f"Bearer {token1}",
                x_mira_demo_session=token2,
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "AMBIGUOUS_SESSION_HEADERS"
        assert exc_info.value.detail["principle_violated"] == "PR-7"
