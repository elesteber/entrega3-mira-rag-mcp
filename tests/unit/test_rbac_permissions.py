"""
Pruebas unitarias de aislamiento organizacional y control RBAC en SQLite (US5, T040, T042, PR-7).
Valida aislamiento de organizaciones, exclusividad de etapa E5 para jefatura y mínimo privilegio comercial.
"""

from __future__ import annotations

import datetime
import os
import jwt
import pytest

from backend.data.init_db import init_database
from backend.mcp.access_control import (
    McpSecurityError,
    get_user_info,
    set_current_user_id,
    validate_user_access_to_org,
)
from backend.mcp.tools.mutation_tools import DEFAULT_JWT_SECRET, marcar_tarea
from backend.mcp.tools.sql_tools import (
    checklist_organizacion,
    consultar_formularios,
    consultar_integracion,
    listar_plantillas,
)


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Inicializa una base de datos limpia para cada prueba unitaria."""
    test_db = tmp_path / "test_mira_rbac.db"
    init_database(db_path=test_db, quiet=True)
    os.environ["SQLITE_DB_PATH"] = str(test_db)
    yield
    set_current_user_id(None)


def _token_for(tarea_id: str, org_id: str, nuevo_estado: str, usuario_id: str) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "action_type": "CAMBIO_ESTADO_TAREA",
        "tarea_id": tarea_id,
        "org_id": org_id,
        "nuevo_estado": nuevo_estado,
        "usuario_id": usuario_id,
        "exp": int((now + datetime.timedelta(minutes=5)).timestamp()),
        "jti": f"rbac-jti-{os.urandom(8).hex()}",
    }
    return jwt.encode(payload, DEFAULT_JWT_SECRET, algorithm="HS256")


def test_aislamiento_ejecutiva_u_i1():
    """
    PR-7: U-I1 solo puede consultar ORG-05 y ORG-07; se le deniega ORG-06 y ORG-08.
    """
    set_current_user_id("U-I1")

    # Permitidas
    assert checklist_organizacion("ORG-05")["org_id"] == "ORG-05"
    assert checklist_organizacion("ORG-07")["org_id"] == "ORG-07"

    # Denegadas
    with pytest.raises(McpSecurityError) as exc_info:
        checklist_organizacion("ORG-06")
    assert exc_info.value.code == "FORBIDDEN_ORGANIZATION_ACCESS"

    with pytest.raises(McpSecurityError) as exc_info:
        consultar_integracion("ORG-08")
    assert exc_info.value.code == "FORBIDDEN_ORGANIZATION_ACCESS"


def test_aislamiento_ejecutivo_u_i2():
    """
    PR-7: U-I2 solo puede consultar ORG-06 y ORG-08; se le deniega ORG-05 y ORG-07.
    """
    set_current_user_id("U-I2")

    # Permitidas
    assert checklist_organizacion("ORG-06")["org_id"] == "ORG-06"
    assert checklist_organizacion("ORG-08")["org_id"] == "ORG-08"

    # Denegadas
    with pytest.raises(McpSecurityError) as exc_info:
        checklist_organizacion("ORG-05")
    assert exc_info.value.code == "FORBIDDEN_ORGANIZATION_ACCESS"

    with pytest.raises(McpSecurityError) as exc_info:
        consultar_formularios("ORG-07")
    assert exc_info.value.code == "FORBIDDEN_ORGANIZATION_ACCESS"


def test_jefatura_u_i3_acceso_global():
    """
    PR-7: U-I3 (jefe_implementacion) posee acceso global a todas las organizaciones.
    """
    set_current_user_id("U-I3")
    for org in ["ORG-05", "ORG-06", "ORG-07", "ORG-08"]:
        res = checklist_organizacion(org)
        assert res["org_id"] == org


def test_comercial_u_i4_minimo_privilegio():
    """
    PR-7 / FR-017: U-I4 tiene acceso al catálogo general de plantillas,
    pero tiene denegado el acceso a checklists, integraciones y formularios.
    """
    set_current_user_id("U-I4")

    # Catálogo general permitido
    assert len(listar_plantillas()["plantillas"]) == 4

    # Operaciones de organizaciones bloqueadas
    with pytest.raises(McpSecurityError) as exc_info:
        checklist_organizacion("ORG-07")
    assert exc_info.value.code == "FORBIDDEN_ROLE_ACCESS"

    with pytest.raises(McpSecurityError) as exc_info:
        consultar_integracion("ORG-07")
    assert exc_info.value.code == "FORBIDDEN_ROLE_ACCESS"

    with pytest.raises(McpSecurityError) as exc_info:
        consultar_formularios("ORG-07")
    assert exc_info.value.code == "FORBIDDEN_ROLE_ACCESS"


def test_restriccion_etapa_e5_rechaza_ejecutivo():
    """
    PR-1 / PR-7 / FR-013: U-I1 (ejecutiva de ORG-05) intenta marcar T-010 (etapa E5: Salida a producción).
    Debe ser rechazada con FORBIDDEN_STAGE_E5 porque E5 es exclusiva de jefatura.
    """
    set_current_user_id("U-I1")
    token = _token_for("T-010", "ORG-05", "completada", "U-I1")

    with pytest.raises(McpSecurityError) as exc_info:
        marcar_tarea(
            tarea_id="T-010",
            nuevo_estado="completada",
            token_confirmacion=token,
            justificacion="Intento de salida a producción por ejecutivo.",
        )
    assert exc_info.value.code == "FORBIDDEN_STAGE_E5"
    assert "jefatura de implementación" in exc_info.value.message


def test_jefatura_u_i3_puede_marcar_etapa_e5():
    """
    PR-1 / PR-7 / FR-013: U-I3 (jefa_implementacion) puede autorizar y marcar etapa E5.
    """
    set_current_user_id("U-I3")
    token = _token_for("T-010", "ORG-05", "completada", "U-I3")

    res = marcar_tarea(
        tarea_id="T-010",
        nuevo_estado="completada",
        token_confirmacion=token,
        justificacion="Aprobación formal de jefatura para salida a producción.",
    )
    assert res["success"] is True
    assert res["tarea_id"] == "T-010"
    assert res["nuevo_estado"] == "completada"

