"""Verificación del corpus oficial del CU-3 antes de indexar (T004).

Comprueba que los 5 documentos del kit estén presentes, intactos (SHA-256 igual
al del ZIP original del kit) y con encabezado legible (código, versión, estado).

Uso:
    uv run python -m backend.rag.verify_corpus
Termina con código 1 si alguna verificación falla.
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

from backend.rag.indexer import CORPUS_DIR_DEFECTO, RAIZ_REPO, leer_documento

ZIP_KIT = RAIZ_REPO / "archivos-base" / "Kit_Entrega_3_MIRA.zip"

# SHA-256 de los documentos dentro de Kit_Entrega_3_MIRA.zip (fuente primaria).
HASHES_ESPERADOS = {
    "FIC-PLA_fichas_plantillas.md": "fec20d832a0a64a5352348c92d3db4dc619e54b09d42066ee0b5f0d93f9874d4",
    "GUI-INC_v1_derogada.md": "ffadb68d9f3979b425729aa7161998bb7ed511c27507bbeb7ccd9165db6649d0",
    "GUI-INC_v2_vigente.md": "01d1412b0104c9f232c23313697c49cec7c89150f1ef41f98a269503f915d387",
    "POL-FOR_formularios_propios.md": "843ede0dd4f27f5b2ab43eae0f912beed3427eb2c97ab674e4e839e176a65177",
    "REQ-INT_requisitos_integracion.md": "4fd6f5d4d9bb2a2e220ff11f3526a42be53ea82c9e6dfed13d9c947b1132cb77",
}


def sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def hashes_del_zip(ruta_zip: Path = ZIP_KIT) -> dict[str, str]:
    """SHA-256 de los .md del CU-3 dentro del ZIP original, si el ZIP existe."""
    if not ruta_zip.exists():
        return {}
    with zipfile.ZipFile(ruta_zip) as kit:
        return {
            Path(nombre).name: sha256(kit.read(nombre))
            for nombre in kit.namelist()
            if "CU-3" in nombre and nombre.endswith(".md")
        }


def verificar(corpus_dir: Path = CORPUS_DIR_DEFECTO) -> list[str]:
    """Devuelve la lista de problemas encontrados (vacía si todo está bien)."""
    problemas: list[str] = []
    presentes = {p.name for p in corpus_dir.glob("*.md")}
    for faltante in sorted(HASHES_ESPERADOS.keys() - presentes):
        problemas.append(f"Falta {faltante}")
    for extra in sorted(presentes - HASHES_ESPERADOS.keys()):
        problemas.append(f"Documento no declarado en el inventario: {extra}")

    del_zip = hashes_del_zip()
    for nombre, esperado in HASHES_ESPERADOS.items():
        ruta = corpus_dir / nombre
        if not ruta.exists():
            continue
        actual = sha256(ruta.read_bytes())
        if actual != esperado:
            problemas.append(f"{nombre} fue modificado (sha256 {actual[:12]}… ≠ {esperado[:12]}…)")
        if del_zip and del_zip.get(nombre) != esperado:
            problemas.append(f"{nombre}: el hash registrado no coincide con el ZIP original del kit")
        try:
            leer_documento(ruta)
        except ValueError as err:
            problemas.append(str(err))
    return problemas


def main() -> None:
    problemas = verificar()
    if problemas:
        print("Corpus CU-3 con problemas:")
        for p in problemas:
            print(f"  - {p}")
        sys.exit(1)
    for nombre in sorted(HASHES_ESPERADOS):
        doc = leer_documento(CORPUS_DIR_DEFECTO / nombre)
        print(f"[OK] {doc.doc_code} {doc.version} ({doc.status}) · {nombre}")
    print("Corpus CU-3 íntegro: 5 documentos, hashes iguales al ZIP original del kit.")


if __name__ == "__main__":
    main()
