"""
Herramienta FastMCP buscar_reglas (STUB coordinado según contracts/mcp-tools.json).
MIRA CU-3 - Asistente de Incorporación de Organizaciones.

NOTA DE COORDINACIÓN:
Esta herramienta corresponde a la tarea T010 asignada a Ángel Salgado (Especialista RAG y Evaluación).
Se expone este stub con la firma y esquemas contractuales acordados para permitir el registro modular
y la inicialización completa del servidor FastMCP (T007).
"""

from __future__ import annotations

from typing import Any, Literal


def buscar_reglas(
    query: str,
    top_k: int = 4,
    filtro_vigencia: Literal["vigente", "todas"] = "vigente",
) -> dict[str, Any]:
    """
    Recupera fragmentos normativos relevantes desde ChromaDB sobre los 5 documentos oficiales del CU-3
    (GUI-INC v1 derogada, GUI-INC v2 vigente, POL-FOR, FIC-PLA, REQ-INT).
    Proporciona evidencia documental con chunk_id y metadatos unificados para citas verificables (PR-2).

    NOTA: Stub temporal mientras Ángel Salgado finaliza la indexación en ChromaDB (T008, T009, T010).
    """
    # Intentar delegar si existe retriever implementado en backend.rag
    try:
        from backend.rag.retriever import retrieve_chunks  # type: ignore
        return retrieve_chunks(query=query, top_k=top_k, filtro_vigencia=filtro_vigencia)
    except (ImportError, ModuleNotFoundError):
        # Stub documentado conforme a contracts/mcp-tools.json
        return {
            "total_found": 0,
            "results": [],
            "_stub_status": "PENDIENTE_DE_COORDINACION_CON_ANGEL_SALGADO",
            "_note": "Índice ChromaDB en proceso de generación offline por Ángel Salgado (T008, T009).",
        }

