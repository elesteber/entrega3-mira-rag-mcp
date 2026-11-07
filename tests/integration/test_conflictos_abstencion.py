"""Conflictos entre fuentes vigentes y abstención, a nivel de RECUPERACIÓN (T047).

Verifica lo que el RAG debe entregar para que el asistente cumpla PR-3 y PR-4:
- conflicto: los fragmentos de ambas fuentes llegan al top-4;
- abstención: una consulta ajena al dominio no trae evidencia (results vacío);
- límite conocido: las preguntas trampa cercanas al corpus SÍ traen fragmentos,
  por lo que la abstención en esos casos la debe decidir el orquestador.

La respuesta final del asistente (presentar ambas posturas, abstenerse con
mensaje) se evalúa de punta a punta en tests/evaluation/eval_goldenset.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.rag.indexer import indexar
from backend.rag.retriever import Recuperador, umbral_defecto

pytestmark = pytest.mark.modelo

GOLDEN = json.loads(
    (Path(__file__).resolve().parents[1] / "evaluation" / "goldenset_cases.json").read_text(encoding="utf-8")
)
CASOS = {c["id"]: c for c in GOLDEN["casos"]}


@pytest.fixture(scope="module")
def recuperador(tmp_path_factory):
    directorio = tmp_path_factory.mktemp("chroma_conflictos")
    indexar("encabezados", persist_dir=directorio)
    return Recuperador("encabezados", persist_dir=directorio)


def _contiene(resultados, esperado) -> bool:
    ancla = " ".join(esperado["ancla"].split())
    return any(
        r["doc_code"] == esperado["doc_code"] and r["version"] == esperado["version"] and ancla in " ".join(r["text"].split())
        for r in resultados
    )


def test_gs19_conflicto_trae_ambas_fuentes(recuperador):
    caso = CASOS["GS-19"]
    resultados = recuperador.buscar(caso["pregunta"], top_k=4, umbral=None)
    for esperado in caso["fragmentos_esperados"]:
        assert _contiene(resultados, esperado), esperado["doc_code"]


@pytest.mark.xfail(reason="Fallo de recuperación conocido (ADR-11): FIC-PLA v1 §1 no llega al top-4", strict=True)
def test_gs18_conflicto_trae_ambas_fuentes(recuperador):
    caso = CASOS["GS-18"]
    resultados = recuperador.buscar(caso["pregunta"], top_k=4, umbral=None)
    assert all(_contiene(resultados, e) for e in caso["fragmentos_esperados"])


def test_gs18_al_menos_una_postura_llega(recuperador):
    caso = CASOS["GS-18"]
    resultados = recuperador.buscar(caso["pregunta"], top_k=4, umbral=None)
    assert any(_contiene(resultados, e) for e in caso["fragmentos_esperados"])


@pytest.mark.parametrize(
    "consulta",
    ["¿Cuál es la capital de Mongolia?", "Receta de pan amasado con chicharrones", "¿Quién ganó el mundial de fútbol de 1962?"],
)
def test_consulta_ajena_al_dominio_no_trae_evidencia(recuperador, consulta):
    assert recuperador.buscar(consulta, top_k=4, umbral=None) == []


@pytest.mark.parametrize("caso_id", ["GS-14", "GS-15", "GS-16", "GS-17"])
def test_trampas_cercanas_al_corpus_superan_el_umbral(recuperador, caso_id):
    """Documenta el límite: el umbral no basta para abstenerse en preguntas sin respuesta del dominio."""
    resultados = recuperador.buscar(CASOS[caso_id]["pregunta"], top_k=4, umbral=None)
    assert resultados, f"{caso_id} quedó bajo el umbral {umbral_defecto()}: revisar ADR-11"
