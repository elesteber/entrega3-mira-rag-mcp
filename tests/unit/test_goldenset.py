"""Validación estructural del golden set del CU-3.

No ejecuta el pipeline RAG ni el modelo: solo comprueba que el golden set
cumple la composición de la pauta (§7.1) y que cada fragmento esperado existe
literalmente, una sola vez, en el documento indicado del corpus del kit.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GOLDEN_SET = RAIZ / "tests" / "evaluation" / "goldenset_cases.json"
CORPUS = RAIZ / "archivos-base" / "Kit_Entrega_3_MIRA" / "CU-3_incorporacion_organizaciones" / "corpus"

TIPOS_VALIDOS = {
    "con_respuesta",
    "sin_respuesta",
    "conflicto_vigente",
    "cambio_version",
    "conflicto_documento_datos",
}
CAMPOS_OBLIGATORIOS = {"id", "tipo", "pregunta", "debe_responder", "fragmentos_esperados", "respuesta_esperada"}

# Archivo del corpus para cada (doc_code, version).
ARCHIVOS = {
    ("GUI-INC", "v1.0"): "GUI-INC_v1_derogada.md",
    ("GUI-INC", "v2.0"): "GUI-INC_v2_vigente.md",
    ("FIC-PLA", "v1.0"): "FIC-PLA_fichas_plantillas.md",
    ("POL-FOR", "v1.0"): "POL-FOR_formularios_propios.md",
    ("REQ-INT", "v2.0"): "REQ-INT_requisitos_integracion.md",
}


def normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(GOLDEN_SET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus() -> dict[tuple[str, str], str]:
    return {clave: normalizar((CORPUS / nombre).read_text(encoding="utf-8")) for clave, nombre in ARCHIVOS.items()}


def test_composicion_minima(golden):
    conteo = Counter(c["tipo"] for c in golden["casos"])
    for tipo, minimo in golden["composicion_minima"].items():
        assert conteo[tipo] >= minimo, f"{tipo}: {conteo[tipo]} < {minimo}"
    nucleo = sum(conteo[t] for t in golden["composicion_minima"])
    assert nucleo >= 20


def test_campos_e_ids(golden):
    ids = [c["id"] for c in golden["casos"]]
    assert len(ids) == len(set(ids)), "IDs duplicados"
    for caso in golden["casos"]:
        faltan = CAMPOS_OBLIGATORIOS - caso.keys()
        assert not faltan, f"{caso['id']} sin {faltan}"
        assert caso["tipo"] in TIPOS_VALIDOS
        assert caso["pregunta"].strip().endswith("?")


def test_debe_responder_coherente_con_tipo(golden):
    for caso in golden["casos"]:
        if caso["tipo"] == "sin_respuesta":
            assert caso["debe_responder"] is False
            assert caso["fragmentos_esperados"] == []
        else:
            assert caso["debe_responder"] is True
            assert caso["fragmentos_esperados"], f"{caso['id']} sin fragmento esperado"


def test_conflictos_citan_dos_documentos(golden):
    for caso in golden["casos"]:
        if caso["tipo"] == "conflicto_vigente":
            docs = {f["doc_code"] for f in caso["fragmentos_esperados"]}
            assert len(docs) >= 2, f"{caso['id']} debe contrastar dos documentos vigentes"


def test_cambio_version_incluye_derogada(golden):
    for caso in golden["casos"]:
        if caso["tipo"] == "cambio_version":
            assert caso.get("fragmentos_derogados_relacionados"), caso["id"]


def _todos_los_fragmentos(golden):
    for caso in golden["casos"]:
        for frag in caso["fragmentos_esperados"] + caso.get("fragmentos_derogados_relacionados", []):
            yield caso["id"], frag


def test_anclas_existen_una_vez_en_su_documento(golden, corpus):
    for caso_id, frag in _todos_los_fragmentos(golden):
        clave = (frag["doc_code"], frag["version"])
        assert clave in corpus, f"{caso_id}: documento desconocido {clave}"
        ancla = normalizar(frag["ancla"])
        apariciones = corpus[clave].count(ancla)
        assert apariciones == 1, f"{caso_id}: ancla aparece {apariciones} veces en {clave}: {ancla!r}"


def test_anclas_no_ambiguas_entre_documentos(golden, corpus):
    for caso_id, frag in _todos_los_fragmentos(golden):
        ancla = normalizar(frag["ancla"])
        en_otros = [c for c, texto in corpus.items() if c != (frag["doc_code"], frag["version"]) and ancla in texto]
        assert not en_otros, f"{caso_id}: ancla también aparece en {en_otros}"
