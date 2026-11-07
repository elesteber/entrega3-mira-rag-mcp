"""Pruebas de integración del endpoint /api/chat para diagnóstico de salida a producción (T017, US1).

Verifica el flujo conversacional completo combinando la sesión de demostración autenticada,
la recuperación de evidencia documental y datos estructurados mediante FastMCP, la evaluación
exhaustiva de los 6 criterios de GUI-INC_v2 §3 y los controles estrictos de autorización (PR-1 a PR-7).
"""

from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastmcp import FastMCP
import pytest

from backend.app.main import app
from backend.app.orchestrator import MiraOrchestrator
from backend.app.routers.chat import get_orchestrator
from backend.app.security import create_session_token
from backend.mcp.client import MiraMcpClient


@pytest.fixture
def mock_cu3_fastmcp_server():
    """Servidor FastMCP en memoria configurado con los datos oficiales de prueba del CU-3."""
    server = FastMCP("cu3_integration_server")

    @server.tool(description="Búsqueda de fragmentos normativos en ChromaDB")
    def buscar_reglas(query: str, top_k: int = 4, filtro_vigencia: str = "vigente") -> dict:
        return {
            "total_found": 3,
            "results": [
                {
                    "chunk_id": "GUI-INC-V2-SEC3-P1",
                    "doc_code": "GUI-INC",
                    "doc_title": "Guía Integral de Incorporación de Clientes",
                    "section": "§3",
                    "version": "v2.0",
                    "status": "vigente",
                    "text": (
                        "Una organización pasa a producción solo si se cumplen todos los criterios siguientes: "
                        "1. Todas las tareas obligatorias de las etapas E0 a E4 están completadas. "
                        "2. La integración fue probada con éxito en el ambiente de integración. "
                        "3. Los umbrales de decisión fueron aprobados por dos supervisores. "
                        "4. Autorización de transferencia internacional de datos firmada si aplica. "
                        "5. Autorización de tratamiento de datos biométricos firmada si la plantilla lo requiere. "
                        "6. Todos los formularios propios en estado operativo."
                    ),
                    "similarity_score": 0.95,
                },
                {
                    "chunk_id": "REQ-INT-V1-SEC5-P1",
                    "doc_code": "REQ-INT",
                    "doc_title": "Requisitos de Integración Técnica",
                    "section": "§5",
                    "version": "v1.0",
                    "status": "vigente",
                    "text": "Límite máximo contractual de 100 llamadas por minuto durante pruebas de integración.",
                    "similarity_score": 0.91,
                },
                {
                    "chunk_id": "POL-FOR-V1-SEC2-P1",
                    "doc_code": "POL-FOR",
                    "doc_title": "Política de Formularios Propios",
                    "section": "§2",
                    "version": "v1.0",
                    "status": "vigente",
                    "text": "Se requiere la recepción de entre 20 y 30 muestras reales antes de iniciar el ajuste del modelo.",
                    "similarity_score": 0.89,
                },
            ],
        }

    @server.tool(description="Consulta tareas de la organización")
    def checklist_organizacion(org_id: str, etapa: str | None = None) -> dict:
        return {
            "org_id": org_id,
            "organizacion_nombre": "Valle Verde Salud",
            "estado_incorporacion": "en_curso",
            "resumen_progreso": {
                "total_tareas": 10,
                "completadas": 6,
                "en_curso": 1,
                "pendientes": 3,
                "porcentaje_avance": 60.0,
            },
            "tareas": [
                {
                    "tarea_id": "T-021",
                    "etapa": "E3",
                    "descripcion": "Configuración de endpoints de callback",
                    "obligatoria": "sí",
                    "estado": "completada",
                },
                {
                    "tarea_id": "T-023",
                    "etapa": "E4",
                    "descripcion": "Aprobación de umbrales por segundo supervisor",
                    "obligatoria": "sí",
                    "estado": "pendiente",
                },
                {
                    "tarea_id": "T-025",
                    "etapa": "E4",
                    "descripcion": "Firma de autorización de tratamiento de datos biométricos",
                    "obligatoria": "sí",
                    "estado": "pendiente",
                },
                {
                    "tarea_id": "T-027",
                    "etapa": "E4",
                    "descripcion": "Prueba de integración de punta a punta",
                    "obligatoria": "sí",
                    "estado": "en_curso",
                },
            ],
        }

    @server.tool(description="Consulta métricas de integración técnica")
    def consultar_integracion(org_id: str) -> dict:
        return {
            "integracion_id": "I-03",
            "org_id": org_id,
            "modo": "api_asincronica",
            "ambiente": "integracion",
            "estado": "en_prueba",
            "casos_ejemplo_enviados": 20,
            "llamadas_vuelta_exitosas": 14,
            "max_llamadas_por_minuto_observado": 240,
            "alerta_tecnica": "Supera límite normativo de 100 req/min y registra fallos de callback.",
        }

    @server.tool(description="Consulta formularios propios")
    def consultar_formularios(org_id: str) -> dict:
        return {
            "org_id": org_id,
            "formularios": [
                {
                    "formulario_id": "F-01",
                    "org_id": org_id,
                    "nombre": "Ficha de ingreso Valle Verde",
                    "ejemplos_recibidos": 12,
                    "fecha_ejemplos_completos": None,
                    "estado": "en_ajuste",
                }
            ],
        }

    @server.tool(description="Lista plantillas de incorporación")
    def listar_plantillas(plantilla_id: str | None = None) -> dict:
        return {
            "plantillas": [
                {
                    "plantilla_id": "PLA-ADM",
                    "nombre": "Admisión Clínica Integral",
                    "requiere_autorizacion_biometrica": "sí",
                }
            ]
        }

    return server


@pytest.fixture
def client_with_mock_orchestrator(mock_cu3_fastmcp_server):
    """Cliente HTTP con orquestador inyectado sobre el servidor MCP de prueba."""
    mcp_client = MiraMcpClient(transport=mock_cu3_fastmcp_server)
    orchestrator = MiraOrchestrator(mcp_client=mcp_client)

    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestProductionDiagnosisIntegration:
    """Suite de integración para el Caso de Uso US1 (T017)."""

    def test_diagnosis_org07_authorized_executive_success(self, client_with_mock_orchestrator):
        """U-I1 (Sofía Tapia) consulta el diagnóstico de ORG-07 (US1, Escenario 1)."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        payload = {
            "message": "¿Qué le falta a la organización ORG-07 para pasar a producción con la plantilla de admisión clínica?",
            "organization_context": "ORG-07",
        }

        response = client_with_mock_orchestrator.post("/api/chat", json=payload, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["evidence_status"] == "COMPLETA"

        # 1. Citas formales con chunk_id y metadatos verificables (PR-2)
        citations = data["citations"]
        assert len(citations) >= 1
        chunk_ids = {c["chunk_id"] for c in citations}
        assert "GUI-INC-V2-SEC3-P1" in chunk_ids

        # 2. Trazas MCP sanitizadas y presentes (PR-5)
        traces = data["mcp_traces"]
        assert len(traces) >= 3
        trace_tools = {t["tool_name"] for t in traces}
        assert "checklist_organizacion" in trace_tools
        assert "consultar_integracion" in trace_tools
        for t in traces:
            assert t["success"] is True
            assert t["execution_time_ms"] > 0
            assert "token" not in str(t["parameters"])

        # 3. Contenido de la respuesta detalla los 6 criterios y las brechas reales de ORG-07
        answer = data["answer"]
        assert "Diagnóstico de Salida a Producción" in answer
        assert "T-023" in answer or "umbrales" in answer.lower()
        assert "T-025" in answer or "biométrica" in answer.lower() or "biometrica" in answer.lower()
        assert "240" in answer or "100" in answer  # Tasa observada vs límite contractual
        assert "F-01" in answer or "muestras" in answer.lower()
        assert "NO puede pasar a producción" in answer

    def test_diagnosis_forbidden_unassigned_executive(self, client_with_mock_orchestrator):
        """U-I2 (Diego Fuentes, asignado a ORG-06 y ORG-08) consulta ORG-07: denegado 403 (PR-7)."""
        token_u2, _, _ = create_session_token("U-I2")
        headers = {"Authorization": f"Bearer {token_u2}"}

        payload = {
            "message": "Diagnóstico de salida a producción de ORG-07",
            "organization_context": "ORG-07",
        }

        response = client_with_mock_orchestrator.post("/api/chat", json=payload, headers=headers)
        assert response.status_code == 403

        err = response.json()
        assert err["code"] == "FORBIDDEN_ORGANIZATION_ACCESS"
        assert err["principle_violated"] == "PR-7"
        assert "ORG-07" in err["message"]

    def test_diagnosis_forbidden_commercial_role(self, client_with_mock_orchestrator):
        """U-I4 (Pablo Reyes, rol comercial) consulta ORG-07 en contexto: denegado 403 (PR-7)."""
        token_u4, _, _ = create_session_token("U-I4")
        headers = {"Authorization": f"Bearer {token_u4}"}

        payload = {
            "message": "¿Qué le falta a ORG-07 para salir a producción?",
            "organization_context": "ORG-07",
        }

        response = client_with_mock_orchestrator.post("/api/chat", json=payload, headers=headers)
        assert response.status_code == 403

        err = response.json()
        assert err["code"] == "FORBIDDEN_ORGANIZATION_ACCESS"
        assert err["principle_violated"] == "PR-7"
        assert "comercial" in err["message"]

    def test_diagnosis_forbidden_commercial_role_mention_in_message_without_context(self, client_with_mock_orchestrator):
        """U-I4 (Pablo Reyes, rol comercial) menciona ORG-07 en mensaje sin context: denegado 403 (PR-7)."""
        token_u4, _, _ = create_session_token("U-I4")
        headers = {"Authorization": f"Bearer {token_u4}"}

        payload = {
            "message": "Por favor infórmame el avance de la organización ORG-07.",
        }

        response = client_with_mock_orchestrator.post("/api/chat", json=payload, headers=headers)
        assert response.status_code == 403

        err = response.json()
        assert err["code"] == "FORBIDDEN_ORGANIZATION_ACCESS"
        assert err["principle_violated"] == "PR-7"
        assert "comercial" in err["message"]

    def test_executive_with_assigned_context_mentioning_unassigned_org_in_message_rejected_403(
        self, client_with_mock_orchestrator
    ):
        """U-I2 (asignado a ORG-06 y ORG-08) usa context=ORG-06 pero menciona ORG-07 en mensaje: denegado 403 (PR-7)."""
        token_u2, _, _ = create_session_token("U-I2")
        headers = {"Authorization": f"Bearer {token_u2}"}

        payload = {
            "message": "Quiero comparar el progreso con ORG-07 para ver si vamos bien.",
            "organization_context": "ORG-06",
        }

        response = client_with_mock_orchestrator.post("/api/chat", json=payload, headers=headers)
        assert response.status_code == 403

        err = response.json()
        assert err["code"] == "FORBIDDEN_ORGANIZATION_ACCESS"
        assert err["principle_violated"] == "PR-7"
        assert "ORG-07" in err["message"]

    def test_diagnosis_allowed_chief_global_access(self, client_with_mock_orchestrator):
        """U-I3 (Carolina Vera, jefa de implementación) tiene supervisión global sobre ORG-07 (PR-7)."""
        token_u3, _, _ = create_session_token("U-I3")
        headers = {"Authorization": f"Bearer {token_u3}"}

        payload = {
            "message": "Evaluar si ORG-07 puede salir a producción",
            "organization_context": "ORG-07",
        }

        response = client_with_mock_orchestrator.post("/api/chat", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["evidence_status"] == "COMPLETA"

    def test_chat_unauthenticated_request_rejected(self, client_with_mock_orchestrator):
        """Petición sin token de sesión: rechazada con 401 (PR-7)."""
        response = client_with_mock_orchestrator.post("/api/chat", json={"message": "Hola"})
        assert response.status_code == 401
        assert response.json()["code"] == "MISSING_SESSION_TOKEN"

    def test_chat_empty_message_rejected(self, client_with_mock_orchestrator):
        """Petición con mensaje vacío: rechazada con 400."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        response = client_with_mock_orchestrator.post(
            "/api/chat",
            json={"message": "    "},
            headers=headers,
        )
        assert response.status_code == 400
        assert response.json()["code"] == "EMPTY_MESSAGE"

    def test_chat_explicit_abstention_on_unsupported_domain(self, client_with_mock_orchestrator):
        """Consulta sobre tema ajeno al corpus genera abstención explícita con status 200 (PR-3)."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        payload = {"message": "¿Existe alguna bonificación por almuerzo en la empresa?"}
        response = client_with_mock_orchestrator.post("/api/chat", json=payload, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["evidence_status"] == "ABSTENCION"
        assert "Abstención explícita (PR-3)" in data["answer"]

    def test_unexpected_500_error_is_sanitized_and_does_not_leak_internals(
        self, client_with_mock_orchestrator
    ):
        """Excepciones no controladas en el orquestador se sanitizan en 500 sin fugar rutas ni stacktraces."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        # Mock del orquestador que lanza una excepción crítica con información sensible
        mock_orch = MagicMock()
        mock_orch.process_chat = AsyncMock(
            side_effect=RuntimeError("Fallo crítico en /var/run/secrets/mira_master_key.pem: DB corrupta")
        )

        app.dependency_overrides[get_orchestrator] = lambda: mock_orch
        try:
            client = TestClient(app)
            response = client.post(
                "/api/chat",
                json={"message": "¿Qué le falta a ORG-07?", "organization_context": "ORG-07"},
                headers=headers,
            )
            assert response.status_code == 500
            data = response.json()
            assert data["code"] == "INTERNAL_ORCHESTRATOR_ERROR"
            assert "error interno al procesar la consulta" in data["message"]
            # Verificar que NINGUNA ruta sensible ni mensaje crudo fue expuesto al cliente
            assert "/var/run/secrets" not in str(data)
            assert "mira_master_key.pem" not in str(data)
            assert "RuntimeError" not in str(data)
        finally:
            app.dependency_overrides.clear()

    def test_end_to_end_chat_with_gemini_async_mock(self, mock_cu3_fastmcp_server):
        """Verifica la orquestación conversacional completa invocando al cliente Gemini oficial."""
        token_u1, _, _ = create_session_token("U-I1")
        headers = {"Authorization": f"Bearer {token_u1}"}

        mcp_client = MiraMcpClient(transport=mock_cu3_fastmcp_server)

        # Mock de Gemini asíncrono oficial
        mock_gemini = MagicMock()
        mock_gen_response = MagicMock()
        mock_gen_response.text = (
            "Síntesis oficial generada por Gemini Flash: La organización ORG-07 presenta 3 brechas pendientes "
            "(umbrales T-023, biometría T-025 y formularios F-01)."
        )
        mock_gemini.aio.models.generate_content = AsyncMock(return_value=mock_gen_response)

        orchestrator = MiraOrchestrator(mcp_client=mcp_client, gemini_client=mock_gemini)
        app.dependency_overrides[get_orchestrator] = lambda: orchestrator

        try:
            client = TestClient(app)
            payload = {
                "message": "¿Qué le falta a la organización ORG-07 para pasar a producción?",
                "organization_context": "ORG-07",
            }
            response = client.post("/api/chat", json=payload, headers=headers)
            assert response.status_code == 200

            data = response.json()
            assert mock_gemini.aio.models.generate_content.called
            assert "Síntesis oficial generada por Gemini Flash" in data["answer"]
            assert data["evidence_status"] == "COMPLETA"
            assert len(data["citations"]) >= 1
            assert len(data["mcp_traces"]) >= 3
        finally:
            app.dependency_overrides.clear()
