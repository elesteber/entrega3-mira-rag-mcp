"""
Pruebas unitarias para checklist_organizacion y resolución de v_tareas_estado_efectivo (US2, T024).
Verifica filtros por etapa, progreso porcentual y control RBAC (PR-5, PR-7).
"""

from __future__ import annotations

import os
import pytest

from backend.data.init_db import init_database
from backend.mcp.access_control import McpSecurityError, set_current_user_id
from backend.mcp.tools.sql_tools import checklist_organizacion


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Inicializa una base de datos limpia para cada prueba unitaria."""
    test_db = tmp_path / "test_mira_checklist.db"
    init_database(db_path=test_db, quiet=True)
    os.environ["SQLITE_DB_PATH"] = str(test_db)
    yield
    set_current_user_id(None)


def test_checklist_org05_completo_para_ejecutivo_asignado():
    """
    US2 / T024: U-I1 consulta ORG-05.
    Datos reales del Excel CU-3_datos.xlsx:
    10 tareas efectivas (6 completadas: T-001..T-005, T-009; 1 en curso: T-006; 3 pendientes: T-007, T-008, T-010).
    Progreso real: 60.0% de avance.
    """
    set_current_user_id("U-I1")
    result = checklist_organizacion("ORG-05")

    assert result["org_id"] == "ORG-05"
    assert result["organizacion_nombre"] == "Mutual de Seguros Puerto Claro"
    assert result["estado_incorporacion"] == "en_adaptacion"

    resumen = result["resumen_progreso"]
    assert resumen["total_tareas"] == 10
    assert resumen["completadas"] == 6
    assert resumen["en_curso"] == 1
    assert resumen["pendientes"] == 3
    assert resumen["porcentaje_avance"] == 60.0

    tareas = result["tareas"]
    assert len(tareas) == 10

    # Comprobar tareas específicas
    t001 = next(t for t in tareas if t["tarea_id"] == "T-001")
    assert t001["etapa"] == "E0"
    assert t001["estado"] == "completada"

    t006 = next(t for t in tareas if t["tarea_id"] == "T-006")
    assert t006["etapa"] == "E3"
    assert t006["estado"] == "en_curso"

    t008 = next(t for t in tareas if t["tarea_id"] == "T-008")
    assert t008["etapa"] == "E4"
    assert t008["estado"] == "pendiente"
    assert t008["observacion"] is not None
    assert t008["es_dato_confiable"] is False  # Regla 5 / T057


def test_checklist_filtro_por_etapa():
    """
    US2 / T024: Filtrar por etapa E3 en ORG-05 retorna exactamente las 2 tareas de dicha etapa.
    """
    set_current_user_id("U-I1")
    result = checklist_organizacion("ORG-05", etapa="E3")

    tareas = result["tareas"]
    assert len(tareas) == 2
    assert {t["tarea_id"] for t in tareas} == {"T-006", "T-007"}
    assert all(t["etapa"] == "E3" for t in tareas)


def test_checklist_filtro_etapa_e0_todas_completadas():
    """
    US2: Etapa E0 en ORG-05 tiene 2 tareas, ambas completadas.
    """
    set_current_user_id("U-I1")
    result = checklist_organizacion("ORG-05", etapa="E0")

    tareas = result["tareas"]
    assert len(tareas) == 2
    assert all(t["estado"] == "completada" for t in tareas)


def test_checklist_rechazo_organizacion_no_asignada():
    """
    PR-7: U-I1 (asignada a ORG-05 y ORG-07) no puede consultar ORG-06 (asignada a U-I2).
    """
    set_current_user_id("U-I1")
    with pytest.raises(McpSecurityError) as exc_info:
        checklist_organizacion("ORG-06")
    assert exc_info.value.code == "FORBIDDEN_ORGANIZATION_ACCESS"


def test_checklist_jefatura_tiene_acceso_global():
    """
    PR-7: U-I3 (jefe_implementacion) puede consultar cualquier organización.
    """
    set_current_user_id("U-I3")
    res5 = checklist_organizacion("ORG-05")
    assert res5["org_id"] == "ORG-05"

    res6 = checklist_organizacion("ORG-06")
    assert res6["org_id"] == "ORG-06"


def test_checklist_comercial_bloqueado():
    """
    PR-7: U-I4 (comercial) no puede consultar tareas de organizaciones.
    """
    set_current_user_id("U-I4")
    with pytest.raises(McpSecurityError) as exc_info:
        checklist_organizacion("ORG-05")
    assert exc_info.value.code == "FORBIDDEN_ROLE_ACCESS"
