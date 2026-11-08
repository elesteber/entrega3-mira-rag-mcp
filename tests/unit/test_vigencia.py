"""Recuperación con filtros de vigencia y detección de normas derogadas (T046, PR-4).

La primera parte no necesita el modelo; la segunda indexa en un directorio
temporal y consulta de verdad (marcador ``modelo``).
"""

from __future__ import annotations

import pytest

from backend.rag.indexer import fragmentar, indexar, leer_corpus
from backend.rag.retriever import Recuperador

PREGUNTAS_VERSION = [
    "¿Cuánto tiempo toma la incorporación completa de una organización según la guía?",
    "¿Quién autoriza que una organización pase a producción?",
]


# --- Metadatos (sin modelo) -------------------------------------------------


def test_solo_gui_inc_v1_es_derogada():
    derogadas = {(d.doc_code, d.version) for d in leer_corpus() if d.status == "derogada"}
    assert derogadas == {("GUI-INC", "v1.0")}


def test_todos_los_fragmentos_de_v1_heredan_estado_derogada():
    fragmentos = fragmentar(leer_corpus(), "encabezados")
    v1 = [f for f in fragmentos if f.doc_code == "GUI-INC" and f.version == "v1.0"]
    assert v1 and all(f.status == "derogada" for f in v1)
    assert all(f.vigencia.endswith("31 de agosto de 2026") for f in v1)
    assert all(f.status == "vigente" for f in fragmentos if f not in v1)


# --- Recuperación real (con modelo) -----------------------------------------


@pytest.fixture(scope="module")
def recuperador(tmp_path_factory):
    directorio = tmp_path_factory.mktemp("chroma_vigencia")
    indexar("encabezados", persist_dir=directorio)
    return Recuperador("encabezados", persist_dir=directorio)


@pytest.mark.modelo
@pytest.mark.parametrize("pregunta", PREGUNTAS_VERSION)
def test_filtro_vigente_nunca_devuelve_derogadas(recuperador, pregunta):
    resultados = recuperador.buscar(pregunta, top_k=10, filtro_vigencia="vigente")
    assert resultados
    assert all(r["status"] == "vigente" for r in resultados)
    assert not any(r["chunk_id"].startswith("GUI-INC-V1") for r in resultados)


@pytest.mark.modelo
@pytest.mark.parametrize(
    "pregunta, vigente, derogada",
    [
        (PREGUNTAS_VERSION[0], "GUI-INC-V2-SEC1-P1", "GUI-INC-V1-SEC1-P1"),
        (PREGUNTAS_VERSION[1], "GUI-INC-V2-SEC4-P1", "GUI-INC-V1-SEC2-P1"),
    ],
)
def test_filtro_todas_trae_vigente_y_derogada_marcadas(recuperador, pregunta, vigente, derogada):
    resultados = {r["chunk_id"]: r for r in recuperador.buscar(pregunta, top_k=6, filtro_vigencia="todas")}
    assert vigente in resultados and resultados[vigente]["status"] == "vigente"
    assert derogada in resultados and resultados[derogada]["status"] == "derogada"
    assert "31 de agosto de 2026" in resultados[derogada]["vigencia"]
