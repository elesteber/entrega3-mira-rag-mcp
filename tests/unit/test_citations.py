"""Validación de citas con chunk_id (T029, PR-2). No requiere modelo ni ChromaDB."""

from __future__ import annotations

from backend.rag.citas import indice_de_fragmentos, validar_cita, validar_citas

CITA_OK = {
    "chunk_id": "GUI-INC-V2-SEC4-P1",
    "doc_code": "GUI-INC",
    "doc_title": "Guía de incorporación de organizaciones",
    "section": "§4",
    "version": "v2.0",
    "status": "vigente",
    "excerpt": "La tarea de salida a producción (E5) solo la marca el jefe de implementación.",
}


def test_todos_los_fragmentos_tienen_chunk_id_y_metadatos_de_cita():
    indice = indice_de_fragmentos()
    assert len(indice) == 24
    for chunk_id, fragmento in indice.items():
        assert chunk_id == fragmento.chunk_id
        assert fragmento.doc_code and fragmento.section.startswith("§")
        assert fragmento.version in {"v1.0", "v2.0"}
        assert fragmento.status in {"vigente", "derogada"}


def test_cita_valida():
    assert validar_cita(CITA_OK) == []


def test_tolera_comillas_elipsis_y_vinetas():
    cita = {
        **CITA_OK,
        "chunk_id": "FIC-PLA-V1-SEC2-P4",
        "doc_code": "FIC-PLA",
        "section": "§2 (PLA-ADM)",
        "version": "v1.0",
        "excerpt": "«Industria: salud. … Umbrales sugeridos: aprobación 85, revisión 60.»",
    }
    assert validar_cita(cita) == []


def test_chunk_id_inexistente():
    assert validar_cita({**CITA_OK, "chunk_id": "GUI-INC-V3-SEC9-P1"})[0].startswith("chunk_id inexistente")


def test_version_o_seccion_incorrecta():
    problemas = validar_cita({**CITA_OK, "version": "v1.0", "section": "§3"})
    assert any("version" in p for p in problemas)
    assert any("section" in p for p in problemas)


def test_derogada_citada_como_vigente():
    cita = {
        **CITA_OK,
        "chunk_id": "GUI-INC-V1-SEC2-P1",
        "section": "§2",
        "version": "v1.0",
        "excerpt": "La organización pasa a producción cuando el ingeniero a cargo da su conformidad.",
    }
    assert any("status" in p for p in validar_cita(cita))
    assert validar_cita({**cita, "status": "derogada"}) == []


def test_extracto_inventado_o_alterado():
    problemas = validar_cita({**CITA_OK, "excerpt": "La tarea E5 la puede marcar cualquier ejecutivo."})
    assert any("no aparece" in p for p in problemas)
    assert validar_cita({**CITA_OK, "excerpt": "  "}) == ["excerpt vacío"]


def test_resumen_de_precision():
    resumen = validar_citas([CITA_OK, {**CITA_OK, "excerpt": "texto inventado"}])
    assert (resumen["total"], resumen["validas"], resumen["proporcion_validas"]) == (2, 1, 0.5)
