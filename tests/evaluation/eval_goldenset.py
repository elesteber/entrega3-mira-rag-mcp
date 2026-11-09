"""Evaluación de punta a punta del asistente contra el golden set (T062).

Hace cada pregunta del golden set a ``POST /api/chat`` (contracts/api-rest.yaml)
con una sesión de demostración y mide:

- Precisión de cita (automática): proporción de citas emitidas que son reales y
  exactas (chunk_id existente, metadatos y extracto literal; backend/rag/citas.py).
- Cita del fragmento esperado: en preguntas con respuesta, si alguna cita apunta
  al fragmento del golden set.
- Abstención correcta: preguntas sin respuesta con ``evidence_status=ABSTENCION``,
  y abstenciones indebidas en preguntas con respuesta.
- Manejo de conflicto y vigencia (pauta §7.1).
- Trazas MCP en el caso que requiere datos (PR-5).

Cada caso fallido se clasifica como fallo de RECUPERACIÓN (el fragmento esperado
no estaba en el top-4 del RAG) o de GENERACIÓN (estaba, pero la respuesta falló).
La fidelidad y si la cita respalda la afirmación requieren juicio humano: se
genera una planilla CSV para completarla a mano (pauta §7.2).

Uso (con el backend levantado):
    uv run python -m tests.evaluation.eval_goldenset --api http://localhost:8000/api
Si la API no responde, termina con error y no escribe resultados.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from backend.rag.citas import indice_de_fragmentos, validar_cita
from backend.rag.indexer import RAIZ_REPO
from tests.evaluation.eval_recuperacion import es_acierto, normalizar

GOLDEN_SET = RAIZ_REPO / "tests" / "evaluation" / "goldenset_cases.json"
DIR_RESULTADOS = RAIZ_REPO / "tests" / "evaluation" / "resultados"
API_DEFECTO = os.environ.get("MIRA_API_URL", "http://localhost:8000/api")
K_RECUPERACION = 4


class ApiNoDisponible(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Cliente HTTP mínimo
# ---------------------------------------------------------------------------


def _post(url: str, cuerpo: dict, token: str | None = None, timeout: float = 120) -> dict:
    datos = json.dumps(cuerpo).encode("utf-8")
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detalle = err.read().decode("utf-8", errors="replace")[:300]
        raise ApiNoDisponible(f"{url} respondió {err.code}: {detalle}") from err
    except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
        raise ApiNoDisponible(f"No se pudo contactar {url}: {err}") from err


def abrir_sesion(api: str, usuario: str) -> str:
    return _post(f"{api}/session/switch", {"user_id": usuario})["session_token"]


def preguntar(api: str, token: str, pregunta: str) -> tuple[dict, float]:
    inicio = time.perf_counter()
    respuesta = _post(f"{api}/chat", {"message": pregunta}, token=token)
    return respuesta, round((time.perf_counter() - inicio) * 1000, 1)


# ---------------------------------------------------------------------------
# Evaluación de un caso (funciones puras, probadas en tests/unit)
# ---------------------------------------------------------------------------


def _fragmento_de_cita(cita: dict) -> dict | None:
    fragmento = indice_de_fragmentos().get(cita.get("chunk_id", ""))
    if fragmento is None:
        return None
    return {"doc_code": fragmento.doc_code, "version": fragmento.version, "text": fragmento.text}


def cita_esperada_presente(citas: list[dict], esperado: dict) -> bool:
    """Alguna cita VÁLIDA (extracto literal y metadatos exactos) apunta al fragmento esperado."""
    return any(
        (f := _fragmento_de_cita(c)) and es_acierto(f, esperado) and not validar_cita(c) for c in citas
    )


def evaluar_caso(caso: dict, respuesta: dict, rangos_recuperacion: list[int | None]) -> dict[str, Any]:
    """Juzga automáticamente una respuesta del asistente para un caso del golden set."""
    citas = respuesta.get("citations") or []
    estado = respuesta.get("evidence_status")
    texto = normalizar(respuesta.get("answer", "")).lower()
    trazas = [t.get("tool_name") for t in respuesta.get("mcp_traces") or []]
    problemas_citas = {c.get("chunk_id"): validar_cita(c) for c in citas}
    citas_validas = sum(not p for p in problemas_citas.values())
    esperados = caso["fragmentos_esperados"]
    presentes = [cita_esperada_presente(citas, e) for e in esperados]

    tipo = caso["tipo"]
    if tipo == "sin_respuesta":
        aciertos = {"se_abstiene": estado == "ABSTENCION"}
    elif tipo == "con_respuesta":
        aciertos = {"no_se_abstiene": estado != "ABSTENCION", "cita_fragmento_esperado": all(presentes)}
    elif tipo == "conflicto_vigente":
        aciertos = {"marca_conflicto": estado == "CONFLICTO_FUENTES", "cita_ambas_fuentes": all(presentes)}
    elif tipo == "cambio_version":
        aciertos = {
            "cita_version_vigente": all(presentes),
            "menciona_derogacion": "derog" in texto,
            "no_cita_derogada_como_vigente": not any(
                (f := indice_de_fragmentos().get(c.get("chunk_id", ""))) and f.status == "derogada" and c.get("status") != "derogada"
                for c in citas
            ),
        }
    elif tipo == "conflicto_documento_datos":
        aciertos = {
            "marca_conflicto": estado == "CONFLICTO_FUENTES",
            "usa_mcp": any(t in {"listar_plantillas"} for t in trazas),
            "expone_ambas_cifras": "85" in texto and "80" in texto,
            "cita_ficha": all(presentes),
        }
    else:
        raise ValueError(f"Tipo desconocido: {tipo}")
    aciertos["todas_las_citas_verificables"] = citas_validas == len(citas)  # PR-2: ninguna cita inventada

    correcto = all(aciertos.values())
    recuperado = all(r is not None and r <= K_RECUPERACION for r in rangos_recuperacion) if esperados else True
    if correcto:
        clase = None
    elif esperados and not recuperado:
        clase = "recuperacion"
    else:
        clase = "generacion"

    return {
        "id": caso["id"],
        "tipo": tipo,
        "evidence_status": estado,
        "correcto": correcto,
        "aciertos": aciertos,
        "clase_fallo": clase,
        "rangos_recuperacion": rangos_recuperacion,
        "citas_emitidas": len(citas),
        "citas_validas": citas_validas,
        "problemas_citas": {k: v for k, v in problemas_citas.items() if v},
        "herramientas": trazas,
    }


def resumir(evaluaciones: list[dict]) -> dict[str, Any]:
    def proporcion(filtro, condicion):
        casos = [e for e in evaluaciones if filtro(e)]
        return (round(sum(condicion(e) for e in casos) / len(casos), 4), len(casos)) if casos else (None, 0)

    emitidas = sum(e["citas_emitidas"] for e in evaluaciones)
    validas = sum(e["citas_validas"] for e in evaluaciones)
    return {
        "exactitud_global": proporcion(lambda e: True, lambda e: e["correcto"]),
        "precision_cita_automatica": round(validas / emitidas, 4) if emitidas else None,
        "citas_emitidas": emitidas,
        "cita_fragmento_esperado": proporcion(
            lambda e: e["tipo"] == "con_respuesta", lambda e: e["aciertos"]["cita_fragmento_esperado"]
        ),
        "abstencion_correcta": proporcion(lambda e: e["tipo"] == "sin_respuesta", lambda e: e["aciertos"]["se_abstiene"]),
        "abstencion_indebida": proporcion(
            lambda e: e["tipo"] == "con_respuesta", lambda e: not e["aciertos"]["no_se_abstiene"]
        ),
        "conflicto_y_vigencia": proporcion(
            lambda e: e["tipo"] in {"conflicto_vigente", "cambio_version"}, lambda e: e["correcto"]
        ),
        "fallos_por_clase": {
            clase: sum(e["clase_fallo"] == clase for e in evaluaciones) for clase in ("recuperacion", "generacion")
        },
    }


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------


def rangos_por_caso(casos: list[dict]) -> dict[str, list[int | None]]:
    """Posición del fragmento esperado en el top-k del RAG local (para clasificar fallos)."""
    from backend.rag.retriever import Recuperador
    from tests.evaluation.eval_recuperacion import rango_de

    recuperador = Recuperador()
    salida = {}
    for caso in casos:
        resultados = recuperador.buscar(caso["pregunta"], top_k=10, umbral=0.0) if caso["fragmentos_esperados"] else []
        salida[caso["id"]] = [rango_de(resultados, e) for e in caso["fragmentos_esperados"]]
    return salida


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluación de punta a punta contra el golden set CU-3.")
    parser.add_argument("--api", default=API_DEFECTO, help="URL base de la API (por defecto MIRA_API_URL)")
    parser.add_argument("--usuario", default="U-I3", help="usuario de la sesión demo (U-I3 ve todas las organizaciones)")
    parser.add_argument("--casos", nargs="*", help="IDs a evaluar (por defecto todos)")
    parser.add_argument("--sin-guardar", action="store_true")
    args = parser.parse_args(argv)

    golden = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))
    casos = [c for c in golden["casos"] if not args.casos or c["id"] in args.casos]

    try:
        token = abrir_sesion(args.api, args.usuario)
    except ApiNoDisponible as err:
        print(f"[ERROR] {err}\nLevante el backend (T020) antes de evaluar. No se generan resultados.")
        sys.exit(2)

    rangos = rangos_por_caso(casos)
    evaluaciones, filas_manual, latencias = [], [], []
    for caso in casos:
        try:
            respuesta, ms = preguntar(args.api, token, caso["pregunta"])
        except ApiNoDisponible as err:
            print(f"[ERROR] {caso['id']}: {err}. Se detiene la corrida; no se guardan resultados parciales.")
            sys.exit(2)
        latencias.append(ms)
        evaluacion = evaluar_caso(caso, respuesta, rangos[caso["id"]])
        evaluacion["latencia_ms"] = ms
        evaluaciones.append(evaluacion)
        marca = "OK " if evaluacion["correcto"] else f"FALLA ({evaluacion['clase_fallo']})"
        print(f"{caso['id']} {caso['tipo']:<26} {marca}  {evaluacion['evidence_status']}  {ms} ms")
        filas_manual.append({
            "id": caso["id"],
            "tipo": caso["tipo"],
            "pregunta": caso["pregunta"],
            "respuesta_esperada": caso["respuesta_esperada"],
            "respuesta_asistente": respuesta.get("answer", ""),
            "citas": "; ".join(f"{c.get('chunk_id')}: {c.get('excerpt', '')[:120]}" for c in respuesta.get("citations") or []),
            "fidelidad_todas_las_afirmaciones_respaldadas (si/no)": "",
            "citas_que_respaldan / citas_emitidas": "",
            "notas_revisor": "",
        })

    resumen = resumir(evaluaciones)
    resumen["latencia_ms"] = {"mediana": statistics.median(latencias), "max": max(latencias)} if latencias else None
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    if args.sin_guardar:
        return

    DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = DIR_RESULTADOS / f"goldenset_{marca}"
    salida = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "api": args.api,
        "usuario": args.usuario,
        "golden_set_version": golden["version_golden_set"],
        "resumen": resumen,
        "casos": evaluaciones,
    }
    base.with_suffix(".json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(f"{base}_revision_manual.csv", "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas_manual[0]))
        escritor.writeheader()
        escritor.writerows(filas_manual)
    print(f"\nResultados: {base.relative_to(RAIZ_REPO)}.json y planilla {base.name}_revision_manual.csv")


if __name__ == "__main__":
    main()
