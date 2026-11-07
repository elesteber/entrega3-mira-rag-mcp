"""
Pruebas unitarias para listar_plantillas (US3, T030).
Valida catálogo de plantillas, esquema contractual y preservación de discrepancia PLA-ADM (80% en SQLite vs 85% en ficha) (PR-4).
"""

from __future__ import annotations

import os
import pytest

from backend.data.init_db import init_database
from backend.mcp.access_control import set_current_user_id
from backend.mcp.tools.sql_tools import listar_plantillas


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Inicializa una base de datos limpia para cada prueba unitaria."""
    test_db = tmp_path / "test_mira_plantillas.db"
    init_database(db_path=test_db, quiet=True)
    os.environ["SQLITE_DB_PATH"] = str(test_db)
    yield
    set_current_user_id(None)


def test_listar_plantillas_todas():
    """
    US3 / T030: Consulta global retorna las 4 plantillas del kit con esquema completo.
    """
    result = listar_plantillas()
    plantillas = result["plantillas"]
    assert len(plantillas) == 4

    p_ids = [p["plantilla_id"] for p in plantillas]
    assert p_ids == ["PLA-ADM", "PLA-CTA", "PLA-REM", "PLA-SIN"]  # Ordenados por plantilla_id

    for p in plantillas:
        assert "plantilla_id" in p
        assert "nombre" in p
        assert "industria" in p
        assert "modulos" in p
        assert isinstance(p["umbral_aprobacion_sugerido"], int)
        assert isinstance(p["umbral_revision_sugerido"], int)
        assert isinstance(p["dias_adaptacion_estimados"], int)
        assert p["requiere_autorizacion_biometrica"] in ("sí", "no")


def test_listar_plantillas_preserva_discrepancia_pla_adm():
    """
    PR-4 / D3: La plantilla PLA-ADM tiene registrado umbral de aprobación 80 en SQLite,
    mientras que la ficha técnica documental FIC-PLA §2 estipula 85.
    La herramienta relacional debe reflejar fielmente el dato de la base de datos (80).
    """
    result = listar_plantillas(plantilla_id="PLA-ADM")
    plantillas = result["plantillas"]
    assert len(plantillas) == 1

    p_adm = plantillas[0]
    assert p_adm["plantilla_id"] == "PLA-ADM"
    assert p_adm["nombre"] == "Admisión clínica"
    assert p_adm["industria"] == "salud"
    assert p_adm["umbral_aprobacion_sugerido"] == 80  # Discrepancia con FIC-PLA (85)
    assert p_adm["requiere_autorizacion_biometrica"] == "sí"


def test_listar_plantillas_pla_cta_requiere_biometria():
    """
    PLA-CTA (Banca) requiere autorización biométrica según el kit oficial.
    """
    result = listar_plantillas(plantilla_id="PLA-CTA")
    p_cta = result["plantillas"][0]
    assert p_cta["plantilla_id"] == "PLA-CTA"
    assert p_cta["requiere_autorizacion_biometrica"] == "sí"
    assert p_cta["umbral_aprobacion_sugerido"] == 90


def test_listar_plantillas_accesible_para_rol_comercial():
    """
    PR-7 / FR-017: El rol comercial (U-I4 Pablo Reyes) tiene autorización explícita
    para consultar el catálogo de plantillas estándar.
    """
    set_current_user_id("U-I4")
    result = listar_plantillas()
    assert len(result["plantillas"]) == 4
