"""
Configuración global de pruebas pytest para MIRA CU-3.
Agrega la raíz del repositorio a sys.path y configura scope de bucle asyncio.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

