"""Indexación offline del corpus CU-3 (fase de indexación del RAG).

Este módulo hace tres cosas, separadas de la consulta (pauta §6.2):

1. Lee los documentos Markdown del kit y extrae los metadatos de su encabezado
   (código, versión, estado, vigencia), que se conservan en cada fragmento.
2. Fragmenta cada documento con una de dos estrategias comparables:
   - ``encabezados``: un fragmento por sección ``##`` (y por subsección ``###``
     cuando existen, por ejemplo cada plantilla de FIC-PLA §2).
   - ``fijo``: ventanas de tamaño fijo en palabras con solapamiento.
3. Calcula embeddings y persiste los fragmentos en ChromaDB.

Las funciones de lectura y fragmentación no dependen de ChromaDB ni del modelo,
para poder probarlas sin descargas (``tests/unit/test_rag_chunker.py``).
Los ``chunk_id`` son deterministas: indexar dos veces produce los mismos ids.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

RAIZ_REPO = Path(__file__).resolve().parents[2]
CORPUS_DIR_DEFECTO = RAIZ_REPO / "archivos-base" / "Kit_Entrega_3_MIRA" / "CU-3_incorporacion_organizaciones" / "corpus"
PERSIST_DIR_DEFECTO = "backend/data/chroma_db"
MODELO_DEFECTO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# El modelo trae max_seq_length=128 y truncaría 11 de 24 secciones; con 256 ninguna
# se trunca (BERT admite hasta 512 posiciones). Elegido por experimento (ADR-10).
MAX_SEQ_LENGTH_DEFECTO = 256

ESTRATEGIAS = ("encabezados", "fijo")
COLECCIONES = {
    "encabezados": "mira_corpus_cu3",  # colección usada por buscar_reglas
    "fijo": "mira_corpus_cu3_fijo",  # solo para el experimento comparativo
}
TAMANO_FIJO_DEFECTO = 150  # palabras (~200 tokens del tokenizador del modelo)
SOLAPE_FIJO_DEFECTO = 40  # palabras (~50 tokens)


# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Documento:
    doc_code: str
    doc_title: str
    version: str  # "v1.0", "v2.0" (formato de contracts/mcp-tools.json)
    status: str  # "vigente" | "derogada" | "en_revision"
    vigencia: str
    responsable: str
    archivo: str
    texto: str


@dataclass(frozen=True)
class Seccion:
    numero: int  # 0 = ficha del documento (encabezado antes de la primera sección)
    titulo: str
    texto: str  # incluye la línea de encabezado


@dataclass(frozen=True)
class Fragmento:
    chunk_id: str
    doc_code: str
    doc_title: str
    section: str  # "§3", "§2 (PLA-ADM)", "§2–§3" (fijo, abarca dos secciones)
    section_title: str
    version: str
    status: str
    vigencia: str
    archivo: str
    estrategia: str
    text: str

    def metadatos(self) -> dict[str, str]:
        """Metadatos planos para ChromaDB (solo valores escalares)."""
        datos = asdict(self)
        datos.pop("text")
        datos["origin"] = "kit_cu3"
        return datos

    def texto_para_embedding(self) -> str:
        """Texto que se vectoriza: contexto del documento + contenido."""
        return f"{self.doc_title} · {self.section} {self.section_title}\n{self.text}"


# ---------------------------------------------------------------------------
# Lectura de documentos
# ---------------------------------------------------------------------------

_FILA_TABLA = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$")


def _normalizar_estado(valor: str) -> str:
    limpio = valor.replace("*", "").strip().lower()
    if limpio.startswith("derogad"):
        return "derogada"
    if limpio.startswith("vigente"):
        return "vigente"
    return "en_revision"


def _normalizar_version(valor: str) -> str:
    numero = re.search(r"\d+(?:\.\d+)?", valor)
    if not numero:
        raise ValueError(f"Versión ilegible: {valor!r}")
    texto = numero.group(0)
    return f"v{texto}" if "." in texto else f"v{texto}.0"


def leer_documento(ruta: Path) -> Documento:
    """Lee un documento del kit y extrae los metadatos de su tabla de encabezado."""
    texto = ruta.read_text(encoding="utf-8")
    titulo = next((ln[2:].strip() for ln in texto.splitlines() if ln.startswith("# ")), ruta.stem)

    campos: dict[str, str] = {}
    for linea in texto.splitlines():
        if linea.startswith("## "):
            break
        coincide = _FILA_TABLA.match(linea)
        if coincide and not set(coincide.group(1)) <= {"-", " "}:
            campos[coincide.group(1).strip().lower()] = coincide.group(2).strip()

    faltan = {"código", "versión", "estado"} - campos.keys()
    if faltan:
        raise ValueError(f"{ruta.name}: encabezado sin {sorted(faltan)}")

    return Documento(
        doc_code=campos["código"],
        doc_title=titulo,
        version=_normalizar_version(campos["versión"]),
        status=_normalizar_estado(campos["estado"]),
        vigencia=campos.get("vigencia", ""),
        responsable=campos.get("responsable", ""),
        archivo=ruta.name,
        texto=texto,
    )


def leer_corpus(corpus_dir: Path | None = None) -> list[Documento]:
    directorio = Path(corpus_dir or os.environ.get("CORPUS_DIR") or CORPUS_DIR_DEFECTO)
    archivos = sorted(directorio.glob("*.md"))
    if not archivos:
        raise FileNotFoundError(f"No hay documentos .md en {directorio}")
    return [leer_documento(a) for a in archivos]


# ---------------------------------------------------------------------------
# Fragmentación
# ---------------------------------------------------------------------------

_H2 = re.compile(r"^##\s+(\d+)\.\s*(.+?)\s*$")
_H3 = re.compile(r"^###\s+(.+?)\s*$")


def dividir_secciones(doc: Documento) -> list[Seccion]:
    """Divide un documento en la ficha (§0) y sus secciones ``## N. Título``."""
    secciones: list[Seccion] = []
    numero, titulo, lineas = 0, "Ficha del documento", []
    for linea in doc.texto.splitlines():
        coincide = _H2.match(linea)
        if coincide:
            secciones.append(Seccion(numero, titulo, "\n".join(lineas).strip()))
            numero, titulo, lineas = int(coincide.group(1)), coincide.group(2), []
        lineas.append(linea)
    secciones.append(Seccion(numero, titulo, "\n".join(lineas).strip()))
    return [s for s in secciones if s.texto]


def _prefijo_id(doc: Documento) -> str:
    mayor = doc.version.lstrip("v").split(".")[0]
    return f"{doc.doc_code}-V{mayor}"


def _fragmento(doc: Documento, chunk_id: str, section: str, section_title: str, estrategia: str, text: str) -> Fragmento:
    return Fragmento(
        chunk_id=chunk_id,
        doc_code=doc.doc_code,
        doc_title=doc.doc_title,
        section=section,
        section_title=section_title,
        version=doc.version,
        status=doc.status,
        vigencia=doc.vigencia,
        archivo=doc.archivo,
        estrategia=estrategia,
        text=text,
    )


def fragmentar_por_encabezados(doc: Documento) -> list[Fragmento]:
    """Estrategia A: un fragmento por sección; si la sección tiene ``###``, uno por subsección.

    Cada subsección conserva la línea ``##`` de su sección como contexto.
    chunk_id: ``{DOC}-V{n}-SEC{s}-P{k}`` (ej. ``GUI-INC-V2-SEC3-P1``).
    """
    fragmentos: list[Fragmento] = []
    prefijo = _prefijo_id(doc)
    for sec in dividir_secciones(doc):
        lineas = sec.texto.splitlines()
        cabecera = lineas[0] if sec.numero > 0 else ""
        bloques: list[tuple[str | None, list[str]]] = [(None, [])]
        for linea in lineas[1:] if sec.numero > 0 else lineas:
            coincide = _H3.match(linea)
            if coincide:
                bloques.append((coincide.group(1), [linea]))
            else:
                bloques[-1][1].append(linea)

        parte = 0
        for subtitulo, cuerpo in bloques:
            contenido = "\n".join(cuerpo).strip()
            if not contenido:
                continue
            parte += 1
            if subtitulo is None:
                section, titulo = f"§{sec.numero}", sec.titulo
            else:
                codigo = subtitulo.split(".")[0].strip()
                section, titulo = f"§{sec.numero} ({codigo})", subtitulo
            texto = f"{cabecera}\n{contenido}".strip()
            chunk_id = f"{prefijo}-SEC{sec.numero}-P{parte}"
            fragmentos.append(_fragmento(doc, chunk_id, section, titulo, "encabezados", texto))
    return fragmentos


def fragmentar_tamano_fijo(
    doc: Documento,
    tamano: int = TAMANO_FIJO_DEFECTO,
    solape: int = SOLAPE_FIJO_DEFECTO,
) -> list[Fragmento]:
    """Estrategia B: ventanas de ``tamano`` palabras con ``solape`` palabras repetidas.

    Ignora la estructura del documento (línea base del experimento). La sección
    registrada es la de la primera y última palabra de la ventana.
    chunk_id: ``{DOC}-V{n}-FIX-{i:03d}``.
    """
    if not 0 <= solape < tamano:
        raise ValueError("Se requiere 0 <= solape < tamano")

    palabras: list[str] = []
    seccion_de_palabra: list[tuple[int, str]] = []
    for sec in dividir_secciones(doc):
        trozos = sec.texto.split()
        palabras.extend(trozos)
        seccion_de_palabra.extend([(sec.numero, sec.titulo)] * len(trozos))

    fragmentos: list[Fragmento] = []
    paso = tamano - solape
    prefijo = _prefijo_id(doc)
    inicio = 0
    while inicio < len(palabras):
        fin = min(inicio + tamano, len(palabras))
        (n_ini, t_ini), (n_fin, _) = seccion_de_palabra[inicio], seccion_de_palabra[fin - 1]
        section = f"§{n_ini}" if n_ini == n_fin else f"§{n_ini}–§{n_fin}"
        chunk_id = f"{prefijo}-FIX-{len(fragmentos) + 1:03d}"
        fragmentos.append(_fragmento(doc, chunk_id, section, t_ini, "fijo", " ".join(palabras[inicio:fin])))
        if fin == len(palabras):
            break
        inicio += paso
    return fragmentos


def fragmentar(docs: Iterable[Documento], estrategia: str, **opciones: int) -> list[Fragmento]:
    if estrategia == "encabezados":
        fragmentos = [f for d in docs for f in fragmentar_por_encabezados(d)]
    elif estrategia == "fijo":
        fragmentos = [f for d in docs for f in fragmentar_tamano_fijo(d, **opciones)]
    else:
        raise ValueError(f"Estrategia desconocida: {estrategia!r}. Opciones: {ESTRATEGIAS}")
    ids = [f.chunk_id for f in fragmentos]
    if len(ids) != len(set(ids)):
        raise ValueError("chunk_id duplicados")
    return fragmentos


# ---------------------------------------------------------------------------
# Embeddings y persistencia
# ---------------------------------------------------------------------------


def resolver_persist_dir(persist_dir: str | Path | None = None) -> Path:
    valor = Path(persist_dir or os.environ.get("CHROMA_PERSIST_DIRECTORY") or PERSIST_DIR_DEFECTO)
    return valor if valor.is_absolute() else RAIZ_REPO / valor


def nombre_modelo() -> str:
    return os.environ.get("EMBEDDING_MODEL_NAME") or MODELO_DEFECTO


_MODELOS: dict[str, object] = {}


def max_seq_length_configurado() -> int:
    """Límite de tokens al vectorizar (``EMBEDDING_MAX_SEQ_LENGTH``, por defecto 256)."""
    return int(os.environ.get("EMBEDDING_MAX_SEQ_LENGTH") or MAX_SEQ_LENGTH_DEFECTO)


def cargar_modelo(nombre: str | None = None):
    """Carga (una vez por proceso) el modelo de embeddings en CPU.

    Los tokens que exceden ``max_seq_length`` se truncan al vectorizar; por eso el
    límite es parte de la configuración del índice y debe ser el mismo al indexar y
    al consultar.
    """
    nombre = nombre or nombre_modelo()
    if nombre not in _MODELOS:
        from sentence_transformers import SentenceTransformer

        _MODELOS[nombre] = SentenceTransformer(nombre, device="cpu")
    modelo = _MODELOS[nombre]
    modelo.max_seq_length = max_seq_length_configurado()
    return modelo


def vectorizar(textos: list[str], modelo=None) -> list[list[float]]:
    modelo = modelo or cargar_modelo()
    vectores = modelo.encode(textos, normalize_embeddings=True, show_progress_bar=False)
    return vectores.tolist()


def abrir_cliente(persist_dir: str | Path | None = None):
    import chromadb
    from chromadb.config import Settings

    ruta = resolver_persist_dir(persist_dir)
    ruta.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(ruta), settings=Settings(anonymized_telemetry=False))


def huella_corpus(docs: Iterable[Documento]) -> str:
    h = hashlib.sha256()
    for d in sorted(docs, key=lambda d: d.archivo):
        h.update(d.archivo.encode())
        h.update(d.texto.encode())
    return h.hexdigest()


def indexar(
    estrategia: str = "encabezados",
    corpus_dir: Path | None = None,
    persist_dir: str | Path | None = None,
    **opciones: int,
) -> dict:
    """Reconstruye desde cero la colección de una estrategia. Devuelve un resumen."""
    docs = leer_corpus(corpus_dir)
    fragmentos = fragmentar(docs, estrategia, **opciones)
    modelo = cargar_modelo()
    vectores = vectorizar([f.texto_para_embedding() for f in fragmentos], modelo)

    cliente = abrir_cliente(persist_dir)
    nombre = COLECCIONES[estrategia]
    try:
        cliente.delete_collection(nombre)
    except Exception:  # la colección aún no existe
        pass
    limite = int(modelo.max_seq_length)
    coleccion = cliente.create_collection(
        nombre, metadata={"hnsw:space": "cosine", "estrategia": estrategia, "max_seq_length": limite}
    )
    coleccion.add(
        ids=[f.chunk_id for f in fragmentos],
        embeddings=vectores,
        documents=[f.text for f in fragmentos],
        metadatas=[f.metadatos() for f in fragmentos],
    )

    tokenizador = modelo.tokenizer
    tokens = [len(tokenizador.encode(f.texto_para_embedding(), add_special_tokens=True)) for f in fragmentos]
    resumen = {
        "coleccion": nombre,
        "estrategia": estrategia,
        "opciones": opciones,
        "modelo": nombre_modelo(),
        "max_seq_length": limite,
        "documentos": [{"archivo": d.archivo, "doc_code": d.doc_code, "version": d.version, "status": d.status} for d in docs],
        "huella_corpus_sha256": huella_corpus(docs),
        "total_fragmentos": len(fragmentos),
        "tokens_por_fragmento": {"min": min(tokens), "max": max(tokens), "promedio": round(sum(tokens) / len(tokens), 1)},
        "fragmentos_truncados": sum(t > limite for t in tokens),
        "chunk_ids": [f.chunk_id for f in fragmentos],
    }
    manifiesto = resolver_persist_dir(persist_dir) / f"manifiesto_{nombre}.json"
    manifiesto.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumen
