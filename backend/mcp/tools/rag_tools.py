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

import logging
from typing import Any, Literal

logger = logging.getLogger(__name__)

MENSAJE_INDICE_NO_DISPONIBLE = (
    "Índice RAG no disponible: ejecute 'uv run python -m backend.rag.index_corpus' "
    "antes de levantar el servidor MCP."
)


MENSAJE_ERROR_BUSQUEDA = "No se pudo completar la búsqueda normativa en el índice RAG."


class IndiceRagNoDisponible(RuntimeError):
    """El índice ChromaDB no fue generado o no se puede abrir."""


class ErrorBusquedaRag(RuntimeError):
    """El índice existe, pero la búsqueda falló (ChromaDB o modelo de embeddings)."""


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
    try:
        # El import también va aquí: si falta una dependencia del RAG (chromadb,
        # sentence-transformers) se informa igual que un índice ausente.
        from backend.rag import retriever

        recuperador = retriever.obtener_recuperador()
    except Exception:  # dependencia ausente, colección inexistente o directorio sin índice
        # El detalle (rutas, tipo de excepción) queda solo en el log del servidor (stderr);
        # el cliente MCP recibe un mensaje fijo, sin datos internos.
        logger.error("No se pudo abrir el índice RAG.", exc_info=True)
        raise IndiceRagNoDisponible(MENSAJE_INDICE_NO_DISPONIBLE) from None

    del recuperador  # buscar_reglas reutiliza la instancia ya cacheada
    try:
        return retriever.buscar_reglas(query, top_k=top_k, filtro_vigencia=filtro_vigencia)
    except ValueError:
        # Validación de argumentos (consulta vacía, top_k o filtro fuera de rango):
        # su mensaje no expone datos internos y le sirve al modelo para corregir la llamada.
        raise
    except Exception:  # fallo de ChromaDB o del modelo de embeddings durante la búsqueda
        logger.error("Falló la búsqueda en el índice RAG.", exc_info=True)
        raise ErrorBusquedaRag(MENSAJE_ERROR_BUSQUEDA) from None
