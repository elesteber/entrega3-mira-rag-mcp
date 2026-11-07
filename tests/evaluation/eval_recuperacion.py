"""Evaluación de la etapa de RECUPERACIÓN del RAG contra el golden set.

No invoca al LLM: mide solo si la búsqueda trae el fragmento esperado
(pauta §7.2, Recall@k a nivel de fragmento). Las métricas de generación
(precisión de cita, fidelidad, abstención del asistente) requieren el sistema
completo y se medirán en ``eval_goldenset.py``.

Para el experimento de fragmentación (criterio C3) indexa cada configuración en
un directorio temporal, sin tocar el índice de trabajo.

Uso:
    uv run python -m tests.evaluation.eval_recuperacion
    uv run python -m tests.evaluation.eval_recuperacion --configs A-128-hibrido --ks 1 4
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from backend.rag.indexer import RAIZ_REPO, indexar, nombre_modelo
from backend.rag.retriever import Recuperador, umbral_defecto

GOLDEN_SET = RAIZ_REPO / "tests" / "evaluation" / "goldenset_cases.json"
DIR_RESULTADOS = RAIZ_REPO / "tests" / "evaluation" / "resultados"
K_MAX = 10


@dataclass(frozen=True)
class Configuracion:
    nombre: str
    estrategia: str
    max_seq_length: int  # tokens al vectorizar; el modelo trae 128 por defecto
    modo: str  # "denso" | "hibrido"
    opciones: dict = field(default_factory=dict)
    descripcion: str = ""


_BASES = [
    ("A-128", "encabezados", 128, {}, "Encabezados Markdown, límite del modelo (128 tokens)"),
    ("A-256", "encabezados", 256, {}, "Encabezados Markdown, límite ampliado a 256 tokens"),
    ("B150-128", "fijo", 128, {"tamano": 150, "solape": 40}, "Fijo 150/40 palabras (~200/50 tokens), 128 tokens"),
    ("B150-256", "fijo", 256, {"tamano": 150, "solape": 40}, "Fijo 150/40 palabras (~200/50 tokens), 256 tokens"),
    ("B60-128", "fijo", 128, {"tamano": 60, "solape": 15}, "Fijo 60/15 palabras (cabe en 128 tokens)"),
]
CONFIGURACIONES = {
    f"{nombre}-{modo}": Configuracion(f"{nombre}-{modo}", estrategia, mx, modo, opciones, f"{desc}, búsqueda {modo}")
    for nombre, estrategia, mx, opciones, desc in _BASES
    for modo in ("denso", "hibrido")
}


def normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def es_acierto(fragmento: dict, esperado: dict) -> bool:
    """Acierto a nivel de fragmento: mismo documento y versión, y contiene el ancla literal."""
    return (
        fragmento["doc_code"] == esperado["doc_code"]
        and fragmento["version"] == esperado["version"]
        and normalizar(esperado["ancla"]) in normalizar(fragmento["text"])
    )


def rango_de(recuperados: list[dict], esperado: dict) -> int | None:
    """Posición (1-indexada) del primer fragmento que acierta, o None."""
    for posicion, fragmento in enumerate(recuperados, start=1):
        if es_acierto(fragmento, esperado):
            return posicion
    return None


def evaluar_configuracion(config: Configuracion, casos: list[dict], ks: list[int]) -> dict:
    with tempfile.TemporaryDirectory(prefix="mira_eval_") as directorio:
        anterior = os.environ.get("EMBEDDING_MAX_SEQ_LENGTH")
        os.environ["EMBEDDING_MAX_SEQ_LENGTH"] = str(config.max_seq_length)
        try:
            resumen = indexar(config.estrategia, persist_dir=directorio, **config.opciones)
            recuperador = Recuperador(config.estrategia, persist_dir=directorio, modo=config.modo)
            detalle = [_evaluar_caso(recuperador, caso) for caso in casos]
        finally:
            if anterior is None:
                os.environ.pop("EMBEDDING_MAX_SEQ_LENGTH", None)
            else:
                os.environ["EMBEDDING_MAX_SEQ_LENGTH"] = anterior

    return {
        "configuracion": config.nombre,
        "descripcion": config.descripcion,
        "estrategia": config.estrategia,
        "modo": config.modo,
        "opciones": config.opciones,
        "max_seq_length": resumen["max_seq_length"],
        "total_fragmentos": resumen["total_fragmentos"],
        "tokens_por_fragmento": resumen["tokens_por_fragmento"],
        "fragmentos_truncados": resumen["fragmentos_truncados"],
        "metricas": _metricas(detalle, ks),
        "detalle": detalle,
    }


def _evaluar_caso(recuperador: Recuperador, caso: dict) -> dict:
    vigentes = recuperador.buscar(caso["pregunta"], top_k=K_MAX, filtro_vigencia="vigente", umbral=0.0)
    salida = {
        "id": caso["id"],
        "tipo": caso["tipo"],
        "similitud_top1": max((f["similarity_score"] for f in vigentes), default=0.0),  # máxima similitud densa
        "top3": [f"{f['chunk_id']} ({f['similarity_score']:.3f})" for f in vigentes[:3]],
        "rangos": [rango_de(vigentes, esp) for esp in caso["fragmentos_esperados"]],
    }
    derogados = caso.get("fragmentos_derogados_relacionados", [])
    if derogados:
        todas = recuperador.buscar(caso["pregunta"], top_k=K_MAX, filtro_vigencia="todas", umbral=0.0)
        salida["rangos_derogados_con_filtro_todas"] = [rango_de(todas, esp) for esp in derogados]
    return salida


def _recall(detalle: list[dict], tipos: set[str], k: int) -> float | None:
    """Recall@k: proporción de fragmentos esperados (de esos tipos) dentro del top-k."""
    rangos = [r for d in detalle if d["tipo"] in tipos for r in d["rangos"]]
    if not rangos:
        return None
    return round(sum(r is not None and r <= k for r in rangos) / len(rangos), 4)


def _metricas(detalle: list[dict], ks: list[int]) -> dict:
    con_respuesta = [d for d in detalle if d["tipo"] == "con_respuesta"]
    rr = [1.0 / d["rangos"][0] if d["rangos"][0] else 0.0 for d in con_respuesta]
    sin_respuesta = [d["similitud_top1"] for d in detalle if d["tipo"] == "sin_respuesta"]
    respondibles = [d["similitud_top1"] for d in detalle if d["tipo"] != "sin_respuesta"]
    version = [d for d in detalle if d["tipo"] == "cambio_version"]
    umbral = umbral_defecto()
    return {
        "abstencion_por_umbral": {
            "umbral": umbral,
            "sin_respuesta_sin_evidencia": (sum(s < umbral for s in sin_respuesta), len(sin_respuesta)),
            "respondibles_sin_evidencia": (sum(s < umbral for s in respondibles), len(respondibles)),
        },
        "recall_con_respuesta": {f"@{k}": _recall(detalle, {"con_respuesta"}, k) for k in ks},
        "recall_conflicto_vigente": {f"@{k}": _recall(detalle, {"conflicto_vigente"}, k) for k in ks},
        "recall_cambio_version": {f"@{k}": _recall(detalle, {"cambio_version"}, k) for k in ks},
        "mrr_con_respuesta": round(statistics.mean(rr), 4) if rr else None,
        "derogada_recuperada_con_filtro_todas@4": (
            sum(all(r is not None and r <= 4 for r in d.get("rangos_derogados_con_filtro_todas", [])) for d in version),
            len(version),
        ),
        "similitud_top1": {
            "respondibles_min": min(respondibles) if respondibles else None,
            "respondibles_promedio": round(statistics.mean(respondibles), 4) if respondibles else None,
            "sin_respuesta_max": max(sin_respuesta) if sin_respuesta else None,
            "sin_respuesta_promedio": round(statistics.mean(sin_respuesta), 4) if sin_respuesta else None,
        },
    }


def _tabla_markdown(resultados: list[dict], ks: list[int]) -> str:
    cab = ["Configuración", "Fragmentos", "Truncados"] + [f"Recall@{k}" for k in ks] + ["MRR", "Conflicto@4", "Versión@4"]
    filas = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for r in resultados:
        m = r["metricas"]
        celdas = [r["configuracion"], str(r["total_fragmentos"]), str(r["fragmentos_truncados"])]
        celdas += [f"{m['recall_con_respuesta'][f'@{k}']:.2f}" for k in ks]
        celdas += [
            f"{m['mrr_con_respuesta']:.2f}",
            f"{m['recall_conflicto_vigente'].get('@4', 0) or 0:.2f}",
            f"{m['recall_cambio_version'].get('@4', 0) or 0:.2f}",
        ]
        filas.append("| " + " | ".join(celdas) + " |")
    return "\n".join(filas)


def _fallos_markdown(resultado: dict, k: int) -> str:
    lineas = []
    for d in resultado["detalle"]:
        if d["tipo"] == "sin_respuesta":
            continue
        fallidos = [i for i, r in enumerate(d["rangos"]) if r is None or r > k]
        if fallidos:
            lineas.append(f"- **{d['id']}** ({d['tipo']}): esperado #{[i + 1 for i in fallidos]} fuera del top-{k}; "
                          f"rangos={d['rangos']}; top-3: {', '.join(d['top3'])}")
    return "\n".join(lineas) or "- Ninguno."


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Recall@k del RAG CU-3 contra el golden set.")
    parser.add_argument("--configs", nargs="+", default=list(CONFIGURACIONES), choices=list(CONFIGURACIONES))
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 3, 4, 5])
    parser.add_argument("--sin-guardar", action="store_true", help="no escribe archivos de resultados")
    args = parser.parse_args(argv)

    if 4 not in args.ks:
        args.ks = sorted({*args.ks, 4})
    golden = json.loads(GOLDEN_SET.read_text(encoding="utf-8"))
    casos = [c for c in golden["casos"] if not c.get("requiere_mcp")]

    resultados = [evaluar_configuracion(CONFIGURACIONES[n], casos, args.ks) for n in args.configs]

    tabla = _tabla_markdown(resultados, args.ks)
    print(tabla)
    for r in resultados:
        print(f"\n[{r['configuracion']}] similitud top-1: {r['metricas']['similitud_top1']}")
        print(f"[{r['configuracion']}] abstención por umbral: {r['metricas']['abstencion_por_umbral']}")
        print(f"[{r['configuracion']}] fallos @4:\n{_fallos_markdown(r, 4)}")

    if args.sin_guardar:
        return
    DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    salida = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "golden_set_version": golden["version_golden_set"],
        "modelo": nombre_modelo(),
        "casos_evaluados": len(casos),
        "ks": args.ks,
        "resultados": resultados,
    }
    ruta_json = DIR_RESULTADOS / f"recuperacion_{marca}.json"
    ruta_json.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    informe = [f"# Evaluación de recuperación · {salida['fecha']}", "",
               f"Golden set v{salida['golden_set_version']} · {len(casos)} casos sin MCP · modelo `{salida['modelo']}`", "",
               tabla, ""]
    for r in resultados:
        informe += [f"## {r['configuracion']} — {r['descripcion']}", "",
                    f"Tokens por fragmento: {r['tokens_por_fragmento']} · truncados: {r['fragmentos_truncados']}", "",
                    f"Similitud top-1: {r['metricas']['similitud_top1']}", "",
                    f"Abstención por umbral: {r['metricas']['abstencion_por_umbral']}", "", "Fallos de recuperación @4:", "",
                    _fallos_markdown(r, 4), ""]
    ruta_md = ruta_json.with_suffix(".md")
    ruta_md.write_text("\n".join(informe), encoding="utf-8")
    print(f"\nResultados: {ruta_json.relative_to(RAIZ_REPO)} y {ruta_md.relative_to(RAIZ_REPO)}")


if __name__ == "__main__":
    main()
