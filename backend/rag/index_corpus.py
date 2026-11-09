"""CLI de indexación offline del corpus CU-3.

Uso (desde la raíz del repositorio):

    uv run python -m backend.rag.index_corpus                 # estrategia por encabezados
    uv run python -m backend.rag.index_corpus --estrategia todas

Cada ejecución reconstruye la colección desde cero, de modo que el índice es
reproducible: mismos documentos -> mismos chunk_id y misma huella del corpus.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.rag.indexer import ESTRATEGIAS, SOLAPE_FIJO_DEFECTO, TAMANO_FIJO_DEFECTO, indexar, resolver_persist_dir
from backend.rag.verify_corpus import verificar


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Indexa el corpus CU-3 en ChromaDB.")
    parser.add_argument("--estrategia", choices=(*ESTRATEGIAS, "todas"), default="encabezados")
    parser.add_argument("--tamano", type=int, default=TAMANO_FIJO_DEFECTO, help="palabras por fragmento (estrategia fijo)")
    parser.add_argument("--solape", type=int, default=SOLAPE_FIJO_DEFECTO, help="palabras de solapamiento (estrategia fijo)")
    parser.add_argument("--persist-dir", default=None, help="directorio de ChromaDB (por defecto CHROMA_PERSIST_DIRECTORY)")
    parser.add_argument("--sin-verificar", action="store_true", help="omite la verificación de integridad del corpus (T004)")
    args = parser.parse_args(argv)

    if not args.sin_verificar:
        problemas = verificar()
        if problemas:
            print("No se indexa: el corpus no coincide con el kit original.\n  - " + "\n  - ".join(problemas))
            sys.exit(1)

    estrategias = ESTRATEGIAS if args.estrategia == "todas" else (args.estrategia,)
    for estrategia in estrategias:
        opciones = {"tamano": args.tamano, "solape": args.solape} if estrategia == "fijo" else {}
        resumen = indexar(estrategia, persist_dir=args.persist_dir, **opciones)
        visible = {k: v for k, v in resumen.items() if k != "chunk_ids"}
        print(json.dumps(visible, ensure_ascii=False, indent=2))
    print(f"Índice persistido en {resolver_persist_dir(args.persist_dir)}")


if __name__ == "__main__":
    main()
