"""Pruebas de integración del RAG: indexación real + buscar_reglas según el contrato MCP.

Cargan el modelo de embeddings (la primera vez lo descarga). Se pueden omitir con
``pytest -m "not modelo"``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.rag import retriever
from backend.rag.indexer import indexar

pytestmark = pytest.mark.modelo

CONTRATO = (
    Path(__file__).resolve().parents[2]
    / "specs" / "001-incorporacion-organizaciones" / "contracts" / "mcp-tools.json"
)
CAMPOS = {"chunk_id", "doc_code", "doc_title", "section", "version", "status", "text", "similarity_score"}


@pytest.fixture(scope="module")
def indice(tmp_path_factory):
    directorio = tmp_path_factory.mktemp("chroma")
    resumen = indexar("encabezados", persist_dir=directorio)
    mp = pytest.MonkeyPatch()
    mp.setattr(retriever, "_RECUPERADORES", {"encabezados": retriever.Recuperador("encabezados", persist_dir=directorio)})
    yield {"dir": directorio, "resumen": resumen}
    mp.undo()


def test_indexacion_reproducible(indice, tmp_path):
    # Se reindexa en otro directorio: reindexar en el mismo invalida la colección
    # abierta por un Recuperador en ejecución (hay que reiniciar el servidor MCP).
    segunda = indexar("encabezados", persist_dir=tmp_path)
    assert segunda["chunk_ids"] == indice["resumen"]["chunk_ids"]
    assert segunda["huella_corpus_sha256"] == indice["resumen"]["huella_corpus_sha256"]
    assert indice["resumen"]["fragmentos_truncados"] == 0


def test_respuesta_cumple_contrato(indice):
    salida = retriever.buscar_reglas("¿Cuáles son los criterios de salida a producción?")
    assert set(salida) == {"total_found", "results"}
    assert salida["total_found"] == len(salida["results"]) <= 4
    for fragmento in salida["results"]:
        assert set(fragmento) == CAMPOS
        assert fragmento["status"] == "vigente"
    assert salida["results"][0]["chunk_id"] == "GUI-INC-V2-SEC3-P1"


def test_contrato_publicado_coincide_si_existe():
    if not CONTRATO.exists():
        pytest.skip("contracts/mcp-tools.json aún no está en esta rama")
    herramientas = {h["name"]: h for h in json.loads(CONTRATO.read_text(encoding="utf-8"))["tools"]}
    item = herramientas["buscar_reglas"]["returns"]["properties"]["results"]["items"]
    assert set(item["required"]) == CAMPOS


def test_filtro_vigente_excluye_derogada(indice):
    pregunta = "¿Cuánto toma la incorporación completa desde la firma?"
    vigentes = retriever.buscar_reglas(pregunta, top_k=10)
    assert all(f["version"] != "v1.0" or f["doc_code"] != "GUI-INC" for f in vigentes["results"])
    todas = retriever.buscar_reglas(pregunta, top_k=10, filtro_vigencia="todas")
    assert any(f["status"] == "derogada" for f in todas["results"])


def test_busqueda_hibrida_recupera_codigo_de_plantilla(indice):
    salida = retriever.buscar_reglas("¿Qué módulos incluye la plantilla de apertura de cuenta?")
    assert "FIC-PLA-V1-SEC2-P3" in [f["chunk_id"] for f in salida["results"]]


@pytest.mark.parametrize("argumentos", [{"top_k": 0}, {"top_k": 11}, {"filtro_vigencia": "derogada"}])
def test_parametros_invalidos(indice, argumentos):
    with pytest.raises(ValueError):
        retriever.buscar_reglas("criterios", **argumentos)


def test_consulta_vacia(indice):
    with pytest.raises(ValueError):
        retriever.buscar_reglas("   ")
