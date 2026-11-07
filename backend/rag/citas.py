"""Validación de citas documentales contra el corpus indexado (T029, PR-2).

Una cita (esquema ``Citation`` de contracts/api-rest.yaml) es válida si:
1. su ``chunk_id`` existe en el índice;
2. ``doc_code``, ``section``, ``version`` y ``status`` coinciden con los del fragmento;
3. el ``excerpt`` aparece literalmente en el fragmento (se ignoran espacios,
   comillas envolventes y elipsis «…» o «...» que separan trozos citados).

No necesita ChromaDB ni el modelo: reconstruye los fragmentos con la misma
fragmentación determinista que usa la indexación, por lo que sirve tanto al
orquestador (validar antes de responder) como a la evaluación (precisión de cita).
Validar que la cita *respalda la afirmación* sigue requiriendo juicio humano o
de un modelo evaluador (pauta §7.2); aquí se verifica que sea real y exacta.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Iterable, Mapping

from backend.rag.indexer import Fragmento, fragmentar, leer_corpus

CAMPOS_COMPARADOS = ("doc_code", "section", "version", "status")
_ELIPSIS = re.compile(r"\s*(?:…|\.\.\.)\s*")
_COMILLAS = "\"'«»“”‘’"


@lru_cache(maxsize=1)
def indice_de_fragmentos() -> dict[str, Fragmento]:
    return {f.chunk_id: f for f in fragmentar(leer_corpus(), "encabezados")}


def _normalizar(texto: str) -> str:
    texto = texto.replace("**", "")
    texto = re.sub(r"^\s*[-*]\s+", "", texto, flags=re.M)  # viñetas de lista
    return re.sub(r"\s+", " ", texto).strip().lower()


def _trozos_del_extracto(extracto: str) -> list[str]:
    limpio = extracto.strip().strip(_COMILLAS).strip()
    return [t for t in (_normalizar(p) for p in _ELIPSIS.split(limpio)) if t]


def validar_cita(cita: Mapping[str, Any], indice: Mapping[str, Fragmento] | None = None) -> list[str]:
    """Devuelve los problemas de la cita; lista vacía = cita válida."""
    indice = indice_de_fragmentos() if indice is None else indice
    chunk_id = cita.get("chunk_id")
    fragmento = indice.get(chunk_id or "")
    if fragmento is None:
        return [f"chunk_id inexistente: {chunk_id!r}"]

    problemas = [
        f"{campo} no coincide: cita={cita.get(campo)!r}, fragmento={getattr(fragmento, campo)!r}"
        for campo in CAMPOS_COMPARADOS
        if cita.get(campo) != getattr(fragmento, campo)
    ]
    trozos = _trozos_del_extracto(str(cita.get("excerpt") or ""))
    if not trozos:
        problemas.append("excerpt vacío")
    texto = _normalizar(fragmento.text)
    for trozo in trozos:
        if trozo not in texto:
            problemas.append(f"excerpt no aparece en {chunk_id}: {trozo[:80]!r}")
    return problemas


def validar_citas(citas: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Resumen para evaluación: cuántas citas son verificables y por qué fallan las demás."""
    detalle = [{"chunk_id": c.get("chunk_id"), "problemas": validar_cita(c)} for c in citas]
    validas = sum(not d["problemas"] for d in detalle)
    return {
        "total": len(detalle),
        "validas": validas,
        "proporcion_validas": round(validas / len(detalle), 4) if detalle else None,
        "detalle": detalle,
    }
