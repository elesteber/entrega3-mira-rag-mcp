"""Lógica de juicio de eval_goldenset (T062) con respuestas simuladas del asistente.

Las respuestas de este archivo son FICTICIAS y solo prueban el evaluador;
no son resultados del sistema.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.evaluation.eval_goldenset import ApiNoDisponible, abrir_sesion, evaluar_caso, resumir

GOLDEN = json.loads((Path(__file__).resolve().parents[1] / "evaluation" / "goldenset_cases.json").read_text(encoding="utf-8"))
CASOS = {c["id"]: c for c in GOLDEN["casos"]}

CITA_GS02 = {
    "chunk_id": "GUI-INC-V2-SEC4-P1", "doc_code": "GUI-INC", "doc_title": "Guía de incorporación de organizaciones",
    "section": "§4", "version": "v2.0", "status": "vigente",
    "excerpt": "Un ejecutivo puede marcar como completadas las tareas de las etapas E0 a E4 de sus organizaciones.",
}


def respuesta(answer="", citations=(), estado="COMPLETA", trazas=()):
    return {"answer": answer, "citations": list(citations), "evidence_status": estado,
            "mcp_traces": [{"tool_name": t, "parameters": {}, "execution_time_ms": 1, "success": True} for t in trazas]}


def test_respuesta_correcta_con_cita_esperada():
    ev = evaluar_caso(CASOS["GS-02"], respuesta("E0 a E4 de sus organizaciones.", [CITA_GS02]), [1])
    assert ev["correcto"] and ev["clase_fallo"] is None and ev["citas_validas"] == 1


def test_cita_inventada_es_fallo_de_generacion_si_el_rag_recupero():
    cita = {**CITA_GS02, "excerpt": "Cualquier ejecutivo marca cualquier tarea."}
    ev = evaluar_caso(CASOS["GS-02"], respuesta("…", [cita]), [1])
    assert not ev["correcto"] and ev["clase_fallo"] == "generacion" and ev["citas_validas"] == 0


def test_fallo_de_recuperacion_si_el_fragmento_no_estaba_en_top4():
    ev = evaluar_caso(CASOS["GS-02"], respuesta("No encuentro.", [], "ABSTENCION"), [None])
    assert ev["clase_fallo"] == "recuperacion"
    assert ev["aciertos"]["no_se_abstiene"] is False


def test_abstencion_correcta_en_pregunta_sin_respuesta():
    ev = evaluar_caso(CASOS["GS-14"], respuesta("El corpus no define tarifas.", [], "ABSTENCION"), [])
    assert ev["correcto"]


def test_conflicto_documento_datos_exige_mcp_y_ambas_cifras():
    cita = {"chunk_id": "FIC-PLA-V1-SEC2-P4", "doc_code": "FIC-PLA", "doc_title": "x", "section": "§2 (PLA-ADM)",
            "version": "v1.0", "status": "vigente", "excerpt": "Umbrales sugeridos: aprobación 85, revisión 60."}
    sin_mcp = evaluar_caso(CASOS["GS-22"], respuesta("La ficha dice 85 y la base 80.", [cita], "CONFLICTO_FUENTES"), [1])
    assert not sin_mcp["correcto"] and not sin_mcp["aciertos"]["usa_mcp"]
    con_mcp = evaluar_caso(
        CASOS["GS-22"], respuesta("La ficha dice 85 y la base 80.", [cita], "CONFLICTO_FUENTES", ["listar_plantillas"]), [1]
    )
    assert con_mcp["correcto"]


def test_resumen_cuenta_clases_de_fallo():
    evs = [
        evaluar_caso(CASOS["GS-02"], respuesta("ok", [CITA_GS02]), [1]),
        evaluar_caso(CASOS["GS-02"], respuesta("", [], "ABSTENCION"), [None]),
        evaluar_caso(CASOS["GS-14"], respuesta("tarifa 5 USD", [], "COMPLETA"), []),
    ]
    r = resumir(evs)
    assert r["fallos_por_clase"] == {"recuperacion": 1, "generacion": 1}
    assert r["abstencion_correcta"] == (0.0, 1)
    assert r["abstencion_indebida"] == (0.5, 2)


def test_api_caida_no_genera_resultados():
    with pytest.raises(ApiNoDisponible):
        abrir_sesion("http://127.0.0.1:9", "U-I3")
