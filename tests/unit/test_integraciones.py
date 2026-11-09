"""
Pruebas unitarias para consultar_integracion y consultar_formularios (US1, T016).
Valida telemetría de pruebas, detección del límite de tasa (240 vs 100 req/min) y control de acceso (PR-5, PR-7).
"""

from __future__ import annotations

import pytest

from backend.data.init_db import init_database
from backend.mcp.access_control import McpSecurityError, set_current_user_id
from backend.mcp.tools.sql_tools import consultar_formularios, consultar_integracion


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Inicializa una base de datos limpia para cada prueba unitaria."""
    test_db = tmp_path / "test_mira.db"
    init_database(db_path=test_db, quiet=True)
    # Establecer variable de entorno para que db.py apunte a esta BD temporal
    import os
    os.environ["SQLITE_DB_PATH"] = str(test_db)
    yield
    set_current_user_id(None)


def test_consultar_integracion_org07_detecta_exceso_de_tasa_y_fallos_callback():
    """
    US1 / T016: ORG-07 registra 240 req/min (límite REQ-INT §5 = 100) y solo 14 de 20 callbacks.
    Debe generar la alerta técnica estructurada requerida.
    """
    set_current_user_id("U-I1")  # Sofía Tapia, ejecutiva asignada a ORG-07
    result = consultar_integracion("ORG-07")

    assert result["org_id"] == "ORG-07"
    assert result["integracion_id"] == "I-03"
    assert result["modo"] == "api_asincronica"
    assert result["ambiente"] == "integracion"
    assert result["casos_ejemplo_enviados"] == 20
    assert result["llamadas_vuelta_exitosas"] == 14
    assert result["max_llamadas_por_minuto_observado"] == 240

    assert result["alerta_tecnica"] is not None
    assert "100 req/min" in result["alerta_tecnica"]
    assert "240 req/min" in result["alerta_tecnica"]
    assert "14 de 20" in result["alerta_tecnica"]


def test_consultar_integracion_org06_dentro_de_limite():
    """
    ORG-06 tiene 80 req/min y 25/25 callbacks exitosos. No debe alertar exceso de tasa.
    """
    set_current_user_id("U-I2")  # Diego Fuentes, ejecutivo asignado a ORG-06
    result = consultar_integracion("ORG-06")

    assert result["org_id"] == "ORG-06"
    assert result["integracion_id"] == "I-02"
    assert result["max_llamadas_por_minuto_observado"] == 80
    assert result["casos_ejemplo_enviados"] == 25
    assert result["llamadas_vuelta_exitosas"] == 25
    assert result["alerta_tecnica"] is None


def test_consultar_formularios_org07():
    """
    US1 / T019: ORG-07 tiene registrado F-01 ('Ficha de ingreso Valle Verde') con 12 ejemplos (mínimo 20).
    """
    set_current_user_id("U-I1")
    result = consultar_formularios("ORG-07")

    assert result["org_id"] == "ORG-07"
    forms = result["formularios"]
    assert len(forms) == 1
    f1 = forms[0]
    assert f1["formulario_id"] == "F-01"
    assert f1["nombre"] == "Ficha de ingreso Valle Verde"
    assert f1["ejemplos_recibidos"] == 12
    assert f1["estado"] == "recibido"
    assert f1["fecha_ejemplos_completos"] is None


def test_consultar_integracion_rechazo_organizacion_no_asignada():
    """
    PR-7: U-I1 (asignada a ORG-05 y ORG-07) no puede consultar ORG-06.
    """
    set_current_user_id("U-I1")
    with pytest.raises(McpSecurityError) as exc_info:
        consultar_integracion("ORG-06")
    assert exc_info.value.code == "FORBIDDEN_ORGANIZATION_ACCESS"
    assert "U-I1" in exc_info.value.message


def test_consultar_integracion_rechazo_rol_comercial():
    """
    PR-7: U-I4 (comercial) tiene denegado el acceso a integraciones y formularios.
    """
    set_current_user_id("U-I4")
    with pytest.raises(McpSecurityError) as exc_info:
        consultar_integracion("ORG-07")
    assert exc_info.value.code == "FORBIDDEN_ROLE_ACCESS"

    with pytest.raises(McpSecurityError) as exc_info:
        consultar_formularios("ORG-07")
    assert exc_info.value.code == "FORBIDDEN_ROLE_ACCESS"

