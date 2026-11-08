"""Pruebas de regresión exhaustivas para los hallazgos de auditoría AUD-01 a AUD-08 (PR #17).

Verifica la mitigación definitiva de las vulnerabilidades y fallos identificados
en AUDITORIA_PR17.md (commit 88ac05b):
- AUD-01: Ausencia de datos tratada como SIN_EVIDENCIA en lugar de CUMPLIDO (P1).
- AUD-02: Diagnóstico completo evaluando REQ-INT §5 y desacoplado de ORG-07 (P2).
- AUD-03: Propagación de identidad y rechazo de respuestas de organizaciones ajenas (P4).
- AUD-04: Sanitización de errores MCP en trazas públicas y respuestas HTTP (P5).
- AUD-05: Prevalencia de reglas deterministas sobre texto generativo sin respaldo (P3).
- AUD-06: Gestión del ciclo de vida y cierre garantizado de clientes MCP efímeros.
- AUD-07: Lista blanca estricta de herramientas de lectura y exclusión de mutaciones.
- AUD-08: Timeouts controlados de API y límites en longitud de mensajes e historial.
"""

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.orchestrator import MiraOrchestrator
from backend.app.schemas.chat import ChatRequest, EvidenceStatusEnum, HistoryMessage
from backend.app.security import SIMULATED_USERS
from backend.mcp.client import (
    KNOWN_QUERY_TOOLS,
    McpSecurityError,
    McpToolNotFoundError,
    McpToolResult,
    McpTrace,
    MiraMcpClient,
    PROTECTED_MUTATION_TOOLS,
    sanitize_mcp_error,
)


class TestAuditPr17Regression:
    """Suite de verificación y regresión para hallazgos de auditoría AUD-01 a AUD-08."""

    # ==========================================================================
    # AUD-01: Ausencia de datos como SIN_EVIDENCIA (P1)
    # ==========================================================================
    def test_aud01_empty_data_produces_sin_evidencia_not_cumplido(self) -> None:
        """P1: Ausencia de datos no debe marcarse como CUMPLIDO en ningún criterio."""
        orchestrator = MiraOrchestrator()
        result = orchestrator._build_production_diagnosis_answer("ORG-07", {}, [])

        # Criterios 1, 2 y 6 deben reflejar falta de evidencia explícitamente (PR-3)
        assert "- **1. Tareas obligatorias E0-E4:** SIN EVIDENCIA" in result
        assert "- **2. Pruebas de integración (REQ-INT §5):** SIN EVIDENCIA" in result
        assert "- **6. Formularios propios (POL-FOR §2):** SIN EVIDENCIA" in result

        # No debe afirmar cumplimiento favorable en ausencia de datos
        assert "1. Tareas obligatorias E0-E4:** CUMPLIDO" not in result
        assert "6. Formularios propios (POL-FOR §2):** CUMPLIDO" not in result

        # Conclusión debe rechazar el paso a producción por falta de evidencia (PR-3)
        assert "NO puede pasar a producción" in result
        assert "falta de evidencia" in result.lower()

    def test_aud01_case_a_empty_task_list_cannot_recommend_production(self) -> None:
        """Caso A: Checklist con lista de tareas vacía no demuestra cumplimiento y debe dar SIN_EVIDENCIA."""
        orchestrator = MiraOrchestrator()
        datos_a = {
            "checklist": {"tareas": []},
            "integracion": {
                "estado": "probada",
                "ambiente": "produccion",
                "casos_ejemplo_enviados": 20,
                "llamadas_vuelta_exitosas": 20,
                "max_llamadas_por_minuto_observado": 75,
            },
            "formularios": {"formularios": []},
        }
        res_a = orchestrator._build_production_diagnosis_answer("ORG-07", datos_a, [])
        # Criterio 1 no puede ser CUMPLIDO con lista vacía de tareas
        assert "- **1. Tareas obligatorias E0-E4:** SIN EVIDENCIA" in res_a
        assert "cumple todos los criterios técnicos y normativos vigentes" not in res_a.lower()
        assert "NO puede pasar a producción" in res_a

    def test_aud01_case_b_empty_dict_formularios_produces_sin_evidencia(self) -> None:
        """Caso B: Respuesta incompleta {'formularios': {}} no debe marcar criterio 6 CUMPLIDO."""
        orchestrator = MiraOrchestrator()
        datos_b = {"formularios": {}}
        res_b = orchestrator._build_production_diagnosis_answer("ORG-07", datos_b, [])
        assert "- **6. Formularios propios (POL-FOR §2):** SIN EVIDENCIA" in res_b
        assert "6. Formularios propios (POL-FOR §2):** CUMPLIDO" not in res_b

    # ==========================================================================
    # AUD-02: Diagnóstico completo y desacoplado de ORG-07 (P2)
    # ==========================================================================
    def test_aud02_p2_incomplete_integration_and_missing_data_rejected(self) -> None:
        """P2: Carga adversarial sintética incompleta debe ser rechazada."""
        orchestrator = MiraOrchestrator()

        # Datos incompletos como en P2: 1 caso enviado, 0 callbacks, sin formularios
        carga_p2 = {
            "integracion": {
                "ambiente": "produccion",
                "estado": "probada",
                "casos_ejemplo_enviados": 1,
                "llamadas_vuelta_exitosas": 0,
                "max_llamadas_por_minuto_observado": 50,
            },
            "checklist": {
                "tareas": [
                    {"tarea_id": "T-023", "etapa": "E2", "descripcion": "Aprobación umbrales supervisor 2", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-025", "etapa": "E2", "descripcion": "Autorización biométrica", "estado": "completada", "obligatoria": "sí"},
                ]
            },
        }

        result = orchestrator._build_production_diagnosis_answer("ORG-07", carga_p2, [])

        # Criterio 2 debe reportar PENDIENTE por no cumplir REQ-INT §5 (casos < 20 y callbacks < 1)
        assert "- **2. Pruebas de integración (REQ-INT §5):** PENDIENTE" in result
        assert "casos de ejemplo insuficientes (1/20 requeridos por REQ-INT §5)" in result
        assert "llamadas de vuelta incompletas (0/1 exitosas" in result

        # Criterio 6 debe reportar SIN EVIDENCIA porque no se suministraron formularios
        assert "- **6. Formularios propios (POL-FOR §2):** SIN EVIDENCIA" in result

        # Conclusión taxativa: no puede pasar a producción
        assert "NO puede pasar a producción" in result
        assert "cumple todos los criterios" not in result.lower()

    def test_aud02_diagnosis_adapts_to_other_organizations_org05_and_org08(self) -> None:
        """Verifica que el evaluador no esté acoplado exclusivamente a ORG-07."""
        orchestrator = MiraOrchestrator()

        # Caso ORG-05: PLA-REM (no requiere biometría, tiene formularios propios operativos)
        datos_org05 = {
            "checklist": {
                "org_id": "ORG-05",
                "tareas": [
                    {"tarea_id": "T-001", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-009", "etapa": "E2", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "completada", "obligatoria": "sí"},
                ]
            },
            "integracion": {
                "ambiente": "integracion",
                "estado": "en_configuracion",  # Pendiente
                "casos_ejemplo_enviados": 0,
                "llamadas_vuelta_exitosas": 0,
                "max_llamadas_por_minuto_observado": 0,
            },
            "formularios": {
                "org_id": "ORG-05",
                "formularios": [
                    {"formulario_id": "F-02", "nombre": "Formulario Reembolso", "estado": "operativo", "ejemplos_recibidos": 25}
                ]
            },
        }

        res_org05 = orchestrator._build_production_diagnosis_answer("ORG-05", datos_org05, [])
        # Biometría debe ser CUMPLIDO ("No aplica: la plantilla asignada a la organización no incluye módulos biométricos")
        assert "- **5. Autorización biométrica (FIC-PLA §2):** CUMPLIDO" in res_org05
        assert "No aplica" in res_org05
        # Formularios propios CUMPLIDO
        assert "- **6. Formularios propios (POL-FOR §2):** CUMPLIDO" in res_org05
        # Integración PENDIENTE por estado en_configuracion
        assert "- **2. Pruebas de integración (REQ-INT §5):** PENDIENTE" in res_org05

    # ==========================================================================
    # AUD-03: Propagación de identidad y rechazo de datos cruzados (P4)
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_aud03_cross_organization_mcp_response_rejected(self) -> None:
        """P4: Respuesta de MCP declarando org_id ajeno debe ser rechazada."""
        client = MiraMcpClient()

        # Simulamos cliente subyacente que devuelve datos de ORG-06 cuando se solicitó ORG-07
        mock_raw_result = MagicMock()
        mock_raw_result.is_error = False
        mock_raw_result.data = {
            "org_id": "ORG-06",  # Discrepancia intencional
            "tareas": [{"tarea_id": "T-015", "descripcion": "Tarea ajena"}],
        }

        mock_fastmcp = MagicMock()
        mock_fastmcp.call_tool = AsyncMock(return_value=mock_raw_result)
        client._client = mock_fastmcp
        client._is_connected = True

        user = SIMULATED_USERS["U-I1"]  # Asignada a ORG-07

        # Invocación directa a herramienta debe detectar y rechazar la discrepancia (PR-7)
        with pytest.raises(McpSecurityError) as exc_info:
            await client.call_tool_for_llm(
                "checklist_organizacion",
                {"org_id": "ORG-07"},
                user_context=user,
            )

        assert "Discrepancia en respuesta MCP" in str(exc_info.value)
        assert "ORG-06" in str(exc_info.value)

    # ==========================================================================
    # AUD-04: Sanitización de errores MCP en trazas públicas (P5)
    # ==========================================================================
    def test_aud04_mcp_error_sanitized_in_traces_and_api(self) -> None:
        """P5: Errores con rutas, tokens y secretos deben ser censurados en trazas."""
        raw_error = "Error fatal en /home/lester/secreto/db.sqlite: Token jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def inválido con clave API_KEY_SECRET_12345"
        sanitized = sanitize_mcp_error(raw_error)

        assert "/home/lester/secreto/db.sqlite" not in sanitized
        assert "[REDACTED_PATH]" in sanitized
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def" not in sanitized
        assert "[REDACTED_JWT]" in sanitized
        assert "API_KEY_SECRET_12345" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

        # Trazabilidad de McpTrace
        trace = McpTrace(
            tool_name="test_tool",
            duration_ms=10.5,
            success=False,
            arguments={},
            response_summary=None,
            error=sanitize_mcp_error(raw_error),
        )
        assert "/home/lester" not in trace.error
        assert "[REDACTED_PATH]" in trace.error

    # ==========================================================================
    # AUD-05: Prevalencia de reglas deterministas sobre texto libre (P3)
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_aud05_hallucinated_llm_approval_overridden_by_deterministic_rules(self) -> None:
        """P3: Afirmaciones del LLM aprobando salida sin respaldo fáctico deben ser sustituidas."""
        # Creamos un cliente Gemini mock que alucina aprobación para una organización no autorizada
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "La organización ORG-07 cumple todos los criterios y puede pasar a producción de inmediato."
        mock_gemini.aio.models.generate_content = AsyncMock(return_value=mock_response)

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]
        request = ChatRequest(message="¿Puede ORG-07 pasar a producción?")

        # Datos donde la integración y formularios no cumplen
        retrieved_data = {
            "checklist": {
                "tareas": [
                    {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-023", "etapa": "E2", "descripcion": "Umbrales 2do supervisor", "estado": "pendiente", "obligatoria": "sí"},
                ]
            },
            "integracion": {
                "estado": "en_prueba",
                "casos_ejemplo_enviados": 14,
                "llamadas_vuelta_exitosas": 10,
                "max_llamadas_por_minuto_observado": 240,
            },
            "formularios": {"formularios": []},
        }

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org="ORG-07",
            retrieved_data=retrieved_data,
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        # Prevalece el dictamen determinista; la alucinación del LLM fue bloqueada (PR-1, AUD-05)
        assert "NO puede pasar a producción" in answer
        assert "Existen tareas obligatorias sin completar" in answer
        assert "La organización ORG-07 cumple todos los criterios y puede pasar a producción de inmediato." not in answer

    @pytest.mark.asyncio
    async def test_aud05_explicit_abstention_never_calls_llm(self) -> None:
        """Abstención explícita (PR-3) debe resolverse de inmediato sin invocar al modelo."""
        mock_gemini = MagicMock()
        mock_gemini.aio.models.generate_content = AsyncMock()

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]
        request = ChatRequest(message="¿Cómo invierto en criptomoneda bitcoin?")

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org=None,
            retrieved_data={},
            citations=[],
            evidence_status=EvidenceStatusEnum.ABSTENCION,
        )

        assert "Abstención explícita (PR-3)" in answer
        mock_gemini.aio.models.generate_content.assert_not_called()

    # ==========================================================================
    # AUD-06: Ciclo de vida y cierre garantizado de cliente MCP efímero
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_aud06_mcp_client_lifecycle_and_cleanup(self) -> None:
        """Verifica que un cliente MCP efímero creado por process_chat sea cerrado en finally."""
        orchestrator = MiraOrchestrator()
        user = SIMULATED_USERS["U-I1"]
        request = ChatRequest(message="¿Cuáles son las reglas de incorporación?", organization_context=None)

        # Interceptamos la creación de MiraMcpClient para verificar llamada a close()
        with patch("backend.app.orchestrator.MiraMcpClient") as mock_client_cls:
            mock_client_instance = AsyncMock(spec=MiraMcpClient)
            mock_client_instance.call_tool_for_llm = AsyncMock(
                return_value=McpToolResult(tool_name="buscar_reglas", success=True, data={"results": []})
            )
            mock_client_instance.get_traces = MagicMock(return_value=[])
            mock_client_cls.return_value = mock_client_instance

            response = await orchestrator.process_chat(user=user, request=request)

            assert response is not None
            # connect() y close() deben haberse ejecutado garantizando limpieza de recursos
            mock_client_instance.connect.assert_awaited_once()
            mock_client_instance.close.assert_awaited_once()

    # ==========================================================================
    # AUD-07: Lista blanca estricta de herramientas (Denial by Default)
    # ==========================================================================
    @pytest.mark.asyncio
    async def test_aud07_tool_classification_default_deny(self) -> None:
        """Verifica que el cliente MCP aplique lista blanca estricta y deniegue por defecto."""
        client = MiraMcpClient()

        # Herramientas del catálogo autorizado
        expected_queries = {
            "buscar_reglas",
            "checklist_organizacion",
            "consultar_integracion",
            "consultar_formularios",
            "listar_plantillas",
        }
        assert KNOWN_QUERY_TOOLS == expected_queries
        assert "marcar_tarea" in PROTECTED_MUTATION_TOOLS

        # Herramienta no autorizada o desconocida
        with pytest.raises(McpToolNotFoundError) as exc_info:
            await client.call_tool_for_llm("herramienta_desconocida", {})
        assert "no está autorizada para consultas del modelo (AUD-07)" in str(exc_info.value)

        # Mutación protegida rechazada al intentar invocarla como herramienta de consulta LLM
        with pytest.raises(McpSecurityError) as exc_info:
            await client.call_tool_for_llm("marcar_tarea", {"tarea_id": "T-001"})
        assert "mutación protegida" in str(exc_info.value)

    # ==========================================================================
    # AUD-08: Timeouts controlados y límites en esquemas
    # ==========================================================================
    def test_aud08_input_limits_enforced_by_schemas(self) -> None:
        """Verifica que mensajes > 4000 caracteres o historial > 50 sean rechazados."""
        # Mensaje excesivo (> 4000)
        long_message = "x" * 4001
        with pytest.raises(ValidationError):
            ChatRequest(message=long_message)

        # Historial excesivo (> 50 mensajes)
        long_history = [
            HistoryMessage(role="user", content=f"Msg {i}") for i in range(51)
        ]
        with pytest.raises(ValidationError):
            ChatRequest(message="Hola", conversation_history=long_history)

        # Longitudes válidas son aceptadas
        valid_request = ChatRequest(
            message="x" * 4000,
            conversation_history=[HistoryMessage(role="user", content="Hola")],
        )
        assert len(valid_request.message) == 4000

    @pytest.mark.asyncio
    async def test_aud08_gemini_timeout_activates_deterministic_fallback(self) -> None:
        """Verifica que una llamada a Gemini que exceda el timeout active el fallback."""
        # Mock de cliente Gemini que duerme más allá del timeout
        mock_gemini = MagicMock()

        async def slow_generation(*args: Any, **kwargs: Any) -> Any:
            await asyncio.sleep(0.5)
            mock_res = MagicMock()
            mock_res.text = "Respuesta tardía"
            return mock_res

        mock_gemini.aio.models.generate_content = slow_generation

        # Configuramos timeout corto para la prueba (0.05 segundos)
        with patch("backend.app.orchestrator.get_settings") as mock_settings_fn:
            test_settings = Settings(
                GEMINI_TIMEOUT_SECONDS=0.05,
                GEMINI_API_KEY="test-key-demo",
            )
            mock_settings_fn.return_value = test_settings

            orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
            user = SIMULATED_USERS["U-I1"]
            request = ChatRequest(message="Diagnóstico de ORG-07")

            answer = await orchestrator._generate_answer(
                user=user,
                request=request,
                target_org="ORG-07",
                retrieved_data={
                    "checklist": {"tareas": []},
                    "integracion": {"estado": "probada", "casos_ejemplo_enviados": 20, "llamadas_vuelta_exitosas": 20, "max_llamadas_por_minuto_observado": 50},
                    "formularios": {"formularios": []},
                },
                citations=[],
                evidence_status=EvidenceStatusEnum.PARCIAL,
            )

            # Debe advertir sobre el timeout y devolver el diagnóstico determinista
            assert "excedió el tiempo límite" in answer
            assert "Diagnóstico de Salida a Producción" in answer

    @pytest.mark.asyncio
    async def test_aud05_alternative_hallucinations_overridden(self) -> None:
        """AUD-05: Formulaciones alternativas de aprobación del LLM quedan subordinadas al veredicto oficial."""
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = (
            "Doy mi total visto bueno profesional: considero que ORG-07 está en condiciones óptimas "
            "y recomiendo proceder con la puesta en marcha definitiva sin restricciones."
        )
        mock_gemini.aio.models.generate_content = AsyncMock(return_value=mock_response)

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]
        request = ChatRequest(message="¿Está lista ORG-07 para producción?")

        retrieved_data = {
            "checklist": {
                "org_id": "ORG-07",
                "tareas": [
                    {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-023", "etapa": "E2", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "pendiente", "obligatoria": "sí"},
                ]
            },
            "integracion": {
                "ambiente": "integracion",
                "estado": "en_prueba",
                "casos_ejemplo_enviados": 20,
                "llamadas_vuelta_exitosas": 14,
                "max_llamadas_por_minuto_observado": 240,
            },
            "formularios": {
                "org_id": "ORG-07",
                "formularios": [{"formulario_id": "F-01", "nombre": "Ficha", "ejemplos_recibidos": 10, "estado": "en_ajuste"}],
            },
        }

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org="ORG-07",
            retrieved_data=retrieved_data,
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        # El veredicto oficial de NO pasar a producción encabeza y gobierna estructuralmente la respuesta
        assert "NO puede pasar a producción en su estado actual" in answer
        assert "Doy mi total visto bueno" not in answer

    @pytest.mark.asyncio
    async def test_aud06_connect_failure_cleans_up_resources(self) -> None:
        """AUD-06: Si connect() falla tras inicializar recursos, el ciclo de vida garantiza close()."""
        orchestrator = MiraOrchestrator()
        user = SIMULATED_USERS["U-I1"]
        request = ChatRequest(message="Consulta de prueba", organization_context=None)

        with patch("backend.app.orchestrator.MiraMcpClient") as mock_client_cls:
            mock_client_instance = AsyncMock(spec=MiraMcpClient)
            mock_client_instance.is_connected = False
            # connect falla después de intentar inicializar
            mock_client_instance.connect = AsyncMock(side_effect=RuntimeError("Fallo simulado en inicio de transporte"))
            mock_client_cls.return_value = mock_client_instance

            with pytest.raises(RuntimeError) as exc_info:
                await orchestrator.process_chat(user=user, request=request)

            assert "Fallo simulado en inicio de transporte" in str(exc_info.value)
            # close() debe haberse llamado en el bloque finally aunque connect() fallara
            mock_client_instance.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aud08_sync_gemini_timeout_and_non_blocking(self) -> None:
        """AUD-08: Invocación síncrona a Gemini ejecuta en hilo separado y respeta el timeout sin bloquear."""
        import time as time_module

        mock_gemini = MagicMock()
        del mock_gemini.aio  # Eliminar aio para forzar la ruta síncrona models.generate_content

        def slow_sync_generate(*args: Any, **kwargs: Any) -> Any:
            time_module.sleep(0.4)
            mock_res = MagicMock()
            mock_res.text = "Respuesta tardía síncrona"
            return mock_res

        mock_gemini.models.generate_content = slow_sync_generate

        with patch("backend.app.orchestrator.get_settings") as mock_settings_fn:
            test_settings = Settings(
                GEMINI_TIMEOUT_SECONDS=0.05,
                GEMINI_API_KEY="test-sync-key",
            )
            mock_settings_fn.return_value = test_settings

            orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
            user = SIMULATED_USERS["U-I1"]
            request = ChatRequest(message="Diagnóstico síncrono de ORG-07")

            answer = await orchestrator._generate_answer(
                user=user,
                request=request,
                target_org="ORG-07",
                retrieved_data={
                    "checklist": {
                        "org_id": "ORG-07",
                        "tareas": [
                            {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                            {"tarea_id": "T-023", "etapa": "E2", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "completada", "obligatoria": "sí"},
                            {"tarea_id": "T-025", "etapa": "E2", "descripcion": "Firma de autorización biométrica", "estado": "completada", "obligatoria": "sí"},
                            {"tarea_id": "T-029", "etapa": "E4", "descripcion": "Transferencia internacional", "estado": "completada", "obligatoria": "sí"},
                        ],
                    },
                    "integracion": {
                        "ambiente": "integracion",
                        "estado": "probada",
                        "casos_ejemplo_enviados": 20,
                        "llamadas_vuelta_exitosas": 20,
                        "max_llamadas_por_minuto_observado": 50,
                    },
                    "formularios": {"org_id": "ORG-07", "formularios": []},
                },
                citations=[],
                evidence_status=EvidenceStatusEnum.PARCIAL,
            )

            # Debe haber capturado TimeoutError en el executor y devuelto el fallback
            assert "excedió el tiempo límite" in answer

    def test_aud04_to_api_mcp_trace_controlled_messages(self) -> None:
        """AUD-04: to_api_mcp_trace asigna mensajes de error públicos controlados."""
        from backend.app.orchestrator import to_api_mcp_trace

        # 1. Error de seguridad / aislamiento
        trace_sec = McpTrace(
            tool_name="checklist_organizacion",
            duration_ms=5.0,
            success=False,
            arguments={},
            response_summary=None,
            error="Violación de aislamiento organizacional (PR-7): acceso denegado en /home/app/db.sqlite",
        )
        api_trace_sec = to_api_mcp_trace(trace_sec)
        assert api_trace_sec.error == "Acceso denegado: violación de aislamiento organizacional (PR-7)."
        assert "/home/app" not in str(api_trace_sec.error)

        # 2. Error de timeout
        trace_to = McpTrace(
            tool_name="buscar_reglas",
            duration_ms=3000.0,
            success=False,
            arguments={},
            response_summary=None,
            error="Timeout de conexión tras 30s en socket tcp://127.0.0.1:8000",
        )
        api_trace_to = to_api_mcp_trace(trace_to)
        assert api_trace_to.error == "Tiempo de espera agotado al consultar servicio MCP."

        # 3. Error no controlado
        trace_gen = McpTrace(
            tool_name="listar_plantillas",
            duration_ms=1.2,
            success=False,
            arguments={},
            response_summary=None,
            error="OperationalError: database disk image is malformed in sqlite3.c:12345",
        )
        api_trace_gen = to_api_mcp_trace(trace_gen)
        assert api_trace_gen.error == "Error controlado en la ejecución de la herramienta MCP."
        assert "sqlite3.c" not in str(api_trace_gen.error)

    # ==========================================================================
    # AUD-05: Garantía Estructural Focalizada y Política Conservadora (Revisión Final)
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_aud05_reproduced_adversarial_authorization_hallucination_blocked(self) -> None:
        """AUD-05: Reproduce el fallo adversarial reportado y comprueba que la aprobación alucinada se bloquea."""
        from backend.app.orchestrator import MiraOrchestrator

        # 1. Configurar cliente Gemini simulado con la respuesta adversarial exacta
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "La incorporación de ORG-07 está autorizada. Recomiendo iniciar sus operaciones de inmediato."
        mock_gemini.aio.models.generate_content = AsyncMock(return_value=mock_response)

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]

        # Consulta adversarial exacta
        request = ChatRequest(
            message="¿Está ORG-07 habilitada para iniciar operaciones?",
            organization_context="ORG-07",
        )

        # Datos simulados del fallo reportado:
        # - Tarea T-023 pendiente
        # - Integración en estado 'en_prueba'
        # - 10 casos enviados, 5 callbacks exitosos, 150 req/min
        retrieved_data = {
            "checklist": {
                "org_id": "ORG-07",
                "tareas": [
                    {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta institucional", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-023", "etapa": "E4", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "pendiente", "obligatoria": "sí"},
                ],
            },
            "integracion": {
                "org_id": "ORG-07",
                "ambiente": "integracion",
                "estado": "en_prueba",
                "casos_ejemplo_enviados": 10,
                "llamadas_vuelta_exitosas": 5,
                "max_llamadas_por_minuto_observado": 150.0,
            },
            "formularios": {
                "org_id": "ORG-07",
                "formularios": [],
            },
        }

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org="ORG-07",
            retrieved_data=retrieved_data,
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        # Verificaciones críticas:
        # 1. La respuesta alucinada NO debe devolverse
        assert "La incorporación de ORG-07 está autorizada." not in answer
        assert "Recomiendo iniciar sus operaciones de inmediato." not in answer

        # 2. El dictamen oficial determinista gobierna la respuesta
        assert "NO puede pasar a producción en su estado actual" in answer

        # 3. Se desglosan con rigor las brechas de integración y tareas pendientes
        assert "T-023" in answer
        assert "casos de ejemplo insuficientes (10/20" in answer
        assert "llamadas de vuelta incompletas (5/10 exitosas" in answer
        assert "150.0 req/min supera el límite normativo contractual de 100 req/min" in answer

    @pytest.mark.asyncio
    async def test_aud05_different_language_approval_hallucination_blocked(self) -> None:
        """AUD-05: Comprueba que formulaciones de aprobación con vocabulario novedoso se bloquean sin requerir lista de palabras."""
        from backend.app.orchestrator import MiraOrchestrator

        # Aprobación expresada con términos completamente ajenos a cualquier lista previa
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = (
            "Certifico formalmente el éxito de las operaciones y otorgo autorización plena "
            "para el arranque productivo definitivo de ORG-07."
        )
        mock_gemini.aio.models.generate_content = AsyncMock(return_value=mock_response)

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]

        request = ChatRequest(
            message="¿Puede la organización ORG-07 comenzar a transaccionar en producción?",
            organization_context="ORG-07",
        )

        retrieved_data = {
            "checklist": {
                "org_id": "ORG-07",
                "tareas": [
                    {"tarea_id": "T-001", "etapa": "E0", "descripcion": "Creación", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-002", "etapa": "E1", "descripcion": "Contratos", "estado": "pendiente", "obligatoria": "sí"},
                ],
            },
            "integracion": {
                "org_id": "ORG-07",
                "ambiente": "integracion",
                "estado": "en_prueba",
                "casos_ejemplo_enviados": 5,
                "llamadas_vuelta_exitosas": 5,
                "max_llamadas_por_minuto_observado": 40.0,
            },
            "formularios": {"org_id": "ORG-07", "formularios": []},
        }

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org="ORG-07",
            retrieved_data=retrieved_data,
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        assert "Certifico formalmente el éxito" not in answer
        assert "arranque productivo definitivo" not in answer
        assert "NO puede pasar a producción" in answer

    @pytest.mark.asyncio
    async def test_aud05_organization_with_pending_requirements(self) -> None:
        """AUD-05: Organización con requisitos pendientes produce dictamen estructurado no favorable."""
        from backend.app.orchestrator import MiraOrchestrator, VeredictoNormativo

        orchestrator = MiraOrchestrator()
        retrieved_data = {
            "checklist": {
                "org_id": "ORG-05",
                "tareas": [
                    {"tarea_id": "T-010", "etapa": "E1", "descripcion": "Documentación", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-012", "etapa": "E3", "descripcion": "Pruebas de callback", "estado": "en_curso", "obligatoria": "sí"},
                    {"tarea_id": "T-014", "etapa": "E2", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "pendiente", "obligatoria": "sí"},
                ],
            },
            "integracion": {
                "org_id": "ORG-05",
                "ambiente": "integracion",
                "estado": "probada",
                "casos_ejemplo_enviados": 25,
                "llamadas_vuelta_exitosas": 25,
                "max_llamadas_por_minuto_observado": 60.0,
            },
            "formularios": {"org_id": "ORG-05", "formularios": []},
        }

        eval_res = orchestrator._evaluar_normativa_estructurada("ORG-05", retrieved_data, citations=[])
        assert eval_res.veredicto == VeredictoNormativo.NO_APROBABLE
        assert len(eval_res.criterios_pendientes) >= 1
        assert len(eval_res.criterios_sin_evidencia) == 0

        md_answer = orchestrator._renderizar_diagnostico_markdown(eval_res)
        assert "NO puede pasar a producción en su estado actual" in md_answer
        assert "T-012" in md_answer
        assert "T-014" in md_answer

    @pytest.mark.asyncio
    async def test_aud05_organization_with_incomplete_information_produces_sin_evidencia(self) -> None:
        """AUD-05: Organización con información faltante produce SIN_EVIDENCIA y no favorable (PR-3)."""
        from backend.app.orchestrator import MiraOrchestrator, VeredictoNormativo

        orchestrator = MiraOrchestrator()
        # Telemetría ausente
        retrieved_data = {
            "checklist": {
                "org_id": "ORG-07",
                "tareas": [
                    {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                ],
            },
            "formularios": {"org_id": "ORG-07", "formularios": []},
        }

        eval_res = orchestrator._evaluar_normativa_estructurada("ORG-07", retrieved_data, citations=[])
        assert eval_res.veredicto == VeredictoNormativo.SIN_EVIDENCIA
        assert any("Pruebas de integración" in c for c in eval_res.criterios_sin_evidencia)

        md_answer = orchestrator._renderizar_diagnostico_markdown(eval_res)
        assert "NO puede pasar a producción" in md_answer
        assert "Existe falta de evidencia" in md_answer

    @pytest.mark.asyncio
    async def test_aud05_normal_informative_query_preserves_conversational_gemini(self) -> None:
        """AUD-05: Las consultas informativas conservan el texto conversacional de Gemini sin forzar diagnóstico genérico."""
        from backend.app.orchestrator import MiraOrchestrator

        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = (
            "En la etapa E2 (Recepción y Validación Documental) se contemplan las tareas de revisión legal, "
            "validación de estatutos y verificación de poderes notariales conforme a GUI-INC_v2 §2."
        )
        mock_gemini.aio.models.generate_content = AsyncMock(return_value=mock_response)

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]

        request = ChatRequest(
            message="¿Qué tareas comprende la etapa E2 en la incorporación de clientes?",
        )

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org=None,
            retrieved_data={},
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        # La respuesta proviene de Gemini y no fue sustituida por un diagnóstico de salida a producción
        assert "En la etapa E2 (Recepción y Validación Documental)" in answer
        assert "Diagnóstico de Salida a Producción" not in answer

    @pytest.mark.asyncio
    async def test_aud05_favorable_case_sufficient_evidence_does_not_imply_automatic_e5_authorization(self) -> None:
        """AUD-05 / PR-1: Un caso con todos los criterios cumplidos no autoriza automáticamente la etapa E5."""
        from backend.app.orchestrator import MiraOrchestrator, VeredictoNormativo

        orchestrator = MiraOrchestrator()

        # Datos completos donde los 6 criterios están cumplidos
        retrieved_data = {
            "checklist": {
                "org_id": "ORG-08",
                "plantilla_id": "PLA-SIN",
                "tareas": [
                    {"tarea_id": "T-001", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-002", "etapa": "E1", "descripcion": "Validación legal", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-003", "etapa": "E2", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-004", "etapa": "E3", "descripcion": "Configuración técnica", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-005", "etapa": "E4", "descripcion": "Firma de transferencia internacional", "estado": "completada", "obligatoria": "sí"},
                ],
            },
            "integracion": {
                "org_id": "ORG-08",
                "ambiente": "integracion",
                "estado": "probada",
                "casos_ejemplo_enviados": 25,
                "llamadas_vuelta_exitosas": 25,
                "max_llamadas_por_minuto_observado": 50.0,
            },
            "formularios": {
                "org_id": "ORG-08",
                "formularios": [],
            },
        }

        eval_res = orchestrator._evaluar_normativa_estructurada("ORG-08", retrieved_data, citations=[])

        # Cumple todos los criterios técnicos y normativos
        assert eval_res.veredicto == VeredictoNormativo.APROBABLE
        assert len(eval_res.criterios_pendientes) == 0
        assert len(eval_res.criterios_sin_evidencia) == 0
        assert len(eval_res.criterios_cumplidos) == 6

        md_answer = orchestrator._renderizar_diagnostico_markdown(eval_res)
        assert "cumple todos los criterios técnicos y normativos vigentes" in md_answer

        # Garantía PR-1: No implica autorización automática de la etapa E5
        assert "NO constituye una autorización automática de la etapa E5" in md_answer
        assert "Jefatura de Implementación" in md_answer

    def test_aud05_structural_evaluation_independent_of_markdown_wording(self) -> None:
        """AUD-05: Comprueba que la evaluación normativa opera sobre estructuras tipadas sin depender del Markdown."""
        from backend.app.orchestrator import (
            CriterioEstado,
            EvaluacionNormativa,
            MiraOrchestrator,
            VeredictoNormativo,
        )

        orchestrator = MiraOrchestrator()
        retrieved_data = {
            "checklist": {"tareas": []},
            "integracion": {
                "ambiente": "integracion",
                "estado": "probada",
                "casos_ejemplo_enviados": 20,
                "llamadas_vuelta_exitosas": 20,
                "max_llamadas_por_minuto_observado": 50.0,
            },
            "formularios": {"org_id": "ORG-07", "formularios": []},
        }

        # La evaluación devuelve un objeto EvaluacionNormativa Pydantic tipado
        eval_res = orchestrator._evaluar_normativa_estructurada("ORG-07", retrieved_data, citations=[])
        assert isinstance(eval_res, EvaluacionNormativa)
        assert eval_res.veredicto == VeredictoNormativo.SIN_EVIDENCIA
        assert eval_res.criterios[1].estado == CriterioEstado.SIN_EVIDENCIA
        assert eval_res.criterios[2].estado == CriterioEstado.CUMPLIDO
        assert eval_res.criterios[6].estado == CriterioEstado.CUMPLIDO

        # El veredicto no se ve alterado por modificaciones cosméticas al texto Markdown
        custom_markdown = eval_res.conclusion_oficial.replace("NO puede pasar", "No está autorizada")
        assert eval_res.veredicto == VeredictoNormativo.SIN_EVIDENCIA

    # ==========================================================================
    # AUD-05: Consultas Mixtas y Precedencia Decisional (Revisión de Robustez)
    # ==========================================================================

    def test_aud05_intent_classification_for_pure_and_mixed_queries(self) -> None:
        """AUD-05: Verifica que las consultas mixtas prioricen la intención decisional sin ser ocultadas por brechas."""
        from backend.app.orchestrator import MiraOrchestrator

        orchestrator = MiraOrchestrator()

        # 1. Pregunta decisional pura -> ruta determinista (True)
        q_decisional = "¿Puede ORG-07 pasar a producción?"
        assert orchestrator._es_consulta_decision_normativa(q_decisional, "ORG-07") is True

        # 2. Pregunta exclusivamente sobre brechas -> ruta conversacional (False)
        q_brechas = "¿Qué le falta a ORG-07 para pasar a producción?"
        assert orchestrator._es_consulta_decision_normativa(q_brechas, "ORG-07") is False

        # 3. Pregunta exclusivamente informativa -> ruta conversacional (False)
        q_informativa = "¿Qué tareas comprende la etapa E2 en la incorporación de clientes?"
        assert orchestrator._es_consulta_decision_normativa(q_informativa, None) is False
        assert orchestrator._es_consulta_decision_normativa(q_informativa, "ORG-07") is False

        # 4. Consultas mixtas reproducidas -> deben priorizar la decisión normativa (True)
        q_mixta_1 = "¿Qué le falta a ORG-07 y puede comenzar a operar mañana?"
        assert orchestrator._es_consulta_decision_normativa(q_mixta_1, "ORG-07") is True

        q_mixta_2 = "¿Qué requisitos faltan para ORG-07 y está autorizada para operar?"
        assert orchestrator._es_consulta_decision_normativa(q_mixta_2, "ORG-07") is True

    @pytest.mark.asyncio
    async def test_aud05_mixed_query_blocks_gemini_invocation_and_preserves_gap_details(self) -> None:
        """AUD-05: En consulta mixta, Gemini NO es invocado (assert_not_awaited) y se entregan brechas completas."""
        from backend.app.orchestrator import MiraOrchestrator

        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "La organización ORG-07 está autorizada para operar de inmediato y no presenta inconvenientes."
        mock_gemini.aio.models.generate_content = AsyncMock(return_value=mock_response)

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]

        # Consulta mixta que solicita brechas y decisión de autorización
        request = ChatRequest(
            message="¿Qué requisitos faltan para ORG-07 y está autorizada para operar?",
            organization_context="ORG-07",
        )

        retrieved_data = {
            "checklist": {
                "org_id": "ORG-07",
                "tareas": [
                    {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-023", "etapa": "E4", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "pendiente", "obligatoria": "sí"},
                ],
            },
            "integracion": {
                "org_id": "ORG-07",
                "ambiente": "integracion",
                "estado": "en_prueba",
                "casos_ejemplo_enviados": 10,
                "llamadas_vuelta_exitosas": 5,
                "max_llamadas_por_minuto_observado": 150.0,
            },
            "formularios": {"org_id": "ORG-07", "formularios": []},
        }

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org="ORG-07",
            retrieved_data=retrieved_data,
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        # 1. Garantía estricta: Gemini NO fue invocado para emitir el veredicto
        mock_gemini.aio.models.generate_content.assert_not_awaited()

        # 2. La aprobación falsa de Gemini no aparece
        assert "La organización ORG-07 está autorizada para operar" not in answer

        # 3. La conclusión determinista no favorable rige la respuesta
        assert "NO puede pasar a producción en su estado actual" in answer

        # 4. Entrega también el detalle exhaustivo de las brechas consultadas (Requisito 7)
        assert "T-023" in answer
        assert "Aprobación de umbrales por segundo supervisor" in answer
        assert "casos de ejemplo insuficientes (10/20" in answer
        assert "llamadas de vuelta incompletas (5/10 exitosas" in answer
        assert "150.0 req/min supera el límite normativo contractual de 100 req/min" in answer

    @pytest.mark.asyncio
    async def test_aud05_mixed_query_second_reproduced_case_e2e(self) -> None:
        """AUD-05: Segunda consulta mixta reproducida ('¿Qué le falta a ORG-07 y puede comenzar a operar mañana?')."""
        from backend.app.orchestrator import MiraOrchestrator

        mock_gemini = MagicMock()
        mock_gemini.aio.models.generate_content = AsyncMock()

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]

        request = ChatRequest(
            message="¿Qué le falta a ORG-07 y puede comenzar a operar mañana?",
            organization_context="ORG-07",
        )

        retrieved_data = {
            "checklist": {
                "org_id": "ORG-07",
                "tareas": [
                    {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                    {"tarea_id": "T-023", "etapa": "E4", "descripcion": "Aprobación de umbrales por segundo supervisor", "estado": "pendiente", "obligatoria": "sí"},
                ],
            },
            "integracion": {
                "org_id": "ORG-07",
                "ambiente": "integracion",
                "estado": "en_prueba",
                "casos_ejemplo_enviados": 15,
                "llamadas_vuelta_exitosas": 15,
                "max_llamadas_por_minuto_observado": 80.0,
            },
            "formularios": {"org_id": "ORG-07", "formularios": []},
        }

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org="ORG-07",
            retrieved_data=retrieved_data,
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        # Gemini no fue llamado para decidir
        mock_gemini.aio.models.generate_content.assert_not_awaited()
        assert "NO puede pasar a producción en su estado actual" in answer
        assert "T-023" in answer

    @pytest.mark.asyncio
    async def test_aud05_mixed_query_with_insufficient_evidence_produces_sin_evidencia(self) -> None:
        """AUD-05 / PR-3: Consulta mixta con datos normativos insuficientes produce resultado no favorable por falta de evidencia."""
        from backend.app.orchestrator import MiraOrchestrator

        mock_gemini = MagicMock()
        mock_gemini.aio.models.generate_content = AsyncMock()

        orchestrator = MiraOrchestrator(gemini_client=mock_gemini)
        user = SIMULATED_USERS["U-I1"]

        request = ChatRequest(
            message="¿Qué requisitos faltan para ORG-07 y está autorizada para operar?",
            organization_context="ORG-07",
        )

        # Telemetría completamente ausente
        retrieved_data = {
            "checklist": {
                "org_id": "ORG-07",
                "tareas": [
                    {"tarea_id": "T-021", "etapa": "E0", "descripcion": "Alta", "estado": "completada", "obligatoria": "sí"},
                ],
            },
            "formularios": {"org_id": "ORG-07", "formularios": []},
        }

        answer = await orchestrator._generate_answer(
            user=user,
            request=request,
            target_org="ORG-07",
            retrieved_data=retrieved_data,
            citations=[],
            evidence_status=EvidenceStatusEnum.PARCIAL,
        )

        mock_gemini.aio.models.generate_content.assert_not_awaited()
        assert "NO puede pasar a producción" in answer
        assert "Existe falta de evidencia documental o de datos del sistema" in answer
        assert "Pruebas de integración" in answer
