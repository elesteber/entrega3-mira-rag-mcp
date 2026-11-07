"""
Herramienta FastMCP buscar_reglas (T010) según contracts/mcp-tools.json.
MIRA CU-3 - Asistente de Incorporación de Organizaciones.

Envuelve la consulta del RAG (backend/rag/retriever.py). No accede a SQLite ni
requiere organización: la documentación normativa es consultable por todos los
roles, incluido el comercial (FR-017).

Si el índice ChromaDB no existe, falla con un error explícito en vez de devolver
una lista vacía: una lista vacía significa "sin evidencia" y haría que el
asistente se abstuviera en silencio por un problema de configuración.
"""

from __future__ import annotations

from typing import Any, Literal


class IndiceRagNoDisponible(RuntimeError):
    """El índice ChromaDB no fue generado o no se puede abrir."""


def buscar_reglas(
    query: str,
    top_k: int = 4,
    filtro_vigencia: Literal["vigente", "todas"] = "vigente",
) -> dict[str, Any]:
    """
    Recupera fragmentos normativos relevantes desde ChromaDB sobre los 5 documentos oficiales del CU-3
    (GUI-INC v1 derogada, GUI-INC v2 vigente, POL-FOR, FIC-PLA, REQ-INT).
    Proporciona evidencia documental con chunk_id y metadatos unificados para citas verificables (PR-2).
    Con filtro_vigencia='vigente' excluye normas derogadas; 'todas' las incluye para comparar versiones (PR-4).
    Una lista de resultados vacía indica que no hay evidencia en el corpus (PR-3).
    """
    from backend.rag import retriever

    try:
        recuperador = retriever.obtener_recuperador()
    except Exception as err:  # colección inexistente o directorio sin índice
        raise IndiceRagNoDisponible(
            "Índice RAG no disponible: ejecute 'uv run python -m backend.rag.index_corpus' "
            f"antes de levantar el servidor MCP ({type(err).__name__}: {err})."
        ) from err

    del recuperador  # buscar_reglas reutiliza la instancia ya cacheada
    return retriever.buscar_reglas(query, top_k=top_k, filtro_vigencia=filtro_vigencia)
