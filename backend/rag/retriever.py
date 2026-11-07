"""Consulta del RAG (fase de consulta, separada de la indexación).

``buscar_reglas`` implementa el contrato de la herramienta MCP homónima
(``specs/001-incorporacion-organizaciones/contracts/mcp-tools.json``). El
servidor FastMCP solo necesita envolverla; la función no invoca al LLM, por lo
que también la usa directamente la evaluación de recuperación (Recall@k).

Modos de búsqueda:
- ``denso``: similitud coseno de embeddings en ChromaDB.
- ``hibrido`` (por defecto): fusiona el ranking denso con BM25 mediante RRF.
  Ver ``docs/decisiones.md`` (ADR-10) y ``tests/evaluation/resultados/``.

En ambos modos ``similarity_score`` es la similitud coseno densa del fragmento,
para que el umbral de evidencia tenga la misma escala.
"""

from __future__ import annotations

import os
from typing import Any

from backend.rag.indexer import COLECCIONES, abrir_cliente, vectorizar
from backend.rag.lexico import BM25, fusion_rrf

FILTROS_VIGENCIA = ("vigente", "todas")
MODOS = ("denso", "hibrido")
TOP_K_MIN, TOP_K_MAX = 1, 10
CAMPOS_RESULTADO = ("chunk_id", "doc_code", "doc_title", "section", "version", "status", "text", "similarity_score")


def umbral_defecto() -> float:
    """Similitud mínima para considerar un fragmento como evidencia (``RAG_SCORE_THRESHOLD``)."""
    return float(os.environ.get("RAG_SCORE_THRESHOLD", "0.35"))


def modo_defecto() -> str:
    return os.environ.get("RAG_MODO_BUSQUEDA", "hibrido")


class Recuperador:
    """Búsqueda sobre una colección ya indexada (no reindexa).

    Si se vuelve a ejecutar ``index_corpus`` mientras un proceso usa un Recuperador,
    la colección se recrea y hay que reiniciar ese proceso (p. ej. el servidor MCP).
    """

    def __init__(self, estrategia: str = "encabezados", persist_dir: str | None = None, modo: str | None = None):
        self.estrategia = estrategia
        self.modo = modo or modo_defecto()
        if self.modo not in MODOS:
            raise ValueError(f"modo debe ser uno de {MODOS}")
        self._coleccion = abrir_cliente(persist_dir).get_collection(COLECCIONES[estrategia])

        # Índice léxico en memoria sobre los mismos fragmentos de ChromaDB.
        datos = self._coleccion.get(include=["documents", "metadatas"])
        self._ids: list[str] = datos["ids"]
        self._fragmentos = {
            i: {**meta, "text": texto} for i, texto, meta in zip(datos["ids"], datos["documents"], datos["metadatas"])
        }
        self._bm25 = BM25([
            f"{m['doc_title']} · {m['section']} {m['section_title']}\n{m['text']}"
            for m in (self._fragmentos[i] for i in self._ids)
        ])

    def buscar(
        self,
        consulta: str,
        top_k: int = 4,
        filtro_vigencia: str = "vigente",
        umbral: float | None = 0.0,
    ) -> list[dict[str, Any]]:
        """Devuelve hasta ``top_k`` fragmentos, del más al menos relevante.

        ``umbral`` es un filtro por CONSULTA, no por fragmento: si ningún candidato
        alcanza esa similitud coseno se devuelve una lista vacía (no hay evidencia);
        si alguno la alcanza se devuelven los ``top_k`` mejores del ranking. Filtrar
        por fragmento eliminaba evidencia correcta que la búsqueda híbrida sí
        rankeaba arriba (p. ej. la ficha PLA-CTA, similitud 0.32). ``None`` usa
        ``RAG_SCORE_THRESHOLD``.
        """
        if not consulta or not consulta.strip():
            raise ValueError("La consulta no puede estar vacía")
        if filtro_vigencia not in FILTROS_VIGENCIA:
            raise ValueError(f"filtro_vigencia debe ser uno de {FILTROS_VIGENCIA}")
        if not TOP_K_MIN <= top_k <= TOP_K_MAX:
            raise ValueError(f"top_k debe estar entre {TOP_K_MIN} y {TOP_K_MAX}")
        umbral = umbral_defecto() if umbral is None else umbral

        candidatos = [
            i for i in self._ids if filtro_vigencia == "todas" or self._fragmentos[i]["status"] == "vigente"
        ]
        if not candidatos:
            return []

        # Ranking denso completo (el corpus es pequeño: decenas de fragmentos).
        densa = self._coleccion.query(
            query_embeddings=vectorizar([consulta]),
            n_results=len(candidatos),
            where={"status": "vigente"} if filtro_vigencia == "vigente" else None,
            include=["distances"],
        )
        similitud = {i: round(1.0 - float(d), 4) for i, d in zip(densa["ids"][0], densa["distances"][0])}
        ranking_denso = list(densa["ids"][0])

        if self.modo == "hibrido":
            puntajes = dict(zip(self._ids, self._bm25.puntajes(consulta)))
            ranking_lexico = sorted((i for i in candidatos if puntajes[i] > 0), key=lambda i: (-puntajes[i], i))
            orden = fusion_rrf([ranking_denso, ranking_lexico])
        else:
            orden = ranking_denso

        if max(similitud.values(), default=0.0) < umbral:
            return []
        return [{**self._fragmentos[i], "similarity_score": similitud.get(i, 0.0)} for i in orden[:top_k]]


_RECUPERADORES: dict[str, Recuperador] = {}


def obtener_recuperador(estrategia: str = "encabezados") -> Recuperador:
    if estrategia not in _RECUPERADORES:
        _RECUPERADORES[estrategia] = Recuperador(estrategia)
    return _RECUPERADORES[estrategia]


def buscar_reglas(query: str, top_k: int = 4, filtro_vigencia: str = "vigente") -> dict[str, Any]:
    """Herramienta ``buscar_reglas`` según contracts/mcp-tools.json.

    Retorna ``{"total_found": n, "results": [...]}`` con exactamente los campos del
    contrato. Si ningún fragmento alcanza ``RAG_SCORE_THRESHOLD`` la lista viene vacía:
    no hay evidencia y el orquestador debe abstenerse (PR-3).
    Una lista no vacía NO garantiza que la respuesta esté en el corpus: el umbral
    no separa bien las preguntas sin respuesta (ver resultados de evaluación).
    """
    fragmentos = obtener_recuperador().buscar(query, top_k=top_k, filtro_vigencia=filtro_vigencia, umbral=None)
    resultados = [{campo: f[campo] for campo in CAMPOS_RESULTADO} for f in fragmentos]
    return {"total_found": len(resultados), "results": resultados}
