"""Búsqueda léxica BM25 (Okapi) sin dependencias externas.

Complementa la búsqueda densa en la recuperación híbrida: los embeddings
pierden términos exactos como códigos de plantilla (``PLA-CTA``) o etapas
(``E3``), que BM25 recupera por coincidencia literal.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

# Palabras funcionales del español que no aportan a la coincidencia léxica.
PALABRAS_VACIAS = frozenset(
    """a al como con cual cuales cuando cuanto cuantos de del el en es esa ese esta este hay la las lo los mas
    no o para por puede que quien se ser si sin son su sus un una y debe""".split()
)


def tokenizar(texto: str) -> list[str]:
    """Minúsculas, sin tildes, solo alfanuméricos; descarta palabras vacías y de una letra."""
    plano = unicodedata.normalize("NFKD", texto.lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return [t for t in re.findall(r"[a-z0-9]+", plano) if len(t) > 1 and t not in PALABRAS_VACIAS]


class BM25:
    def __init__(self, textos: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self._docs = [Counter(tokenizar(t)) for t in textos]
        self._largos = [sum(d.values()) for d in self._docs]
        self._largo_medio = (sum(self._largos) / len(self._largos)) if self._largos else 0.0
        frecuencia_doc = Counter(t for d in self._docs for t in d)
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in frecuencia_doc.items()}

    def puntajes(self, consulta: str) -> list[float]:
        terminos = tokenizar(consulta)
        salida = []
        for doc, largo in zip(self._docs, self._largos):
            puntaje = 0.0
            for termino in terminos:
                tf = doc.get(termino)
                if tf:
                    norma = tf + self.k1 * (1 - self.b + self.b * largo / self._largo_medio)
                    puntaje += self._idf[termino] * tf * (self.k1 + 1) / norma
            salida.append(puntaje)
        return salida


def fusion_rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal Rank Fusion (Cormack et al., 2009) con la constante estándar k=60."""
    puntaje: dict[str, float] = {}
    for ranking in rankings:
        for posicion, ident in enumerate(ranking, start=1):
            puntaje[ident] = puntaje.get(ident, 0.0) + 1.0 / (k + posicion)
    return sorted(puntaje, key=lambda i: (-puntaje[i], i))
