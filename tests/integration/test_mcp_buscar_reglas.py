"""Integración de buscar_reglas en el servidor FastMCP (T010).

Requiere el índice RAG generado (uv run python -m backend.rag.index_corpus);
si no existe, las pruebas que lo necesitan se omiten con el motivo.
"""

from __future__ import annotations

import pytest

from backend.mcp.tools import rag_tools
from backend.rag import retriever
from backend.rag.indexer import COLECCIONES, abrir_cliente
from tests.clients.test_external_mcp_client import execute_tool_call, get_available_tools

pytestmark = pytest.mark.modelo


def _indice_disponible() -> bool:
    try:
        abrir_cliente().get_collection(COLECCIONES["encabezados"])
        return True
    except Exception:
        return False


requiere_indice = pytest.mark.skipif(not _indice_disponible(), reason="índice RAG no generado")


def test_buscar_reglas_registrada_en_servidor():
    assert "buscar_reglas" in get_available_tools()


@requiere_indice
def test_cliente_externo_obtiene_criterios_con_chunk_id():
    res = execute_tool_call("U-I1", "buscar_reglas", {"query": "¿Cuáles son los criterios de salida a producción?"})
    assert res["status"] == 200
    primero = res["result"]["results"][0]
    assert primero["chunk_id"] == "GUI-INC-V2-SEC3-P1"
    assert (primero["doc_code"], primero["section"], primero["version"]) == ("GUI-INC", "§3", "v2.0")


@requiere_indice
def test_rol_comercial_puede_consultar_normativa():
    res = execute_tool_call("U-I4", "buscar_reglas", {"query": "¿Qué módulos incluye la plantilla de apertura de cuenta?"})
    assert res["status"] == 200 and res["result"]["total_found"] > 0


@requiere_indice
def test_filtro_todas_incluye_version_derogada():
    res = execute_tool_call(
        "U-I3", "buscar_reglas",
        {"query": "¿Cuánto toma la incorporación completa desde la firma?", "top_k": 10, "filtro_vigencia": "todas"},
    )
    assert any(f["status"] == "derogada" for f in res["result"]["results"])


def test_indice_ausente_da_error_explicito(monkeypatch):
    def falla():
        raise ValueError("Collection [mira_corpus_cu3] does not exist")

    monkeypatch.setattr(retriever, "obtener_recuperador", falla)
    with pytest.raises(rag_tools.IndiceRagNoDisponible, match="index_corpus"):
        rag_tools.buscar_reglas("criterios de salida a producción")


@requiere_indice
def test_llamada_por_protocolo_mcp_real():
    """Cliente FastMCP en memoria: recorre el protocolo MCP (list_tools + call_tool), no la función directa."""
    import asyncio
    import json

    from fastmcp import Client

    from backend.mcp.server import mcp

    async def llamar():
        async with Client(mcp) as cliente:
            nombres = [t.name for t in await cliente.list_tools()]
            respuesta = await cliente.call_tool(
                "buscar_reglas", {"query": "¿Cuáles son los criterios de salida a producción?", "top_k": 2}
            )
            datos = respuesta.structured_content or json.loads(respuesta.content[0].text)
            return nombres, datos

    nombres, datos = asyncio.run(llamar())
    assert "buscar_reglas" in nombres
    assert datos["results"][0]["chunk_id"] == "GUI-INC-V2-SEC3-P1"
