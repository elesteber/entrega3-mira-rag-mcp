"""buscar_reglas por MCP stdio entre procesos, con delegación AUD-03 (T010).

El servidor corre en un proceso independiente (StdioTransport), igual que lo
lanzará el backend FastAPI. Requiere el índice RAG generado
(uv run python -m backend.rag.index_corpus); si no existe, las pruebas que lo
necesitan se omiten con el motivo.
"""

from __future__ import annotations

import json

import pytest

from backend.rag.indexer import resolver_persist_dir
from tests.integration.test_auth_stdio import cliente, credencial, entorno  # noqa: F401 (fixture)
from tests.integration.test_mcp_buscar_reglas import requiere_indice

pytestmark = pytest.mark.modelo

CONSULTA = {"query": "¿Cuáles son los criterios de salida a producción?", "top_k": 2}


def _con_indice(env: dict, persist_dir) -> dict:
    """Fija el índice del subproceso sin depender del entorno del desarrollador."""
    return {**env, "CHROMA_PERSIST_DIRECTORY": str(persist_dir), "CHROMADB_PATH": str(persist_dir)}


def _datos(resultado) -> dict:
    return resultado.structured_content or json.loads(resultado.content[0].text)


def _texto(resultado) -> str:
    return " ".join(getattr(bloque, "text", "") for bloque in resultado.content)


@requiere_indice
@pytest.mark.asyncio
async def test_buscar_reglas_por_stdio_exige_delegacion(entorno):  # noqa: F811
    _, secret, _, env = entorno
    async with cliente(_con_indice(env, resolver_persist_dir())) as client:
        assert "buscar_reglas" in [t.name for t in await client.list_tools()]

        sin_delegacion = await client.call_tool("buscar_reglas", CONSULTA, raise_on_error=False)
        assert sin_delegacion.is_error

        for usuario in ("U-I1", "U-I4"):  # U-I4 comercial también consulta normativa (FR-017)
            respuesta = await client.call_tool(
                "buscar_reglas", CONSULTA,
                meta={"mira_delegation": credencial(secret, usuario)}, raise_on_error=False,
            )
            assert not respuesta.is_error
            assert _datos(respuesta)["results"][0]["chunk_id"] == "GUI-INC-V2-SEC3-P1"


@pytest.mark.asyncio
async def test_indice_ausente_por_stdio_no_expone_detalles(entorno, tmp_path):  # noqa: F811
    _, secret, _, env = entorno
    vacio = tmp_path / "sin_indice"
    async with cliente(_con_indice(env, vacio)) as client:
        respuesta = await client.call_tool(
            "buscar_reglas", CONSULTA,
            meta={"mira_delegation": credencial(secret)}, raise_on_error=False,
        )
    assert respuesta.is_error
    texto = _texto(respuesta)
    assert "index_corpus" in texto
    assert str(vacio) not in texto
    assert "Collection" not in texto and "Error:" not in texto.split("index_corpus")[-1]
