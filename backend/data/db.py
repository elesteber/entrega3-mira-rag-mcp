"""
Configuración de base de datos relacional y gestión de conexiones SQLite con thread-safety.
MIRA CU-3 - Caso de Uso: Asistente de Incorporación de Organizaciones.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Sequence

# Ruta por defecto de la base de datos relacional
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "mira_cu3.db"


def get_db_path() -> Path:
    """
    Retorna la ruta absoluta al archivo SQLite resolviendo desde la variable de entorno
    SQLITE_DB_PATH o utilizando la ruta unificada por defecto.
    """
    env_path = os.getenv("SQLITE_DB_PATH")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p
    return DEFAULT_DB_PATH


def create_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """
    Crea una nueva conexión SQLite configurada para alta concurrencia y seguridad relacional.
    - check_same_thread=False para permitir uso en servidores asíncronos y multihilo.
    - PRAGMA foreign_keys = ON para integridad referencial obligatoria.
    - PRAGMA journal_mode = WAL para lecturas concurrentes sin bloqueo.
    - PRAGMA busy_timeout = 5000 para reintentos transparentes ante contención.
    - row_factory = sqlite3.Row para acceso posicional y por nombre de columna.
    """
    target_path = Path(db_path) if db_path else get_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(target_path),
        timeout=30.0,
        check_same_thread=False,
        isolation_level=None,  # Autocommit manual para control explícito de transacciones
    )
    conn.row_factory = sqlite3.Row

    # Configuraciones de rendimiento y robustez
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.close()

    return conn


@contextmanager
def get_db_connection(db_path: str | Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager generador de conexión SQLite.
    Garantiza el cierre seguro de la conexión al salir del contexto.
    """
    conn = create_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection, mode: str = "IMMEDIATE") -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager para transacciones atómicas SQLite.
    Usa 'BEGIN IMMEDIATE' por defecto para prevenir deadlocks en escrituras concurrentes.
    Realiza COMMIT automático al salir sin errores o ROLLBACK ante cualquier excepción.
    """
    cursor = conn.cursor()
    cursor.execute(f"BEGIN {mode};")
    try:
        yield cursor
        cursor.execute("COMMIT;")
    except Exception:
        cursor.execute("ROLLBACK;")
        raise
    finally:
        cursor.close()

