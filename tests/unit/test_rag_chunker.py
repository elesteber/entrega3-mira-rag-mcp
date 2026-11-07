"""Pruebas de lectura de metadatos y fragmentación del corpus CU-3 (sin modelo ni ChromaDB)."""

from __future__ import annotations

import re

import pytest

from backend.rag.indexer import (
    dividir_secciones,
    fragmentar,
    fragmentar_por_encabezados,
    fragmentar_tamano_fijo,
    leer_corpus,
)
from backend.rag.lexico import BM25, fusion_rrf, tokenizar


@pytest.fixture(scope="module")
def docs():
    return {f"{d.doc_code}-{d.version}": d for d in leer_corpus()}


def test_corpus_tiene_los_cinco_documentos_del_kit(docs):
    assert set(docs) == {"FIC-PLA-v1.0", "GUI-INC-v1.0", "GUI-INC-v2.0", "POL-FOR-v1.0", "REQ-INT-v2.0"}


def test_metadatos_de_vigencia(docs):
    assert docs["GUI-INC-v1.0"].status == "derogada"
    assert docs["GUI-INC-v1.0"].vigencia.startswith("1 de noviembre de 2025")
    for clave in ("GUI-INC-v2.0", "FIC-PLA-v1.0", "POL-FOR-v1.0", "REQ-INT-v2.0"):
        assert docs[clave].status == "vigente"
        assert docs[clave].vigencia == "Desde el 1 de septiembre de 2026"
    assert docs["REQ-INT-v2.0"].doc_title == "Requisitos técnicos de integración"


def test_secciones_de_gui_inc_v2(docs):
    secciones = dividir_secciones(docs["GUI-INC-v2.0"])
    assert [(s.numero, s.titulo) for s in secciones] == [
        (0, "Ficha del documento"),
        (1, "Meta"),
        (2, "Etapas"),
        (3, "Criterios de salida a producción"),
        (4, "Permisos"),
    ]


def test_encabezados_ids_deterministas_y_unicos(docs):
    primera = fragmentar(docs.values(), "encabezados")
    segunda = fragmentar(leer_corpus(), "encabezados")
    assert [f.chunk_id for f in primera] == [f.chunk_id for f in segunda]
    assert all(re.fullmatch(r"[A-Z]+-[A-Z]+-V\d+-SEC\d+-P\d+", f.chunk_id) for f in primera)
    assert len(primera) == 24


def test_encabezados_separa_plantillas_de_fic_pla(docs):
    fragmentos = fragmentar_por_encabezados(docs["FIC-PLA-v1.0"])
    sec2 = [f for f in fragmentos if f.section.startswith("§2")]
    assert [f.section for f in sec2] == ["§2 (PLA-REM)", "§2 (PLA-SIN)", "§2 (PLA-CTA)", "§2 (PLA-ADM)"]
    adm = sec2[-1]
    assert adm.chunk_id == "FIC-PLA-V1-SEC2-P4"
    assert adm.text.startswith("## 2. Plantillas disponibles")  # conserva el contexto de la sección
    assert "aprobación 85" in adm.text and "PLA-CTA" not in adm.text


def test_criterios_de_salida_quedan_en_un_solo_fragmento(docs):
    sec3 = [f for f in fragmentar_por_encabezados(docs["GUI-INC-v2.0"]) if f.section == "§3"]
    assert len(sec3) == 1 and sec3[0].chunk_id == "GUI-INC-V2-SEC3-P1"
    for n in range(1, 7):
        assert f"\n{n}. " in sec3[0].text


def test_metadatos_planos_para_chromadb(docs):
    fragmento = fragmentar_por_encabezados(docs["GUI-INC-v1.0"])[0]
    meta = fragmento.metadatos()
    assert "text" not in meta
    assert meta["status"] == "derogada" and meta["origin"] == "kit_cu3"
    assert all(isinstance(v, str) for v in meta.values())


def test_tamano_fijo_respeta_tamano_y_solape(docs):
    doc = docs["GUI-INC-v2.0"]
    fragmentos = fragmentar_tamano_fijo(doc, tamano=50, solape=10)
    palabras = [f.text.split() for f in fragmentos]
    assert all(len(p) <= 50 for p in palabras)
    for anterior, siguiente in zip(palabras, palabras[1:]):
        assert anterior[-10:] == siguiente[:10]
    total = sum(len(s.texto.split()) for s in dividir_secciones(doc))
    assert len(palabras[0]) + sum(len(p) - 10 for p in palabras[1:]) == total


def test_tamano_fijo_rechaza_solape_invalido(docs):
    with pytest.raises(ValueError):
        fragmentar_tamano_fijo(docs["POL-FOR-v1.0"], tamano=10, solape=10)


def test_estrategia_desconocida(docs):
    with pytest.raises(ValueError):
        fragmentar(docs.values(), "semantica")


def test_tokenizar_quita_tildes_y_palabras_vacias():
    assert tokenizar("¿Qué módulos incluye la plantilla PLA-CTA?") == ["modulos", "incluye", "plantilla", "pla", "cta"]


def test_bm25_prefiere_coincidencia_literal():
    bm25 = BM25(["plantilla de apertura de cuenta", "guía de incorporación", "límite de llamadas por minuto"])
    puntajes = bm25.puntajes("apertura de cuenta")
    assert puntajes[0] > 0 and puntajes[1] == 0 and puntajes[2] == 0


def test_fusion_rrf_combina_rankings():
    assert fusion_rrf([["a", "b", "c"], ["c", "a"]]) == ["a", "c", "b"]
