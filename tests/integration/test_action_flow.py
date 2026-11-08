"""Pruebas de integración del flujo de mutaciones en dos pasos (T035, T037, T038, US4).

Verifica el ciclo completo de preparación y confirmación humana interactiva:
1. Preparación estructurada de cambio de estado (POST /api/action/prepare)
2. Inmutabilidad de la base de datos durante la preparación
3. Confirmación humana interactiva (POST /api/action/confirm) con token efímero HMAC-SHA256
4. Validación estricta de permisos por rol, organización y etapa E5 (PR-7)
5. Control anti-replay y detección de conflictos de concurrencia optimista (PR-6)
6. Exclusión de marcar_tarea del catálogo de herramientas expuesto al LLM (PR-1)
7. Sanitización y no divulgación de secretos o tokens en trazas y errores
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
import jwt
import pytest

from backend.app.config import get_settings
from backend.app.main import app
from backend.app.routers.actions import get_mcp_client
from backend.app.security import (
    compute_token_hash,
    create_confirmation_token,
    create_session_token,
)
from backend.mcp.client import (
    MiraMcpClient,
    McpConnectionError,
    McpExecutionError,
    McpSecurityError,
    McpTimeoutError,
)


@pytest.fixture
def mock_mcp_actions_server():
    """Servidor FastMCP en memoria que simula checklist_organizacion y marcar_tarea."""
    server = FastMCP("mock_actions_mcp_server")

    # Almacén de tareas en memoria para simular el estado de SQLite
    tasks_db = {
        "ORG-05": [
            {
                "tarea_id": "T-006",
                "org_id": "ORG-05",
                "etapa": "E3",
                "descripcion": "Configurar intercambio de archivos con el sistema central",
                "obligatoria": "sí",
                "estado": "en_curso",
                "responsable": "U-I1",
            },
            {
                "tarea_id": "T-010",
                "org_id": "ORG-05",
                "etapa": "E5",
                "descripcion": "Autorización formal de salida a producción",
                "obligatoria": "sí",
                "estado": "pendiente",
                "responsable": "U-I3",
            },
        ],
        "ORG-06": [
            {
                "tarea_id": "T-015",
                "org_id": "ORG-06",
                "etapa": "E2",
                "descripcion": "Revisión de campos personalizados de admisión",
                "obligatoria": "no",
                "estado": "pendiente",
                "responsable": "U-I2",
            }
        ],
        "ORG-07": [
            {
                "tarea_id": "T-023",
                "org_id": "ORG-07",
                "etapa": "E4",
                "descripcion": "Aprobación de umbrales por segundo supervisor",
                "obligatoria": "sí",
                "estado": "pendiente",
                "responsable": "U-I1",
            }
        ],
    }

    # Registro de auditoría y control anti-replay
    used_token_hashes = set()
    events_log = []
    concurrency_conflict_trigger = {"active": False}
    checklist_calls = []

    @server.tool(description="Consulta tareas de la organización")
    def checklist_organizacion(org_id: str, etapa: str | None = None) -> dict:
        checklist_calls.append(org_id)
        tareas = tasks_db.get(org_id, [])
        if etapa:
            tareas = [t for t in tareas if t.get("etapa") == etapa]
        return {
            "org_id": org_id,
            "tareas": tareas,
            "total_tareas": len(tareas),
        }

    @server.tool(description="Herramienta protegida de mutación para marcar tarea")
    def marcar_tarea(
        tarea_id: str,
        nuevo_estado: str,
        token_confirmacion: str,
        justificacion: str | None = None,
    ) -> dict:
        token_hash = compute_token_hash(token_confirmacion)

        # 1. Control Anti-Replay en transacción SQLite
        if token_hash in used_token_hashes:
            raise ToolError(
                "token_hash ya registrado en tarea_eventos_cambio (control anti-replay PR-6)"
            )

        # 2. Control de Concurrencia Optimista
        if concurrency_conflict_trigger["active"]:
            raise ToolError(
                "Conflicto de concurrencia optimista: el estado efectivo ha cambiado"
            )

        # Buscar la tarea en tasks_db
        target_task = None
        target_org = None
        for org, t_list in tasks_db.items():
            for t in t_list:
                if t["tarea_id"] == tarea_id:
                    target_task = t
                    target_org = org
                    break
            if target_task:
                break

        if not target_task:
            raise ToolError(f"Tarea '{tarea_id}' no encontrada en la base de datos.")

        # Registrar mutación atómica
        used_token_hashes.add(token_hash)
        target_task["estado"] = nuevo_estado
        evento_id = len(events_log) + 1
        now_iso = datetime.now(timezone.utc).isoformat()

        event_record = {
            "evento_id": evento_id,
            "tarea_id": tarea_id,
            "org_id": target_org,
            "nuevo_estado": nuevo_estado,
            "justificacion": justificacion,
            "fecha_cambio": now_iso,
        }
        events_log.append(event_record)

        return {
            "success": True,
            "evento_id": evento_id,
            "tarea_id": tarea_id,
            "org_id": target_org,
            "nuevo_estado": nuevo_estado,
            "justificacion": justificacion,
            "fecha_cambio": now_iso,
        }

    # Adjuntar estado interno para inspección en pruebas
    server.test_state = {
        "tasks_db": tasks_db,
        "used_token_hashes": used_token_hashes,
        "events_log": events_log,
        "concurrency_conflict_trigger": concurrency_conflict_trigger,
        "checklist_calls": checklist_calls,
    }

    return server


@pytest.fixture
def client_with_actions_mcp(mock_mcp_actions_server):
    """Cliente HTTP con cliente FastMCP inyectado sobre el servidor de mutaciones."""
    mcp_client = MiraMcpClient(transport=mock_mcp_actions_server)
    app.dependency_overrides[get_mcp_client] = lambda: mcp_client
    client = TestClient(app)
    client.mcp_client = mcp_client
    client.server_state = mock_mcp_actions_server.test_state
    yield client
    app.dependency_overrides.clear()


class TestActionFlowIntegration:
    """Suite de integración para el flujo de dos pasos de mutación (US4, T037, T038)."""

    def test_complete_two_step_mutation_lifecycle_t006(self, client_with_actions_mcp):
        """1. Preparación correcta de T-006 para U-I1 y 3. Confirmación exitosa."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        # Paso 1: Preparación (/api/action/prepare)
        prep_payload = {
            "tarea_id": "T-006",
            "nuevo_estado": "completada",
            "justificacion": "Se habilitó carpeta SFTP compartida y se verificó recepción de archivos.",
        }

        prep_res = client_with_actions_mcp.post("/api/action/prepare", json=prep_payload, headers=headers)
        assert prep_res.status_code == 200

        data = prep_res.json()
        proposal = data["proposal"]
        assert proposal["action_type"] == "CAMBIO_ESTADO_TAREA"
        assert proposal["tarea_id"] == "T-006"
        assert proposal["org_id"] == "ORG-05"
        assert proposal["estado_actual"] == "en_curso"
        assert proposal["estado_propuesto"] == "completada"
        assert "SFTP" in proposal["justificacion"]
        assert "confirmation_token" in proposal

        # 2. Verificar que preparar no altera SQLite ni registra eventos
        assert len(client_with_actions_mcp.server_state["events_log"]) == 0
        task_in_db = client_with_actions_mcp.server_state["tasks_db"]["ORG-05"][0]
        assert task_in_db["estado"] == "en_curso"

        # Paso 2: Confirmación (/api/action/confirm)
        confirm_token = proposal["confirmation_token"]
        conf_payload = {"confirmation_token": confirm_token}

        conf_res = client_with_actions_mcp.post("/api/action/confirm", json=conf_payload, headers=headers)
        assert conf_res.status_code == 200

        conf_data = conf_res.json()
        assert conf_data["success"] is True
        assert conf_data["evento_id"] == 1
        assert conf_data["tarea_id"] == "T-006"
        assert conf_data["org_id"] == "ORG-05"
        assert conf_data["nuevo_estado"] == "completada"
        assert conf_data["usuario_id"] == "U-I1"
        assert "SFTP" in conf_data["justificacion"]

        # Verificar persistencia del evento
        assert len(client_with_actions_mcp.server_state["events_log"]) == 1
        assert task_in_db["estado"] == "completada"

    def test_unauthenticated_request_rejected_401(self, client_with_actions_mcp):
        """4. Solicitud sin autenticación: rechazo con HTTP 401."""
        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Test"},
        )
        assert prep_res.status_code == 401
        assert prep_res.json()["code"] == "MISSING_SESSION_TOKEN"

        conf_res = client_with_actions_mcp.post(
            "/api/action/confirm",
            json={"confirmation_token": "some.token.value"},
        )
        assert conf_res.status_code == 401
        assert conf_res.json()["code"] == "MISSING_SESSION_TOKEN"

    def test_commercial_user_u_i4_forbidden_403(self, client_with_actions_mcp):
        """5. Usuario comercial U-I4 intentando modificar tareas: rechazo HTTP 403."""
        token_u4, _, _ = create_session_token("U-I4")
        headers = {"Authorization": f"Bearer {token_u4}"}

        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Intento comercial"},
            headers=headers,
        )
        assert prep_res.status_code == 403
        assert prep_res.json()["code"] == "FORBIDDEN_ACTION"
        assert "comercial" in prep_res.json()["message"]

    def test_unassigned_task_search_without_org_id_does_not_query_other_orgs_and_returns_404(
        self, client_with_actions_mcp
    ):
        """1. U-I1 buscando una tarea fuera de sus organizaciones sin org_id:
        El backend NO consulta organizaciones ajenas (como ORG-06) y responde 404 genérico.
        """
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        # Limpiar registro de llamadas previas
        client_with_actions_mcp.server_state["checklist_calls"].clear()

        # T-015 existe en ORG-06, pero U-I1 solo tiene asignadas ORG-05 y ORG-07
        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-015", "nuevo_estado": "completada", "justificacion": "Búsqueda sin org_id"},
            headers=headers,
        )
        assert prep_res.status_code == 404
        assert prep_res.json()["code"] == "TASK_NOT_FOUND"
        assert "ORG-06" not in prep_res.json()["message"]
        assert "organizaciones autorizadas" in prep_res.json()["message"]

        # Verificar que el cliente MCP NUNCA fue llamado para ORG-06 ni ninguna otra fuera de las asignadas
        called_orgs = client_with_actions_mcp.server_state["checklist_calls"]
        assert "ORG-06" not in called_orgs
        assert set(called_orgs).issubset({"ORG-05", "ORG-07"})

    def test_unassigned_organization_explicit_rejected_403(self, client_with_actions_mcp):
        """2. Organización no asignada indicada explícitamente en el cuerpo: rechazo HTTP 403."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        client_with_actions_mcp.server_state["checklist_calls"].clear()

        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={
                "tarea_id": "T-015",
                "org_id": "ORG-06",
                "nuevo_estado": "completada",
                "justificacion": "Intento explícito sobre org ajena",
            },
            headers=headers,
        )
        assert prep_res.status_code == 403
        assert prep_res.json()["code"] == "FORBIDDEN_ORGANIZATION_ACCESS"
        assert "ORG-06" in prep_res.json()["message"]
        # Se deniega en servidor antes de consultar MCP
        assert "ORG-06" not in client_with_actions_mcp.server_state["checklist_calls"]

    def test_executive_cannot_modify_stage_e5_task_403(self, client_with_actions_mcp):
        """7. Ejecutivo (U-I1) intenta modificar tarea E5 (T-010): rechazo HTTP 403; Jefa (U-I3) puede."""
        token_u1, _, _ = create_session_token("U-I1")
        headers_u1 = {"Authorization": f"Bearer {token_u1}"}

        # U-I1 (ejecutivo) rechazado
        prep_u1 = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-010", "nuevo_estado": "completada", "justificacion": "Paso a producción"},
            headers=headers_u1,
        )
        assert prep_u1.status_code == 403
        assert prep_u1.json()["code"] == "FORBIDDEN_TASK_MUTATION"
        assert "jefatura" in prep_u1.json()["message"].lower()

        # U-I3 (jefe_implementacion) autorizado
        token_u3, _, _ = create_session_token("U-I3")
        headers_u3 = {"Authorization": f"Bearer {token_u3}"}
        prep_u3 = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-010", "nuevo_estado": "completada", "justificacion": "Paso a producción aprobado"},
            headers=headers_u3,
        )
        assert prep_u3.status_code == 200
        assert prep_u3.json()["proposal"]["tarea_id"] == "T-010"

    def test_tampered_token_rejected_400(self, client_with_actions_mcp):
        """8. Token falso o con firma alterada: rechazo HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Test firma"},
            headers=headers,
        )
        raw_token = prep_res.json()["proposal"]["confirmation_token"]
        tampered_token = raw_token[:-8] + "xxxxxxxx"

        conf_res = client_with_actions_mcp.post(
            "/api/action/confirm",
            json={"confirmation_token": tampered_token},
            headers=headers,
        )
        assert conf_res.status_code == 400
        assert conf_res.json()["code"] == "INVALID_TOKEN"

    def test_expired_token_rejected_400(self, client_with_actions_mcp):
        """9. Token vencido: rechazo HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        # Generar token expirado
        expired_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
            expires_delta=timedelta(seconds=-10),
        )

        conf_res = client_with_actions_mcp.post(
            "/api/action/confirm",
            json={"confirmation_token": expired_token},
            headers=headers,
        )
        assert conf_res.status_code == 400
        assert conf_res.json()["code"] == "TOKEN_EXPIRED"

    def test_confirmation_by_different_user_rejected_403(self, client_with_actions_mcp):
        """10. Confirmación realizada por usuario distinto del preparador: rechazo HTTP 403."""
        token_u1, _, _ = create_session_token("U-I1")
        headers_u1 = {"Authorization": f"Bearer {token_u1}"}

        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Preparado por U-I1"},
            headers=headers_u1,
        )
        token = prep_res.json()["proposal"]["confirmation_token"]

        # U-I3 (jefa) intenta confirmar el token preparado por U-I1
        token_u3, _, _ = create_session_token("U-I3")
        headers_u3 = {"Authorization": f"Bearer {token_u3}"}

        conf_res = client_with_actions_mcp.post(
            "/api/action/confirm",
            json={"confirmation_token": token},
            headers=headers_u3,
        )
        assert conf_res.status_code == 403
        assert conf_res.json()["code"] == "IDENTITY_MISMATCH"

    def test_inconsistent_token_claims_rejected_400(self, client_with_actions_mcp):
        """11. Token con claims incompatibles o alterados: rechazo HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}
        settings = get_settings()

        # Token con discrepancia entre sub y usuario_id
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "U-I1",
            "usuario_id": "U-I2",  # Discrepancia
            "tarea_id": "T-006",
            "org_id": "ORG-05",
            "estado_actual": "en_curso",
            "estado_anterior": "en_curso",
            "nuevo_estado": "completada",
            "jti": "some-jti-123",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "type": "action_confirmation",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        conf_res = client_with_actions_mcp.post(
            "/api/action/confirm",
            json={"confirmation_token": token},
            headers=headers,
        )
        assert conf_res.status_code == 400
        assert conf_res.json()["code"] == "INVALID_TOKEN"

    def test_replay_attack_rejected_400(self, client_with_actions_mcp):
        """12. Segundo uso del mismo token: rechazo anti-replay HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Anti-replay test"},
            headers=headers,
        )
        token = prep_res.json()["proposal"]["confirmation_token"]

        # Primer uso: 200 OK
        res1 = client_with_actions_mcp.post("/api/action/confirm", json={"confirmation_token": token}, headers=headers)
        assert res1.status_code == 200

        # Segundo uso con el mismo token: 400 TOKEN_ALREADY_USED
        res2 = client_with_actions_mcp.post("/api/action/confirm", json={"confirmation_token": token}, headers=headers)
        assert res2.status_code == 400
        assert res2.json()["code"] == "TOKEN_ALREADY_USED"

    def test_concurrent_modification_conflict_rejected_409(self, client_with_actions_mcp):
        """13. Cambio concurrente del estado efectivo: rechazo HTTP 409 sin registrar evento."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Concurrencia test"},
            headers=headers,
        )
        token = prep_res.json()["proposal"]["confirmation_token"]

        # Simular que el estado cambió concurrentemente en SQLite antes de confirmar
        client_with_actions_mcp.server_state["concurrency_conflict_trigger"]["active"] = True

        conf_res = client_with_actions_mcp.post(
            "/api/action/confirm",
            json={"confirmation_token": token},
            headers=headers,
        )
        assert conf_res.status_code == 409
        assert conf_res.json()["code"] == "CONCURRENCY_CONFLICT"

    def test_mcp_connection_error_handled_503(self):
        """14. Error de conexión MCP: respuesta HTTP 503 sin afirmar éxito ficticio."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        # Mock de cliente MCP desconectado que falla al conectar
        mock_broken_client = MagicMock()
        mock_broken_client.call_tool = AsyncMock(side_effect=McpConnectionError("Script mcp no existe"))
        mock_broken_client.execute_confirmed_mutation = AsyncMock(side_effect=McpConnectionError("Fallo de conexión stdio"))

        app.dependency_overrides[get_mcp_client] = lambda: mock_broken_client
        try:
            client = TestClient(app)
            # En prepare
            res_prep = client.post(
                "/api/action/prepare",
                json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Test"},
                headers=headers,
            )
            assert res_prep.status_code == 503
            assert res_prep.json()["code"] == "MCP_CONNECTION_ERROR"

            # En confirm
            valid_token, _, _ = create_confirmation_token(
                usuario_id="U-I1",
                tarea_id="T-006",
                org_id="ORG-05",
                estado_actual="en_curso",
                nuevo_estado="completada",
            )
            res_conf = client.post(
                "/api/action/confirm",
                json={"confirmation_token": valid_token},
                headers=headers,
            )
            assert res_conf.status_code == 503
            assert res_conf.json()["code"] == "MCP_CONNECTION_ERROR"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_marcar_tarea_strictly_excluded_from_llm(self, mock_mcp_actions_server):
        """15. Ningún intento de invocación a marcar_tarea es permitido a través de la interfaz de LLM (PR-1, PR-6)."""
        client = MiraMcpClient(transport=mock_mcp_actions_server)
        await client.connect()

        # 1. get_tools_for_llm no la lista
        llm_tools = await client.get_tools_for_llm()
        tool_names = {t.name for t in llm_tools}
        assert "marcar_tarea" not in tool_names

        # 2. call_tool_for_llm rechaza con McpSecurityError
        with pytest.raises(McpSecurityError) as exc:
            await client.call_tool_for_llm(
                "marcar_tarea",
                {"tarea_id": "T-006", "nuevo_estado": "completada", "token_confirmacion": "tok"},
            )
        assert "mutación protegida" in str(exc.value)

        await client.close()

    def test_secrets_redacted_in_traces_and_errors(self, client_with_actions_mcp):
        """16. Ausencia de secretos y tokens en respuestas de error y trazas sanitizadas."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        prep_res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Censura test"},
            headers=headers,
        )
        token = prep_res.json()["proposal"]["confirmation_token"]

        conf_res = client_with_actions_mcp.post(
            "/api/action/confirm",
            json={"confirmation_token": token},
            headers=headers,
        )
        assert conf_res.status_code == 200

        # Verificar trazas registradas en el cliente MCP
        traces = client_with_actions_mcp.mcp_client.get_traces()
        for t in traces:
            sanitized_args_str = str(t.sanitized_arguments)
            # El token JWT debe figurar redactado en las trazas
            assert token not in sanitized_args_str
            if "token_confirmacion" in t.sanitized_arguments:
                assert t.sanitized_arguments["token_confirmacion"] in ["[REDACTED_JWT]", "[REDACTED_SECRET]"]

    def test_redundant_transition_rejected_400(self, client_with_actions_mcp):
        """Transición hacia el mismo estado actual rechazada con HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        # T-006 ya está en_curso
        res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "en_curso", "justificacion": "Redundante"},
            headers=headers,
        )
        assert res.status_code == 400
        assert res.json()["code"] == "REDUNDANT_TRANSITION"

    def test_empty_justification_rejected_400(self, client_with_actions_mcp):
        """Justificación vacía rechazada con HTTP 400."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "   "},
            headers=headers,
        )
        assert res.status_code == 400
        assert res.json()["code"] == "EMPTY_JUSTIFICATION"

    def test_task_not_found_rejected_404(self, client_with_actions_mcp):
        """3. Tarea inexistente en el sistema rechazada con HTTP 404 sin filtraciones."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        res = client_with_actions_mcp.post(
            "/api/action/prepare",
            json={"tarea_id": "T-999", "nuevo_estado": "completada", "justificacion": "No existe"},
            headers=headers,
        )
        assert res.status_code == 404
        assert res.json()["code"] == "TASK_NOT_FOUND"
        assert res.json()["message"] == "La tarea T-999 no fue encontrada en las organizaciones autorizadas."

    def test_mcp_error_during_task_search_does_not_mask_as_404(self):
        """4. Error en el servidor MCP durante búsqueda: HTTP 502/503, no debe enmascararse como 404."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        # 4a: Fallo devuelto por la herramienta MCP (success=False)
        mock_client = MagicMock()
        mock_client.call_tool = AsyncMock(
            return_value=MagicMock(success=False, error="Error interno en SQLite MCP", data=None)
        )
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)
            res = client.post(
                "/api/action/prepare",
                json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Test MCP error"},
                headers=headers,
            )
            assert res.status_code == 502
            assert res.json()["code"] == "MCP_QUERY_FAILED"
            assert res.status_code != 404

            # 4b: Fallo de conexión del transporte MCP
            mock_client.call_tool = AsyncMock(side_effect=McpConnectionError("Pipe stdio cerrado inesperadamente"))
            res_conn = client.post(
                "/api/action/prepare",
                json={"tarea_id": "T-006", "nuevo_estado": "completada", "justificacion": "Test conn error"},
                headers=headers,
            )
            assert res_conn.status_code == 503
            assert res_conn.json()["code"] == "MCP_CONNECTION_ERROR"
            assert res_conn.status_code != 404
        finally:
            app.dependency_overrides.clear()

    def test_mcp_result_success_false_rejected_502(self):
        """5. mcp_result.success=False en confirmación: rechazo con HTTP 502, no genera HTTP 200."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        mock_client = MagicMock()
        mock_client.execute_confirmed_mutation = AsyncMock(
            return_value=MagicMock(success=False, error="Fallo en la persistencia del evento", data=None)
        )
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)
            res = client.post(
                "/api/action/confirm",
                json={"confirmation_token": valid_token},
                headers=headers,
            )
            assert res.status_code == 502
            assert res.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
            assert res.status_code != 200
        finally:
            app.dependency_overrides.clear()

    def test_mcp_result_empty_data_rejected_502(self):
        """6. Respuesta MCP con data={}: rechazo con HTTP 502 sin fabricar evento_id=1 ficticio."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        mock_client = MagicMock()
        mock_client.execute_confirmed_mutation = AsyncMock(
            return_value=MagicMock(success=True, data={})
        )
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)
            res = client.post(
                "/api/action/confirm",
                json={"confirmation_token": valid_token},
                headers=headers,
            )
            assert res.status_code == 502
            assert res.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
        finally:
            app.dependency_overrides.clear()

    def test_mcp_result_missing_required_audit_fields_rejected_502(self):
        """7. Respuesta MCP sin fecha_cambio o evento_id: rechazo con HTTP 502."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        mock_client = MagicMock()
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)

            # Caso 7a: Falta evento_id (o es None o <= 0)
            mock_client.execute_confirmed_mutation = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    data={
                        "success": True,
                        "tarea_id": "T-006",
                        "org_id": "ORG-05",
                        "nuevo_estado": "completada",
                        "fecha_cambio": "2026-11-08T01:00:00Z",
                    },
                )
            )
            res1 = client.post("/api/action/confirm", json={"confirmation_token": valid_token}, headers=headers)
            assert res1.status_code == 502
            assert res1.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
            assert "evento" in res1.json()["message"].lower()

            # Caso 7b: Falta fecha_cambio
            mock_client.execute_confirmed_mutation = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    data={
                        "success": True,
                        "evento_id": 99,
                        "tarea_id": "T-006",
                        "org_id": "ORG-05",
                        "nuevo_estado": "completada",
                    },
                )
            )
            res2 = client.post("/api/action/confirm", json={"confirmation_token": valid_token}, headers=headers)
            assert res2.status_code == 502
            assert res2.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
            assert "tiempo" in res2.json()["message"].lower() or "fecha" in res2.json()["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_mcp_result_mismatched_attributes_rejected_502(self):
        """8. Respuesta MCP que informa otra tarea, organización, estado o usuario: rechazo con HTTP 502."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        mock_client = MagicMock()
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)

            # 8a: Tarea distinta devuelta
            mock_client.execute_confirmed_mutation = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    data={
                        "success": True,
                        "evento_id": 1,
                        "tarea_id": "T-999",
                        "org_id": "ORG-05",
                        "nuevo_estado": "completada",
                        "fecha_cambio": "2026-11-08T01:00:00Z",
                    },
                )
            )
            res_tarea = client.post("/api/action/confirm", json={"confirmation_token": valid_token}, headers=headers)
            assert res_tarea.status_code == 502
            assert res_tarea.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
            assert "tarea" in res_tarea.json()["message"].lower()

            # 8b: Organización distinta devuelta
            mock_client.execute_confirmed_mutation = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    data={
                        "success": True,
                        "evento_id": 1,
                        "tarea_id": "T-006",
                        "org_id": "ORG-99",
                        "nuevo_estado": "completada",
                        "fecha_cambio": "2026-11-08T01:00:00Z",
                    },
                )
            )
            res_org = client.post("/api/action/confirm", json={"confirmation_token": valid_token}, headers=headers)
            assert res_org.status_code == 502
            assert res_org.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
            assert "organización" in res_org.json()["message"].lower()

            # 8c: Nuevo estado distinto devuelto
            mock_client.execute_confirmed_mutation = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    data={
                        "success": True,
                        "evento_id": 1,
                        "tarea_id": "T-006",
                        "org_id": "ORG-05",
                        "nuevo_estado": "bloqueada",
                        "fecha_cambio": "2026-11-08T01:00:00Z",
                    },
                )
            )
            res_est = client.post("/api/action/confirm", json={"confirmation_token": valid_token}, headers=headers)
            assert res_est.status_code == 502
            assert res_est.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
            assert "estado" in res_est.json()["message"].lower()

            # 8d: Usuario distinto informado en el evento
            mock_client.execute_confirmed_mutation = AsyncMock(
                return_value=MagicMock(
                    success=True,
                    data={
                        "success": True,
                        "evento_id": 1,
                        "tarea_id": "T-006",
                        "org_id": "ORG-05",
                        "nuevo_estado": "completada",
                        "usuario_id": "U-I2",
                        "fecha_cambio": "2026-11-08T01:00:00Z",
                    },
                )
            )
            res_usr = client.post("/api/action/confirm", json={"confirmation_token": valid_token}, headers=headers)
            assert res_usr.status_code == 502
            assert res_usr.json()["code"] == "MUTATION_CONFIRMATION_INVALID"
            assert "identidad" in res_usr.json()["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_mcp_error_with_internal_path_or_secret_is_sanitized(self):
        """9. Excepción MCP conteniendo ruta interna o token: respuesta HTTP sanitizada."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        valid_token, _, _ = create_confirmation_token(
            usuario_id="U-I1",
            tarea_id="T-006",
            org_id="ORG-05",
            estado_actual="en_curso",
            nuevo_estado="completada",
        )

        mock_client = MagicMock()
        mock_client.execute_confirmed_mutation = AsyncMock(
            side_effect=McpExecutionError(
                f"Error en /var/run/secrets/internal/db.sqlite: fallo de token {valid_token}"
            )
        )
        app.dependency_overrides[get_mcp_client] = lambda: mock_client
        try:
            client = TestClient(app)
            res = client.post("/api/action/confirm", json={"confirmation_token": valid_token}, headers=headers)
            assert res.status_code == 400
            assert res.json()["code"] == "MUTATION_EXECUTION_FAILED"
            raw_body = res.text
            assert "/var/run/secrets" not in raw_body
            assert "db.sqlite" not in raw_body
            assert valid_token not in raw_body
        finally:
            app.dependency_overrides.clear()
